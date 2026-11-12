from datetime import datetime
from typing import Iterator, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
import models


def get_by_id(
    db: Session,
    id_ticket: str,
    include_deleted: bool = False,
) -> Optional[models.Ticket]:
    query = db.query(models.Ticket).filter(models.Ticket.id == id_ticket)
    if not include_deleted:
        query = query.filter(models.Ticket.eliminado == False)
    return query.first()


def get_active_by_placa(db: Session, placa: str) -> Optional[models.Ticket]:
    return (
        db.query(models.Ticket)
        .filter(
            models.Ticket.placa == placa.upper(),
            models.Ticket.eliminado == False,
            models.Ticket.fecha_salida == None,
        )
        .first()
    )


def list_active_history(db: Session) -> list[models.Ticket]:
    return (
        db.query(models.Ticket)
        .filter(models.Ticket.eliminado == False)
        .order_by(models.Ticket.fecha_ingreso.desc())
        .all()
    )


def list_paginated(
    db: Session,
    page: int,
    limit: int,
    estado: Optional[str] = None,
    placa: Optional[str] = None,
) -> tuple[list[models.Ticket], int]:
    filters = [models.Ticket.eliminado == False]

    if estado:
        filters.append(models.Ticket.estado == estado.strip().upper())

    if placa:
        prefix = placa.strip().upper()
        if prefix:
            # Rango de prefijo permite usar ix_tickets_placa en SQLite sin table scan de LIKE '%...%'.
            if ord(prefix[-1]) < 0x10FFFF:
                next_prefix = prefix[:-1] + chr(ord(prefix[-1]) + 1)
                filters.append(models.Ticket.placa >= prefix)
                filters.append(models.Ticket.placa < next_prefix)
            else:
                filters.append(models.Ticket.placa >= prefix)

    total = (
        db.query(func.count(models.Ticket.id))
        .filter(*filters)
        .scalar()
        or 0
    )

    offset = (page - 1) * limit
    items = (
        db.query(models.Ticket)
        .filter(*filters)
        .order_by(models.Ticket.fecha_ingreso.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, int(total)


def create(
    db: Session,
    placa: str,
    nombre_parqueadero: str,
    id_tipo_vehiculo: str,
) -> models.Ticket:
    db_ticket = models.Ticket(
        placa=placa.upper(),
        nombre_parqueadero=nombre_parqueadero,
        id_tipo_vehiculo=id_tipo_vehiculo,
        eliminado=False,
        estado="ACTIVO",
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def save(db: Session, db_ticket: models.Ticket) -> models.Ticket:
    db.commit()
    db.refresh(db_ticket)
    return db_ticket


def iter_tickets_for_export(
    db: Session,
    fecha_desde: datetime,
    fecha_hasta: datetime,
    batch_size: int = 200,
) -> Iterator[models.Ticket]:
    return (
        db.query(models.Ticket)
        .filter(
            models.Ticket.eliminado == False,
            models.Ticket.fecha_ingreso >= fecha_desde,
            models.Ticket.fecha_ingreso <= fecha_hasta,
        )
        .order_by(models.Ticket.fecha_ingreso.asc())
        .yield_per(batch_size)
    )


def list_distinct_years(db: Session) -> list[int]:
    year_expr = func.strftime("%Y", models.Ticket.fecha_ingreso)
    rows = (
        db.query(year_expr)
        .filter(models.Ticket.eliminado == False)
        .distinct()
        .order_by(year_expr.desc())
        .all()
    )
    years: list[int] = []
    for (raw_year,) in rows:
        if raw_year is not None:
            try:
                years.append(int(raw_year))
            except (TypeError, ValueError):
                continue
    return years
