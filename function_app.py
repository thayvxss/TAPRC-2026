import csv
import io
import logging
import os
from datetime import datetime, timezone

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


def _required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Configuração obrigatória ausente: {name}")
    return value


@app.timer_trigger(
    schedule="0 * * * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False,
)
def extract_itsm_tables(myTimer: func.TimerRequest) -> None:
    logging.info("Iniciando extração das tabelas ITSM")

    sql_server = _required_setting("HOST")
    sql_database = _required_setting("DATABASE")
    sql_user = _required_setting("USER")
    sql_pass = _required_setting("PASSWORD")
    datalake_connection_string = _required_setting("DATALAKE_CONNECTION_STRING")

    conn_str = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={sql_server};"
        f"DATABASE={sql_database};"
        f"UID={sql_user};"
        f"PWD={sql_pass};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
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
                    writer.writerows(rows)

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
