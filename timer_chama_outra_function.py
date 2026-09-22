import azure.functions as func
import logging
import os
import urllib.request
import urllib.parse

bp = func.Blueprint()


@bp.timer_trigger(
    schedule="0 */5 * * * *",
    arg_name="myTimer2",
    run_on_startup=False,
    use_monitor=False,
)
def timer_chama_outra_function(myTimer2: func.TimerRequest) -> None:
    url_base = os.environ.get(
        "URL_HTTP_PROCESSA",
        "http://localhost:7071/api/http_processa",
    )

    valor_a_enviar = "ola-da-timer"
    query = urllib.parse.urlencode({"valor": valor_a_enviar})
    url_completa = f"{url_base}?{query}"

    logging.info(f"[timer_chama_outra_function] Chamando: {url_completa}")

    try:
        with urllib.request.urlopen(url_completa, timeout=10) as resp:
            corpo = resp.read().decode("utf-8")
            logging.info(f"[timer_chama_outra_function] Resposta recebida: {corpo}")
    except Exception as e:
        logging.error(f"[timer_chama_outra_function] Erro ao chamar a function: {e}")