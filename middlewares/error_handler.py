from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from services.errors import AppError

_STATUS_CODE_MAP = {
    400: "SOLICITUD_INVALIDA",
    401: "NO_AUTENTICADO",
    403: "PROHIBIDO",
    404: "NO_ENCONTRADO",
    405: "METODO_NO_PERMITIDO",
    409: "CONFLICTO",
    422: "VALIDACION_ERROR",
    429: "LIMITE_EXCEDIDO",
    500: "ERROR_INTERNO",
}


def _error_body(codigo: str, mensaje: str) -> dict[str, dict[str, str]]:
    return {"error": {"codigo": codigo, "mensaje": mensaje}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.codigo, exc.mensaje),
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        if isinstance(exc.detail, dict) and "codigo" in exc.detail and "mensaje" in exc.detail:
            codigo = str(exc.detail["codigo"])
            mensaje = str(exc.detail["mensaje"])
        else:
            codigo = _STATUS_CODE_MAP.get(exc.status_code, f"HTTP_{exc.status_code}")
            mensaje = str(exc.detail) if exc.detail else "Error en la solicitud"
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(codigo, mensaje),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", []) if part != "body")
            msg = first.get("msg", "Datos inválidos")
            mensaje = f"{loc}: {msg}" if loc else msg
        else:
            mensaje = "Datos de entrada inválidos"
        return JSONResponse(
            status_code=422,
            content=_error_body("VALIDACION_ERROR", mensaje),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("ERROR_INTERNO", "Error interno del servidor"),
        )
