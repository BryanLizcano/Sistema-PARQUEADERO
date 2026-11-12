from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import models


def get_by_id(db: Session, usuario_id: str) -> Optional[models.Usuario]:
    return db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()


def get_by_nombre(db: Session, nombre: str) -> Optional[models.Usuario]:
    normalized = nombre.strip().lower()
    return (
        db.query(models.Usuario)
        .filter(func.lower(models.Usuario.nombre) == normalized)
        .first()
    )


def create(
    db: Session,
    nombre: str,
    password_hash: str,
    rol: str,
    activo: bool = True,
) -> models.Usuario:
    usuario = models.Usuario(
        nombre=nombre.strip(),
        hash=password_hash,
        rol=rol,
        activo=activo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def update_hash(db: Session, usuario: models.Usuario, nuevo_hash: str) -> models.Usuario:
    usuario.hash = nuevo_hash
    db.commit()
    db.refresh(usuario)
    return usuario
