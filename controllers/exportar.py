from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from middlewares.auth_middleware import require_roles
import models
import schemas
from services import export_service

router = APIRouter(
    prefix="/api/exportar",
    tags=["Exportación"],
)


@router.get(
    "/anios",
    response_model=schemas.AniosDisponiblesResponse,
    summary="Listar años con registros activos/históricos disponibles para exportar (solo admin)",
)
def listar_anios_exportables(
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    return {"anios": export_service.listar_anios_con_registros(db)}


@router.get(
    "",
    summary="Exportar registros en XLSX o PDF por streaming (solo admin)",
    responses={
        200: {
            "description": "Archivo binario en streaming (XLSX o PDF)",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {},
                "application/pdf": {},
            },
        }
    },
)
def exportar_registros(
    formato: Optional[str] = Query(default=None, description="xlsx | pdf"),
    tipo: Optional[str] = Query(default=None, description="dias | semanas | mes | anio"),
    desde: Optional[str] = Query(default=None, description="Fecha inicial YYYY-MM-DD"),
    hasta: Optional[str] = Query(default=None, description="Fecha final YYYY-MM-DD"),
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    stream_iter, media_type, filename = export_service.generar_exportacion(
        db=db,
        formato=formato,
        tipo=tipo,
        desde=desde,
        hasta=hasta,
        actor=actor,
    )
    return StreamingResponse(
        stream_iter,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
