from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session
from database import get_db
from middlewares.auth_middleware import is_cookie_secure, require_auth
import models
import schemas
from services import auth_service
from services.errors import AppError
from services.rate_limit_service import login_rate_limiter

router = APIRouter(
    prefix="/api/auth",
    tags=["Autenticación"],
)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=schemas.LoginResponse)
def login(
    payload: schemas.LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    allowed, retry_after = login_rate_limiter.check_and_record(_client_ip(request))
    if not allowed:
        raise AppError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "LIMITE_EXCEDIDO",
            "Demasiados intentos de inicio de sesión. Intente nuevamente más tarde.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        usuario, sesion = auth_service.login(db, payload.nombre, payload.password)
    except auth_service.AuthenticationError as exc:
        raise AppError(
            status.HTTP_401_UNAUTHORIZED,
            "CREDENCIALES_INVALIDAS",
            str(exc),
        ) from exc
    except auth_service.InactiveUserError as exc:
        raise AppError(
            status.HTTP_403_FORBIDDEN,
            "USUARIO_INACTIVO",
            str(exc),
        ) from exc

    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=sesion.id,
        max_age=auth_service.get_session_ttl_seconds(),
        httponly=True,
        samesite="strict",
        secure=is_cookie_secure(request),
        path="/",
    )
    return schemas.LoginResponse(usuario=usuario, expira=sesion.expira)


@router.post("/logout", response_model=schemas.MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    session_id = request.cookies.get(auth_service.SESSION_COOKIE_NAME)
    auth_service.logout(db, session_id)
    response.delete_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=is_cookie_secure(request),
    )
    return schemas.MessageResponse(detail="Sesión cerrada")


@router.get("/me", response_model=schemas.MeResponse)
def me(
    request: Request,
    usuario: models.Usuario = Depends(require_auth),
):
    sesion = getattr(request.state, "sesion", None)
    return schemas.MeResponse(
        id=usuario.id,
        nombre=usuario.nombre,
        rol=usuario.rol,
        activo=usuario.activo,
        expira=sesion.expira if sesion else None,
    )


@router.post("/cambiar-password", response_model=schemas.MessageResponse)
def cambiar_password(
    payload: schemas.CambiarPasswordRequest,
    request: Request,
    usuario: models.Usuario = Depends(require_auth),
    db: Session = Depends(get_db),
):
    sesion = getattr(request.state, "sesion", None)
    try:
        auth_service.cambiar_password(
            db=db,
            usuario=usuario,
            password_actual=payload.password_actual,
            password_nueva=payload.password_nueva,
            current_session_id=sesion.id if sesion else None,
        )
    except auth_service.InvalidPasswordError as exc:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "PASSWORD_INCORRECTA",
            str(exc),
        ) from exc

    return schemas.MessageResponse(detail="Contraseña actualizada correctamente")
