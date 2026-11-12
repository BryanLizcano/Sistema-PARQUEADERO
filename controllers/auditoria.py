from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from controllers.registros import parse_int_query
from database import get_db
from middlewares.auth_middleware import require_roles
import schemas
from services import auditoria_service

router = APIRouter(
    prefix="/api/auditoria",
    tags=["Auditoría"],
)


@router.get(
    "",
    response_model=schemas.AuditoriaPaginadaResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def listar_auditoria(
    page: Optional[str] = Query(default=None),
    limit: Optional[str] = Query(default="50"),
    entidad: Optional[str] = Query(default=None),
    accion: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    parsed_page = parse_int_query(page, 1, "page")
    parsed_limit = parse_int_query(limit, 50, "limit")
    return auditoria_service.listar_auditoria(
        db=db,
        page=parsed_page,
        limit=parsed_limit,
        entidad=entidad,
        accion=accion,
    )
