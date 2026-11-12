from sqlalchemy.orm import Session
from repositories import usuario_repository
from services.auth_service import hash_password

DEFAULT_USERS = (
    ("Admin", "admin", "admin"),
    ("Cajero", "123456", "cajero"),
)


def seed_usuarios(db: Session) -> list[str]:
    created: list[str] = []
    for nombre, raw_password, rol in DEFAULT_USERS:
        existing = usuario_repository.get_by_nombre(db, nombre)
        if existing is None:
            usuario_repository.create(
                db=db,
                nombre=nombre,
                password_hash=hash_password(raw_password),
                rol=rol,
                activo=True,
            )
            created.append(nombre)
    return created
