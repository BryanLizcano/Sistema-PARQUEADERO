import json
import math
from typing import Any, Optional
from sqlalchemy.orm import Session
from repositories import auditoria_repository


def _serialize(payload: Optional[dict[str, Any]]) -> Optional[str]:
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, default=str)


def registrar_evento(
    db: Session,
    quien: str,
    accion: str,
    entidad: str,
    entidad_id: Optional[str] = None,
    antes: Optional[dict[str, Any]] = None,
    despues: Optional[dict[str, Any]] = None,
) -> None:
    auditoria_repository.create(
        db=db,
        quien=quien,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        antes=_serialize(antes),
        despues=_serialize(despues),
    )


def listar_auditoria(
    db: Session,
    page: int = 1,
    limit: int = 50,
    entidad: Optional[str] = None,
    accion: Optional[str] = None,
) -> dict[str, Any]:
    page = max(1, page)
    limit = min(100, max(1, limit))
    items, total = auditoria_repository.list_paginated(
        db=db, page=page, limit=limit, entidad=entidad, accion=accion
    )
    total_pages = math.ceil(total / limit) if total > 0 else 0
    return {
        "data": items,
        "page": page,
        "limit": limit,
        "total": total,
        "totalPages": total_pages,
    }
