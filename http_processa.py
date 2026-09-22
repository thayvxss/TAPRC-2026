import azure.functions as func
import logging

bp = func.Blueprint()


@bp.route(route="http_processa", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def http_processa(req: func.HttpRequest) -> func.HttpResponse:
    valor = req.params.get("valor", "sem-valor")
    resposta = f"[http_processa respondeu] Valor recebido -> {valor}"
    logging.info(f"[http_processa] {resposta}")
    return func.HttpResponse(resposta)