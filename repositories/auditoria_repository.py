from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import models


def create(
    db: Session,
    quien: str,
    accion: str,
    entidad: str,
    entidad_id: Optional[str] = None,
    antes: Optional[str] = None,
    despues: Optional[str] = None,
) -> models.Auditoria:
    evento = models.Auditoria(
        quien=quien,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        antes=antes,
        despues=despues,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento


def list_paginated(
    db: Session,
    page: int = 1,
    limit: int = 50,
    entidad: Optional[str] = None,
    accion: Optional[str] = None,
) -> tuple[list[models.Auditoria], int]:
    filters = []
    if entidad:
        filters.append(models.Auditoria.entidad == entidad.strip())
    if accion:
        filters.append(models.Auditoria.accion == accion.strip().upper())

    total = db.query(func.count(models.Auditoria.id)).filter(*filters).scalar() or 0
    offset = (page - 1) * limit
    items = (
        db.query(models.Auditoria)
        .filter(*filters)
        .order_by(models.Auditoria.fecha.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, int(total)
