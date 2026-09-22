import azure.functions as func
import logging

bp = func.Blueprint()


@bp.route(route="http_echo", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def http_echo(req: func.HttpRequest) -> func.HttpResponse:
    parametro = req.params.get("nome")
    logging.info(f"[http_echo] Parâmetro recebido via GET: {parametro}")

    if not parametro:
        return func.HttpResponse(
            "Envie o parâmetro 'nome' na URL. Ex: ?nome=Thays",
            status_code=400,
        )

    return func.HttpResponse(f"Parâmetro recebido: {parametro}")