import azure.functions as func
import datetime
import logging

from http_echo import bp as http_echo_bp
from http_processa import bp as http_processa_bp
from timer_chama_outra_function import bp as timer_chama_bp

app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 */5 * * * *",
    arg_name="myTimer",
    run_on_startup=False,
    use_monitor=False,
)
def timer_log_simples(myTimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().isoformat()
    logging.info(f"[timer_log_simples] Timer trigger executado em: {utc_timestamp}")


app.register_functions(http_echo_bp)
app.register_functions(http_processa_bp)
app.register_functions(timer_chama_bp)