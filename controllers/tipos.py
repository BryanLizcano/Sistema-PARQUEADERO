from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from middlewares.auth_middleware import require_roles
import models
import schemas
from services import tipo_service

router = APIRouter(
    prefix="/tipos-vehiculo",
    tags=["Tipos de Vehículo"],
)


@router.post("", response_model=schemas.TipoVehiculo, status_code=201)
def crear_tipo_vehiculo(
    tipo: schemas.TipoVehiculoCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    return tipo_service.crear_tipo(db, tipo, actor)


@router.get(
    "",
    response_model=List[schemas.TipoVehiculo],
    dependencies=[Depends(require_roles("admin", "cajero"))],
)
def listar_tipos_vehiculo(db: Session = Depends(get_db)):
    return tipo_service.listar_tipos(db)


@router.put("/{id_tipo}", response_model=schemas.TipoVehiculo)
def actualizar_tipo_vehiculo(
    id_tipo: str,
    tipo: schemas.TipoVehiculoCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    return tipo_service.actualizar_tipo(db, id_tipo, tipo, actor)
