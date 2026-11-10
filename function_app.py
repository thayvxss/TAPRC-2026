import csv
import io
import logging
import os
import re
from datetime import date, datetime, time, timezone
from decimal import Decimal

import azure.functions as func
import pyodbc
from azure.storage.filedatalake import DataLakeServiceClient

app = func.FunctionApp()

ITSM_TABLES = (
    "analista",
    "categoria",
    "chamado",
    "chamado_sla",
    "chamado_status_historico",
    "cliente_organizacao",
    "csat_avaliacao",
    "fila",
    "sla",
    "solicitante",
)

ITSM_LOAD_ORDER = (
    "fila",
    "categoria",
    "cliente_organizacao",
    "sla",
    "analista",
    "solicitante",
    "chamado",
    "chamado_sla",
    "chamado_status_historico",
    "csat_avaliacao",
)

ITSM_PRIMARY_KEYS = {
    "analista": "id_analista",
    "categoria": "id_categoria",
    "chamado": "id_chamado",
    "chamado_sla": "id_chamado_sla",
    "chamado_status_historico": "id_chamado_status_historico",
    "cliente_organizacao": "id_cliente_organizacao",
    "csat_avaliacao": "id_csat_avaliacao",
    "fila": "id_fila",
    "sla": "id_sla",
    "solicitante": "id_solicitante",
}

CSV_NULL = "__AZURE_SQL_NULL_9F31A2__"


def _required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Configuração obrigatória ausente: {name}")
    return value


def _odbc_value(value: str) -> str:
    return "{" + value.replace("}", "}}") + "}"


def _sql_connection_string(
    server: str, database: str, user: str, password: str
) -> str:
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={_odbc_value(server)};"
        f"DATABASE={_odbc_value(database)};"
        f"UID={_odbc_value(user)};"
        f"PWD={_odbc_value(password)};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


@app.timer_trigger(
    schedule="0 0 4 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True,
)
def extract_itsm_tables(myTimer: func.TimerRequest) -> None:
    logging.info("Iniciando extração das tabelas ITSM")

    sql_server = _required_setting("HOST")
    sql_database = _required_setting("DATABASE")
    sql_user = _required_setting("USER")
    sql_pass = _required_setting("PASSWORD")
    datalake_connection_string = _required_setting("DATALAKE_CONNECTION_STRING")

    conn_str = _sql_connection_string(
        sql_server, sql_database, sql_user, sql_pass
    )

    datalake = DataLakeServiceClient.from_connection_string(
        datalake_connection_string
    )
    bronze = datalake.get_file_system_client("bronze")
    now = datetime.now(timezone.utc)
    failures = []

    try:
        with pyodbc.connect(conn_str) as conn:
            for table_name in ITSM_TABLES:
                try:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT * FROM [itsm].[{table_name}]")
                    rows = cursor.fetchall()
                    columns = [column[0] for column in cursor.description]

                    buffer = io.StringIO()
                    writer = csv.writer(buffer)
                    writer.writerow(columns)
                    writer.writerows(
                        [
                            (
                                CSV_NULL
                                if value is None
                                else CSV_NULL + CSV_NULL
                                if isinstance(value, str) and value == CSV_NULL
                                else value
                            )
                            for value in row
                        ]
                        for row in rows
                    )

                    file_path = (
                        f"{table_name}/{now:%Y/%m/%d}/"
                        f"{table_name}_{now:%Y%m%d_%H%M%S}.csv"
                    )
                    bronze.get_file_client(file_path).upload_data(
                        buffer.getvalue().encode("utf-8"),
                        overwrite=True,
                    )

                    logging.info(
                        "%s: %s linhas lidas; arquivo gravado em bronze/%s",
                        table_name,
                        len(rows),
                        file_path,
                    )
                except Exception:
                    logging.exception("Falha ao extrair a tabela itsm.%s", table_name)
                    failures.append(table_name)
    except Exception:
        logging.exception("Falha na conexão ou na execução das extrações ITSM")
        raise

    if failures:
        raise RuntimeError(
            "Falha na extração das tabelas: " + ", ".join(failures)
        )

    logging.info("Extração concluída para %s tabelas ITSM", len(ITSM_TABLES))


def _latest_complete_export(bronze, export_date: date) -> dict[str, str]:
    files_by_table = {}

    for table_name in ITSM_TABLES:
        prefix = f"{table_name}/{export_date:%Y/%m/%d}/"
        pattern = re.compile(
            rf"{re.escape(table_name)}_(\d{{8}}_\d{{6}})\.csv$"
        )
        files = {}
        for path in bronze.get_paths(path=prefix):
            if path.is_directory:
                continue
            match = pattern.search(path.name)
            if match:
                files[match.group(1)] = path.name
        files_by_table[table_name] = files

    common_timestamps = set.intersection(
        *(set(files) for files in files_by_table.values())
    )
    if not common_timestamps:
        missing = [
            table_name
            for table_name, files in files_by_table.items()
            if not files
        ]
        if missing:
            raise RuntimeError(
                "Não foram encontrados CSVs de hoje para: "
                + ", ".join(missing)
            )
        raise RuntimeError(
            "Os CSVs encontrados não pertencem à mesma extração diária."
        )

    latest_timestamp = max(common_timestamps)
    return {
        table_name: files[latest_timestamp]
        for table_name, files in files_by_table.items()
    }


def _target_columns(cursor, table_name: str) -> dict[str, tuple[str, bool, bool]]:
    cursor.execute(
        """
        SELECT c.name, TYPE_NAME(c.user_type_id), c.is_nullable, c.is_identity
        FROM sys.columns AS c
        JOIN sys.tables AS t ON t.object_id = c.object_id
        JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE s.name = ? AND t.name = ?
        ORDER BY c.column_id
        """,
        "itsm",
        table_name,
    )
    return {
        name: (data_type.lower(), bool(is_nullable), bool(is_identity))
        for name, data_type, is_nullable, is_identity in cursor.fetchall()
    }


def _convert_csv_value(
    value: str, data_type: str, is_nullable: bool
):
    if value == CSV_NULL:
        return None
    if value == CSV_NULL + CSV_NULL:
        return CSV_NULL
    if value == "":
        return None if is_nullable else ""

    if data_type in {"int", "bigint", "smallint", "tinyint"}:
        return int(value)
    if data_type == "bit":
        normalized = value.casefold()
        if normalized in {"true", "1"}:
            return True
        if normalized in {"false", "0"}:
            return False
        raise ValueError(f"Valor BIT inválido: {value!r}")
    if data_type in {"decimal", "numeric", "money", "smallmoney"}:
        return Decimal(value)
    if data_type in {"float", "real"}:
        return float(value)
    if data_type in {"datetime", "datetime2", "smalldatetime"}:
        return datetime.fromisoformat(value)
    if data_type == "date":
        return date.fromisoformat(value)
    if data_type == "time":
        return time.fromisoformat(value)
    if data_type in {
        "char",
        "nchar",
        "varchar",
        "nvarchar",
        "text",
        "ntext",
    }:
        return value

    raise RuntimeError(f"Tipo SQL não suportado na carga: {data_type}")


def _read_export_rows(file_client, columns: dict[str, tuple[str, bool, bool]]):
    content = file_client.download_file().readall().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content, newline=""))
    try:
        headers = next(reader)
    except StopIteration as exc:
        raise RuntimeError("Arquivo CSV vazio, sem cabeçalho.") from exc

    if len(headers) != len(set(headers)):
        raise RuntimeError("O CSV contém nomes de coluna repetidos.")
    if set(headers) != set(columns):
        raise RuntimeError(
            "Colunas do CSV incompatíveis com o destino. "
            f"CSV={headers}; destino={list(columns)}"
        )

    header_indexes = {name: index for index, name in enumerate(headers)}
    for row_number, row in enumerate(reader, start=2):
        if len(row) != len(headers):
            raise RuntimeError(
                f"Linha {row_number} do CSV tem {len(row)} valores; "
                f"esperados {len(headers)}."
            )
        yield tuple(
            _convert_csv_value(
                row[header_indexes[column_name]],
                columns[column_name][0],
                columns[column_name][1],
            )
            for column_name in columns
        )


def _upsert_table(cursor, table_name: str, file_client) -> int:
    target_columns = _target_columns(cursor, table_name)
    if not target_columns:
        raise RuntimeError(f"Tabela de destino itsm.{table_name} não encontrada.")

    primary_key = ITSM_PRIMARY_KEYS[table_name]
    if primary_key not in target_columns or not target_columns[primary_key][2]:
        raise RuntimeError(
            f"A coluna {primary_key} de itsm.{table_name} não é IDENTITY "
            "como esperado."
        )

    column_names = list(target_columns)
    quoted_columns = ", ".join(f"[{column}]" for column in column_names)
    source_columns = ", ".join(f"src.[{column}]" for column in column_names)
    alias_columns = ", ".join(f"[{column}]" for column in column_names)
    update_columns = [column for column in column_names if column != primary_key]
    update_set = ", ".join(
        f"dest.[{column}] = src.[{column}]" for column in update_columns
    )
    row_capacity = max(1, min(500, 1800 // len(column_names)))
    rows = []
    processed = 0

    def persist_batch(batch):
        if not batch:
            return
        values_clause = ", ".join(
            "(" + ", ".join("?" for _ in column_names) + ")"
            for _ in batch
        )
        parameters = [value for row in batch for value in row]
        source = f"(VALUES {values_clause}) AS src ({alias_columns})"
        table = f"[itsm].[{table_name}]"

        cursor.execute(
            f"""
            UPDATE dest
            SET {update_set}
            FROM {table} AS dest
            JOIN {source} ON dest.[{primary_key}] = src.[{primary_key}]
            """,
            parameters,
        )
        cursor.execute(
            f"""
            INSERT INTO {table} ({quoted_columns})
            SELECT {source_columns}
            FROM {source}
            WHERE NOT EXISTS (
                SELECT 1
                FROM {table} AS dest
                WHERE dest.[{primary_key}] = src.[{primary_key}]
            )
            """,
            parameters,
        )

    cursor.execute(f"SET IDENTITY_INSERT [itsm].[{table_name}] ON")
    for row in _read_export_rows(file_client, target_columns):
        rows.append(row)
        processed += 1
        if len(rows) >= row_capacity:
            persist_batch(rows)
            rows.clear()
    persist_batch(rows)
    cursor.execute(f"SET IDENTITY_INSERT [itsm].[{table_name}] OFF")
    return processed


@app.timer_trigger(
    schedule="0 0 5 * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=True,
)
def load_itsm_tables(myTimer: func.TimerRequest) -> None:
    logging.info("Iniciando carga diária das tabelas ITSM")

    datalake_connection_string = _required_setting("DATALAKE_CONNECTION_STRING")
    dest_conn_str = _sql_connection_string(
        _required_setting("DEST_HOST"),
        _required_setting("DEST_DATABASE"),
        _required_setting("DEST_USER"),
        _required_setting("DEST_PASSWORD"),
    )
    bronze = DataLakeServiceClient.from_connection_string(
        datalake_connection_string
    ).get_file_system_client("bronze")
    exports = _latest_complete_export(bronze, datetime.now(timezone.utc).date())
    connection = pyodbc.connect(dest_conn_str)

    try:
        cursor = connection.cursor()
        for table_name in ITSM_LOAD_ORDER:
            try:
                count = _upsert_table(
                    cursor,
                    table_name,
                    bronze.get_file_client(exports[table_name]),
                )
                logging.info(
                    "itsm.%s: %s linhas processadas do arquivo %s",
                    table_name,
                    count,
                    exports[table_name],
                )
            except Exception:
                logging.exception("Falha ao carregar itsm.%s", table_name)
                raise
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    logging.info(
        "Carga diária concluída para %s tabelas ITSM", len(ITSM_LOAD_ORDER)
    )
