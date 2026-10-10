
import logging
import azure.functions as func
import os
import pyodbc

app = func.FunctionApp()
@app.timer_trigger(schedule="0 * * * * *", arg_name="myTimer", run_on_startup=False,
              use_monitor=False) 
def extract_chamada(myTimer: func.TimerRequest) -> None:
    
    host = os.getenv("HOST")
    database = os.getenv("DATABASE")
    user = os.getenv("USER")
    password = os.getenv("PASSWORD");;
    
    conn = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={host};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )
    
    # criar conexão com o banco
    try:
        cnxn = pyodbc.connect(conn)
        logging.info("Conexão com o banco de dados estabelecida com sucesso.")
    except Exception as e:
        logging.error(f"Erro ao conectar ao banco de dados: {e}")
        return
    
    # fazer um select na tabela analista, categoria, chamado, chamado_sla, 
    # chamado_status_historico, cliente_organizacao, csat_avaliacao, fila, 
    # sla e solicitante.
    cursor = cnxn.cursor()
    try:
        cursor.execute("SELECT * FROM itsm.analista")
        rows = cursor.fetchall()

        for row in rows:
            logging.info(f"Resultado: {row}")
            
    except Exception as e:
        logging.error(f"Erro ao executar a consulta: {e}")
        return
    finally:
        cursor.close()
        cnxn.close()
     
    