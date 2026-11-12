from typing import Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import models
from repositories import tipo_repository
import schemas
from services import auditoria_service
from services.errors import AppError


def _tipo_snapshot(tipo: models.TipoVehiculo) -> dict[str, Any]:
    return {
        "id": tipo.id,
        "nombre": tipo.nombre,
        "tarifa_hora": tipo.tarifa_hora,
        "tarifa_dia": tipo.tarifa_dia,
        "tarifa_noche": tipo.tarifa_noche,
    }


def crear_tipo(
    db: Session,
    data: schemas.TipoVehiculoCreate,
    actor: models.Usuario,
) -> models.TipoVehiculo:
    if tipo_repository.get_by_nombre(db, data.nombre) is not None:
        raise AppError(400, "TIPO_DUPLICADO", "Ya existe un tipo de vehículo con ese nombre")

    db_tipo = tipo_repository.create(
        db=db,
        nombre=data.nombre,
        tarifa_hora=data.tarifa_hora,
        tarifa_dia=data.tarifa_dia,
        tarifa_noche=data.tarifa_noche,
    )
    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="CREAR",
        entidad="tipo_vehiculo",
        entidad_id=db_tipo.id,
        despues=_tipo_snapshot(db_tipo),
    )
    return db_tipo


def listar_tipos(db: Session) -> list[models.TipoVehiculo]:
    return tipo_repository.list_all(db)


def actualizar_tipo(
    db: Session,
    id_tipo: str,
    data: schemas.TipoVehiculoCreate,
    actor: models.Usuario,
) -> models.TipoVehiculo:
    db_tipo = tipo_repository.get_by_id(db, id_tipo)
    if not db_tipo:
        raise AppError(404, "TIPO_NO_ENCONTRADO", "Tipo de vehículo no encontrado")

    antes = _tipo_snapshot(db_tipo)
    db_tipo.nombre = data.nombre
    db_tipo.tarifa_hora = data.tarifa_hora
    db_tipo.tarifa_dia = data.tarifa_dia
    db_tipo.tarifa_noche = data.tarifa_noche

    try:
        updated = tipo_repository.save(db, db_tipo)
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            400, "TIPO_DUPLICADO", "Error al actualizar (posible nombre duplicado)"
        ) from exc

    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="EDITAR",
        entidad="tipo_vehiculo",
        entidad_id=updated.id,
        antes=antes,
        despues=_tipo_snapshot(updated),
    )
    return updated
