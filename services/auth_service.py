from datetime import timedelta
import os
import secrets
from typing import Optional
import bcrypt
from sqlalchemy.orm import Session
import models
from repositories import sesion_repository, usuario_repository
from services import auditoria_service

SESSION_COOKIE_NAME = "session_id"
DEFAULT_SESSION_TTL_SECONDS = 43200  # 12 horas para cubrir un turno completo de parqueadero

# Hash fijo para igualar tiempos cuando el usuario no existe y evitar enumeración por timing.
_DUMMY_BCRYPT_HASH = bcrypt.hashpw(b"dummy-timing-guard", bcrypt.gensalt(rounds=10)).decode("utf-8")


class AuthenticationError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class InvalidPasswordError(Exception):
    pass


def get_session_ttl_seconds() -> int:
    return int(os.getenv("SESSION_TTL_SECONDS", str(DEFAULT_SESSION_TTL_SECONDS)))


def _get_bcrypt_rounds() -> int:
    return int(os.getenv("BCRYPT_ROUNDS", "12"))


def _validate_password_bytes(password: str, field_name: str = "contraseña") -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise InvalidPasswordError(
            f"La {field_name} excede el límite máximo de 72 bytes permitido por bcrypt"
        )
    return encoded


def hash_password(password: str) -> str:
    encoded = _validate_password_bytes(password)
    salt = bcrypt.gensalt(rounds=_get_bcrypt_rounds())
    return bcrypt.hashpw(encoded, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        return False
    return bcrypt.checkpw(encoded, password_hash.encode("utf-8"))


def login(
    db: Session,
    nombre: str,
    password: str,
) -> tuple[models.Usuario, models.Sesion]:
    usuario = usuario_repository.get_by_nombre(db, nombre)
    candidate_hash = usuario.hash if usuario else _DUMMY_BCRYPT_HASH
    password_ok = verify_password(password, candidate_hash)

    if not usuario or not password_ok:
        auditoria_service.registrar_evento(
            db=db,
            quien=nombre.strip() or "desconocido",
            accion="LOGIN_FALLIDO",
            entidad="sesion",
            despues={"motivo": "credenciales_invalidas"},
        )
        raise AuthenticationError("Credenciales inválidas")

    if not usuario.activo:
        auditoria_service.registrar_evento(
            db=db,
            quien=usuario.nombre,
            accion="LOGIN_FALLIDO",
            entidad="sesion",
            entidad_id=usuario.id,
            despues={"motivo": "usuario_inactivo"},
        )
        raise InactiveUserError("Usuario desactivado")

    now = models.get_utc_now()
    sesion_repository.delete_expired(db, now)

    ttl_seconds = get_session_ttl_seconds()
    sesion_id = secrets.token_urlsafe(32)
    expira = now + timedelta(seconds=ttl_seconds)
    sesion = sesion_repository.create(db, sesion_id=sesion_id, usuario_id=usuario.id, expira=expira)

    auditoria_service.registrar_evento(
        db=db,
        quien=usuario.nombre,
        accion="LOGIN",
        entidad="sesion",
        entidad_id=sesion.id,
        despues={"rol": usuario.rol},
    )
    return usuario, sesion


def get_authenticated_session(
    db: Session,
    sesion_id: Optional[str],
) -> Optional[tuple[models.Usuario, models.Sesion]]:
    if not sesion_id:
        return None

    sesion = sesion_repository.get_by_id(db, sesion_id)
    if not sesion:
        return None

    if sesion.expira <= models.get_utc_now():
        sesion_repository.delete_by_id(db, sesion.id)
        return None

    usuario = usuario_repository.get_by_id(db, sesion.usuario_id)
    if not usuario or not usuario.activo:
        sesion_repository.delete_by_id(db, sesion.id)
        return None

    return usuario, sesion


def logout(db: Session, sesion_id: Optional[str]) -> bool:
    if not sesion_id:
        return False

    sesion = sesion_repository.get_by_id(db, sesion_id)
    if not sesion:
        return False

    usuario = usuario_repository.get_by_id(db, sesion.usuario_id)
    quien = usuario.nombre if usuario else sesion.usuario_id
    deleted = sesion_repository.delete_by_id(db, sesion.id)
    if deleted:
        auditoria_service.registrar_evento(
            db=db,
            quien=quien,
            accion="LOGOUT",
            entidad="sesion",
            entidad_id=sesion.id,
        )
    return deleted


def cambiar_password(
    db: Session,
    usuario: models.Usuario,
    password_actual: str,
    password_nueva: str,
    current_session_id: Optional[str] = None,
) -> None:
    if not verify_password(password_actual, usuario.hash):
        raise InvalidPasswordError("La contraseña actual es incorrecta")

    if len(password_nueva.strip()) < 4:
        raise InvalidPasswordError("La nueva contraseña debe tener al menos 4 caracteres")

    nuevo_hash = hash_password(password_nueva)
    usuario_repository.update_hash(db, usuario, nuevo_hash)
    sesion_repository.delete_other_user_sessions(
        db, usuario_id=usuario.id, keep_sesion_id=current_session_id
    )

    auditoria_service.registrar_evento(
        db=db,
        quien=usuario.nombre,
        accion="CAMBIO_CLAVE",
        entidad="usuario",
        entidad_id=usuario.id,
        despues={"actualizado": True},
    )
