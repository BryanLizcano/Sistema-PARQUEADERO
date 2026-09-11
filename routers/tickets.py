from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models
import schemas
from database import get_db
from datetime import datetime
import math

router = APIRouter(
    prefix="/ticket",
    tags=["Tickets"]
)

@router.post("/ingreso", response_model=schemas.Ticket, status_code=201)
def registrar_ingreso(ticket_in: schemas.TicketCreate, db: Session = Depends(get_db)):
    tipo_vehiculo = db.query(models.TipoVehiculo).filter(models.TipoVehiculo.id == ticket_in.id_tipo_vehiculo).first()
    if not tipo_vehiculo:
        raise HTTPException(status_code=404, detail="Tipo de vehículo no encontrado")
    
    db_ticket = models.Ticket(**ticket_in.model_dump())
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@router.get("/pre-salida/{identificador}")
def pre_salida_ticket(identificador: str, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == identificador).first()
    
    if not db_ticket:
        db_ticket = db.query(models.Ticket).filter(
            models.Ticket.placa == identificador.upper(),
            models.Ticket.fecha_salida == None
        ).first()

    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket o placa activa no encontrados")
        
    if db_ticket.fecha_salida is not None:
        raise HTTPException(status_code=400, detail="El ticket ya tiene registrada una salida")

    fecha_salida_simulada = datetime.now()
    delta = fecha_salida_simulada - db_ticket.fecha_ingreso
    horas_exactas = delta.total_seconds() / 3600.0
    total_horas = math.ceil(horas_exactas) if horas_exactas > 0 else 1.0
    
    tipo_vehiculo = db.query(models.TipoVehiculo).filter(models.TipoVehiculo.id == db_ticket.id_tipo_vehiculo).first()
    
    if total_horas < 12:
        precio_total = total_horas * tipo_vehiculo.tarifa_hora
    elif 12 <= total_horas < 24:
        precio_total = tipo_vehiculo.tarifa_dia
    else:
        dias = math.ceil(total_horas / 24.0)
        precio_total = dias * tipo_vehiculo.tarifa_dia

    return {
        "id": db_ticket.id,
        "placa": db_ticket.placa,
        "total_horas": total_horas,
        "precio_total": precio_total
    }

@router.put("/salida/{identificador}", response_model=schemas.Ticket)
def registrar_salida(identificador: str, payload: schemas.TicketSalida = None, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == identificador).first()
    
    # Si no lo encuentra por ID, intentar buscar por placa activa
    if not db_ticket:
        db_ticket = db.query(models.Ticket).filter(
            models.Ticket.placa == identificador.upper(),
            models.Ticket.fecha_salida == None
        ).first()

    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket o placa activa no encontrados")
        
    if db_ticket.fecha_salida is not None:
        raise HTTPException(status_code=400, detail="El ticket ya tiene registrada una salida")
        
    db_ticket.fecha_salida = datetime.now()
    
    # Calcular horas transcurridas
    delta = db_ticket.fecha_salida - db_ticket.fecha_ingreso
    horas_exactas = delta.total_seconds() / 3600.0
    db_ticket.total_horas = math.ceil(horas_exactas) if horas_exactas > 0 else 1.0
    
    tipo_vehiculo = db.query(models.TipoVehiculo).filter(models.TipoVehiculo.id == db_ticket.id_tipo_vehiculo).first()
    
    # Lógica de cálculo o valor personalizado
    if payload and payload.precio_personalizado is not None:
        db_ticket.precio_total = payload.precio_personalizado
    else:
        if db_ticket.total_horas < 12:
            db_ticket.precio_total = db_ticket.total_horas * tipo_vehiculo.tarifa_hora
        elif 12 <= db_ticket.total_horas < 24:
            db_ticket.precio_total = tipo_vehiculo.tarifa_dia
        else:
            dias = math.ceil(db_ticket.total_horas / 24.0)
            db_ticket.precio_total = dias * tipo_vehiculo.tarifa_dia
        
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@router.get("", response_model=List[schemas.Ticket])
def listar_tickets(db: Session = Depends(get_db)):
    return db.query(models.Ticket).order_by(models.Ticket.fecha_ingreso.desc()).all()

@router.get("/{id_ticket}", response_model=schemas.Ticket)
def obtener_ticket(id_ticket: str, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == id_ticket).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    return db_ticket

@router.delete("/{id_ticket}", status_code=204)
def eliminar_ticket(id_ticket: str, db: Session = Depends(get_db)):
    db_ticket = db.query(models.Ticket).filter(models.Ticket.id == id_ticket).first()
    if not db_ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    db.delete(db_ticket)
    db.commit()
    return None

