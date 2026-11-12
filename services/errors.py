from typing import Optional


class AppError(Exception):
    """Excepción de dominio con código semántico para respuestas uniformes."""

    def __init__(
        self,
        status_code: int,
        codigo: str,
        mensaje: str,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(mensaje)
        self.status_code = status_code
        self.codigo = codigo
        self.mensaje = mensaje
        self.headers = headers
