from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import get_db

router = APIRouter(
    prefix="/tipos-vehiculo",
    tags=["Tipos de Vehículo"]
)

@router.post("", response_model=schemas.TipoVehiculo, status_code=201)
def crear_tipo_vehiculo(tipo: schemas.TipoVehiculoCreate, db: Session = Depends(get_db)):
    db_tipo = models.TipoVehiculo(**tipo.model_dump())
    db.add(db_tipo)
    db.commit()
    db.refresh(db_tipo)
    return db_tipo

@router.get("", response_model=List[schemas.TipoVehiculo])
def listar_tipos_vehiculo(db: Session = Depends(get_db)):
    return db.query(models.TipoVehiculo).all()

@router.put("/{id_tipo}", response_model=schemas.TipoVehiculo)
def actualizar_tipo_vehiculo(id_tipo: str, tipo: schemas.TipoVehiculoCreate, db: Session = Depends(get_db)):
    db_tipo = db.query(models.TipoVehiculo).filter(models.TipoVehiculo.id == id_tipo).first()
    if not db_tipo:
        raise HTTPException(status_code=404, detail="Tipo de vehículo no encontrado")
    
    db_tipo.nombre = tipo.nombre
    db_tipo.tarifa_hora = tipo.tarifa_hora
    db_tipo.tarifa_dia = tipo.tarifa_dia
    db_tipo.tarifa_noche = tipo.tarifa_noche
    
    try:
        db.commit()
        db.refresh(db_tipo)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Error al actualizar (posible nombre duplicado)")
    return db_tipo

