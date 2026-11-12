from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
import models


def create(
    db: Session,
    sesion_id: str,
    usuario_id: str,
    expira: datetime,
) -> models.Sesion:
    sesion = models.Sesion(
        id=sesion_id,
        usuario_id=usuario_id,
        expira=expira,
    )
    db.add(sesion)
    db.commit()
    db.refresh(sesion)
    return sesion


def get_by_id(db: Session, sesion_id: str) -> Optional[models.Sesion]:
    return db.query(models.Sesion).filter(models.Sesion.id == sesion_id).first()


def delete_by_id(db: Session, sesion_id: str) -> bool:
    deleted = db.query(models.Sesion).filter(models.Sesion.id == sesion_id).delete()
    db.commit()
    return deleted > 0


def delete_other_user_sessions(
    db: Session,
    usuario_id: str,
    keep_sesion_id: Optional[str] = None,
) -> int:
    query = db.query(models.Sesion).filter(models.Sesion.usuario_id == usuario_id)
    if keep_sesion_id:
        query = query.filter(models.Sesion.id != keep_sesion_id)
    deleted = query.delete(synchronize_session=False)
    db.commit()
    return deleted


def delete_expired(db: Session, now: datetime) -> int:
    deleted = db.query(models.Sesion).filter(models.Sesion.expira <= now).delete()
    db.commit()
    return deleted
