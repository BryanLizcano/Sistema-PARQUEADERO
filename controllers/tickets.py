from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from middlewares.auth_middleware import require_roles
import models
import schemas
from services import ticket_service

router = APIRouter(
    prefix="/ticket",
    tags=["Tickets"],
)


@router.post("/ingreso", response_model=schemas.Ticket, status_code=201)
def registrar_ingreso(
    ticket_in: schemas.TicketCreate,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin", "cajero")),
):
    return ticket_service.registrar_ingreso(db, ticket_in, actor)


@router.get(
    "/pre-salida/{identificador}",
    dependencies=[Depends(require_roles("admin", "cajero"))],
)
def pre_salida_ticket(identificador: str, db: Session = Depends(get_db)):
    return ticket_service.pre_salida(db, identificador)


@router.put("/salida/{identificador}", response_model=schemas.Ticket)
def registrar_salida(
    identificador: str,
    payload: Optional[schemas.TicketSalida] = None,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin", "cajero")),
):
    return ticket_service.registrar_salida(db, identificador, payload, actor)


@router.patch("/{id_ticket}/precio", response_model=schemas.Ticket)
@router.put("/{id_ticket}/precio", response_model=schemas.Ticket)
def editar_precio_ticket(
    id_ticket: str,
    payload: schemas.TicketEditarPrecio,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin", "cajero")),
):
    return ticket_service.editar_precio_final(db, id_ticket, payload, actor)


@router.put("/{id_ticket}", response_model=schemas.Ticket)
def editar_ticket(
    id_ticket: str,
    payload: schemas.TicketUpdateAdmin,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    return ticket_service.editar_ticket_admin(db, id_ticket, payload, actor)


@router.get(
    "",
    response_model=List[schemas.Ticket],
    dependencies=[Depends(require_roles("admin", "cajero"))],
)
def listar_tickets(db: Session = Depends(get_db)):
    return ticket_service.listar_tickets(db)


@router.get(
    "/{id_ticket}",
    response_model=schemas.Ticket,
    dependencies=[Depends(require_roles("admin", "cajero"))],
)
def obtener_ticket(id_ticket: str, db: Session = Depends(get_db)):
    return ticket_service.obtener_ticket(db, id_ticket)


@router.delete("/{id_ticket}", status_code=204)
def eliminar_ticket(
    id_ticket: str,
    db: Session = Depends(get_db),
    actor: models.Usuario = Depends(require_roles("admin")),
):
    ticket_service.eliminar_ticket(db, id_ticket, actor)
    return None
