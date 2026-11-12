from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from middlewares.auth_middleware import require_roles
import schemas
from services import ticket_service
from services.errors import AppError

router = APIRouter(
    prefix="/api/registros",
    tags=["Registros"],
)


def parse_int_query(raw: Optional[str], default: int, field_name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError as exc:
        raise AppError(
            400,
            "PARAMETRO_INVALIDO",
            f"El parámetro '{field_name}' debe ser un número entero",
        ) from exc


@router.get(
    "",
    response_model=schemas.RegistrosPaginadosResponse,
    dependencies=[Depends(require_roles("admin", "cajero"))],
)
def listar_registros(
    page: Optional[str] = Query(default=None),
    limit: Optional[str] = Query(default="50"),
    estado: Optional[str] = Query(default=None),
    placa: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    parsed_page = parse_int_query(page, 1, "page")
    parsed_limit = parse_int_query(limit, 50, "limit")
    return ticket_service.listar_registros_paginados(
        db=db,
        page=parsed_page,
        limit=parsed_limit,
        estado=estado,
        placa=placa,
    )
