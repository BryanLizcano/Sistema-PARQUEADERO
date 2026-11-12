from http.cookies import SimpleCookie
import os
from typing import Callable, Optional
from fastapi import Depends, Request, status
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send
from database import get_db
import models
from repositories import usuario_repository
from services import auth_service
from services.errors import AppError


def is_cookie_secure(request: Request) -> bool:
    explicit = os.getenv("COOKIE_SECURE", "").strip().lower()
    if explicit in {"1", "true", "yes"}:
        return True
    if explicit in {"0", "false", "no"}:
        return False
    env = os.getenv("APP_ENV", os.getenv("ENV", "development")).strip().lower()
    if env in {"prod", "production"}:
        return True
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    return request.url.scheme == "https" or proto == "https"


def _extract_cookie(headers: Headers, cookie_name: str) -> Optional[str]:
    raw_cookie = headers.get("cookie")
    if not raw_cookie:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw_cookie)
    except Exception:
        return None
    morsel = cookie.get(cookie_name)
    return morsel.value if morsel else None


class AuthContextMiddleware:
    """Resuelve la sesión de cookie httpOnly en request.state respetando dependency_overrides."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["usuario"] = None
        state["sesion"] = None
        state["auth_checked"] = True

        headers = Headers(scope=scope)
        session_id = _extract_cookie(headers, auth_service.SESSION_COOKIE_NAME)
        if session_id:
            fastapi_app = scope.get("app")
            overrides = getattr(fastapi_app, "dependency_overrides", {})
            db_provider = overrides.get(get_db, get_db)
            gen = db_provider()
            db = next(gen)
            try:
                resolved = auth_service.get_authenticated_session(db, session_id)
                if resolved is not None:
                    usuario, sesion = resolved
                    # Expunge evita DetachedInstanceError al leer atributos fuera de esta sesión.
                    db.expunge(usuario)
                    db.expunge(sesion)
                    state["usuario"] = usuario
                    state["sesion"] = sesion
            finally:
                try:
                    next(gen)
                except StopIteration:
                    pass

        await self.app(scope, receive, send)


def require_auth(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    state_user: Optional[models.Usuario] = getattr(request.state, "usuario", None)
    if state_user is not None:
        usuario = usuario_repository.get_by_id(db, state_user.id)
        if usuario and usuario.activo:
            return usuario

    if not getattr(request.state, "auth_checked", False):
        session_id = request.cookies.get(auth_service.SESSION_COOKIE_NAME)
        resolved = auth_service.get_authenticated_session(db, session_id)
        if resolved is not None:
            usuario, sesion = resolved
            request.state.usuario = usuario
            request.state.sesion = sesion
            return usuario

    raise AppError(
        status.HTTP_401_UNAUTHORIZED,
        "NO_AUTENTICADO",
        "No autenticado o sesión expirada",
    )


def require_roles(*roles: str) -> Callable[..., models.Usuario]:
    allowed_roles = set(roles)

    def _authorize_role(
        usuario: models.Usuario = Depends(require_auth),
    ) -> models.Usuario:
        if usuario.rol not in allowed_roles:
            raise AppError(
                status.HTTP_403_FORBIDDEN,
                "PROHIBIDO",
                "No tiene permisos suficientes para realizar esta acción",
            )
        return usuario

    return _authorize_role
