from typing import Optional
from sqlalchemy.orm import Session
import models


def get_by_id(db: Session, id_tipo: str) -> Optional[models.TipoVehiculo]:
    return db.query(models.TipoVehiculo).filter(models.TipoVehiculo.id == id_tipo).first()


def get_by_nombre(db: Session, nombre: str) -> Optional[models.TipoVehiculo]:
    return db.query(models.TipoVehiculo).filter(models.TipoVehiculo.nombre == nombre).first()


def list_all(db: Session) -> list[models.TipoVehiculo]:
    return db.query(models.TipoVehiculo).all()


def create(
    db: Session,
    nombre: str,
    tarifa_hora: float,
    tarifa_dia: float,
    tarifa_noche: float,
) -> models.TipoVehiculo:
    db_tipo = models.TipoVehiculo(
        nombre=nombre,
        tarifa_hora=tarifa_hora,
        tarifa_dia=tarifa_dia,
        tarifa_noche=tarifa_noche,
    )
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo


def save(db: Session, db_tipo: models.TipoVehiculo) -> models.TipoVehiculo:
    db.commit()
    db.refresh(db_tipo)
    return db_tipo
