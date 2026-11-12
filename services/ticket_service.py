from datetime import datetime
import math
from typing import Any, Optional
from sqlalchemy.orm import Session
import models
from repositories import ticket_repository, tipo_repository
import schemas
from services import auditoria_service
from services.errors import AppError


def _ticket_snapshot(ticket: models.Ticket) -> dict[str, Any]:
    return {
        "id": ticket.id,
        "placa": ticket.placa,
        "nombre_parqueadero": ticket.nombre_parqueadero,
        "id_tipo_vehiculo": ticket.id_tipo_vehiculo,
        "fecha_ingreso": ticket.fecha_ingreso,
        "fecha_salida": ticket.fecha_salida,
        "total_horas": ticket.total_horas,
        "precio_total": ticket.precio_total,
        "precio_calculado": ticket.precio_calculado,
        "precio_final": ticket.precio_final,
        "motivo_ajuste": ticket.motivo_ajuste,
        "eliminado": ticket.eliminado,
        "estado": ticket.estado,
    }


def calcular_tarifa(
    fecha_ingreso: datetime,
    fecha_salida: datetime,
    tipo_vehiculo: models.TipoVehiculo,
) -> tuple[float, float]:
    delta = fecha_salida - fecha_ingreso
    horas_exactas = delta.total_seconds() / 3600.0
    total_horas = math.ceil(horas_exactas) if horas_exactas > 0 else 1.0

    if total_horas < 12:
        precio_calculado = total_horas * tipo_vehiculo.tarifa_hora
    elif 12 <= total_horas < 24:
        precio_calculado = tipo_vehiculo.tarifa_dia
    else:
        dias = math.ceil(total_horas / 24.0)
        precio_calculado = dias * tipo_vehiculo.tarifa_dia

    return total_horas, precio_calculado


def _resolve_ticket_por_identificador(
    db: Session, identificador: str
) -> models.Ticket:
    db_ticket = ticket_repository.get_by_id(db, identificador, include_deleted=False)
    if not db_ticket:
        db_ticket = ticket_repository.get_active_by_placa(db, identificador)
    if not db_ticket:
        raise AppError(
            404, "TICKET_NO_ENCONTRADO", "Ticket o placa activa no encontrados"
        )
    return db_ticket


def registrar_ingreso(
    db: Session,
    ticket_in: schemas.TicketCreate,
    actor: models.Usuario,
) -> models.Ticket:
    tipo_vehiculo = tipo_repository.get_by_id(db, ticket_in.id_tipo_vehiculo)
    if not tipo_vehiculo:
        raise AppError(404, "TIPO_NO_ENCONTRADO", "Tipo de vehículo no encontrado")

    db_ticket = ticket_repository.create(
        db=db,
        placa=ticket_in.placa,
        nombre_parqueadero=ticket_in.nombre_parqueadero or "PARQUEADERO BAHONDO",
        id_tipo_vehiculo=ticket_in.id_tipo_vehiculo,
    )
    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="CREAR",
        entidad="ticket",
        entidad_id=db_ticket.id,
        despues=_ticket_snapshot(db_ticket),
    )
    return db_ticket


def pre_salida(db: Session, identificador: str) -> dict[str, Any]:
    db_ticket = _resolve_ticket_por_identificador(db, identificador)
    if db_ticket.fecha_salida is not None:
        raise AppError(
            400, "TICKET_YA_FINALIZADO", "El ticket ya tiene registrada una salida"
        )

    tipo_vehiculo = tipo_repository.get_by_id(db, db_ticket.id_tipo_vehiculo)
    total_horas, precio_calculado = calcular_tarifa(
        db_ticket.fecha_ingreso, datetime.now(), tipo_vehiculo
    )
    return {
        "id": db_ticket.id,
        "placa": db_ticket.placa,
        "total_horas": total_horas,
        "precio_total": precio_calculado,
        "precio_calculado": precio_calculado,
    }


def registrar_salida(
    db: Session,
    identificador: str,
    payload: Optional[schemas.TicketSalida],
    actor: models.Usuario,
) -> models.Ticket:
    db_ticket = _resolve_ticket_por_identificador(db, identificador)
    if db_ticket.fecha_salida is not None:
        raise AppError(
            400, "TICKET_YA_FINALIZADO", "El ticket ya tiene registrada una salida"
        )

    antes = _ticket_snapshot(db_ticket)
    fecha_salida = datetime.now()
    tipo_vehiculo = tipo_repository.get_by_id(db, db_ticket.id_tipo_vehiculo)
    total_horas, precio_calculado = calcular_tarifa(
        db_ticket.fecha_ingreso, fecha_salida, tipo_vehiculo
    )

    db_ticket.fecha_salida = fecha_salida
    db_ticket.total_horas = total_horas
    db_ticket.precio_calculado = precio_calculado

    if payload and payload.precio_personalizado is not None:
        motivo = (payload.motivo_ajuste or "").strip()
        if not motivo:
            raise AppError(
                400,
                "MOTIVO_REQUERIDO",
                "Debe indicar un motivo para ajustar el precio final",
            )
        db_ticket.precio_final = payload.precio_personalizado
        # Mantener precio_total sincronizado con precio_final preserva static/ticket.html sin cambios.
        db_ticket.precio_total = payload.precio_personalizado
        db_ticket.motivo_ajuste = motivo
        accion = "AJUSTE_PRECIO"
    else:
        db_ticket.precio_final = precio_calculado
        db_ticket.precio_total = precio_calculado
        db_ticket.motivo_ajuste = None
        accion = "SALIDA"

    db_ticket.estado = "FINALIZADO"
    saved = ticket_repository.save(db, db_ticket)

    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion=accion,
        entidad="ticket",
        entidad_id=saved.id,
        antes=antes,
        despues=_ticket_snapshot(saved),
    )
    return saved


def editar_precio_final(
    db: Session,
    id_ticket: str,
    payload: schemas.TicketEditarPrecio,
    actor: models.Usuario,
) -> models.Ticket:
    db_ticket = ticket_repository.get_by_id(db, id_ticket, include_deleted=False)
    if not db_ticket:
        raise AppError(404, "TICKET_NO_ENCONTRADO", "Ticket no encontrado")

    if db_ticket.fecha_salida is None:
        raise AppError(
            400,
            "TICKET_ACTIVO",
            "No se puede editar el precio final antes de registrar la salida",
        )

    motivo = payload.motivo_ajuste.strip()
    if not motivo:
        raise AppError(
            400,
            "MOTIVO_REQUERIDO",
            "Debe indicar un motivo para ajustar el precio final",
        )

    antes = _ticket_snapshot(db_ticket)
    if db_ticket.precio_calculado is None:
        db_ticket.precio_calculado = db_ticket.precio_total

    db_ticket.precio_final = payload.precio_final
    db_ticket.precio_total = payload.precio_final
    db_ticket.motivo_ajuste = motivo

    saved = ticket_repository.save(db, db_ticket)
    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="AJUSTE_PRECIO",
        entidad="ticket",
        entidad_id=saved.id,
        antes=antes,
        despues=_ticket_snapshot(saved),
    )
    return saved


def editar_ticket_admin(
    db: Session,
    id_ticket: str,
    payload: schemas.TicketUpdateAdmin,
    actor: models.Usuario,
) -> models.Ticket:
    db_ticket = ticket_repository.get_by_id(db, id_ticket, include_deleted=False)
    if not db_ticket:
        raise AppError(404, "TICKET_NO_ENCONTRADO", "Ticket no encontrado")

    antes = _ticket_snapshot(db_ticket)

    if payload.id_tipo_vehiculo is not None:
        tipo_vehiculo = tipo_repository.get_by_id(db, payload.id_tipo_vehiculo)
        if not tipo_vehiculo:
            raise AppError(404, "TIPO_NO_ENCONTRADO", "Tipo de vehículo no encontrado")
        db_ticket.id_tipo_vehiculo = payload.id_tipo_vehiculo

    if payload.placa is not None:
        db_ticket.placa = payload.placa.upper()

    if payload.nombre_parqueadero is not None:
        db_ticket.nombre_parqueadero = payload.nombre_parqueadero.strip()

    if payload.precio_final is not None:
        if db_ticket.fecha_salida is None:
            raise AppError(
                400,
                "TICKET_ACTIVO",
                "No se puede editar el precio final antes de registrar la salida",
            )
        motivo = (payload.motivo_ajuste or "").strip()
        if not motivo:
            raise AppError(
                400,
                "MOTIVO_REQUERIDO",
                "Debe indicar un motivo para ajustar el precio final",
            )
        if db_ticket.precio_calculado is None:
            db_ticket.precio_calculado = db_ticket.precio_total
        db_ticket.precio_final = payload.precio_final
        db_ticket.precio_total = payload.precio_final
        db_ticket.motivo_ajuste = motivo
    elif payload.motivo_ajuste is not None:
        db_ticket.motivo_ajuste = payload.motivo_ajuste.strip() or None

    saved = ticket_repository.save(db, db_ticket)
    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="EDITAR",
        entidad="ticket",
        entidad_id=saved.id,
        antes=antes,
        despues=_ticket_snapshot(saved),
    )
    return saved


def eliminar_ticket(
    db: Session,
    id_ticket: str,
    actor: models.Usuario,
) -> None:
    db_ticket = ticket_repository.get_by_id(db, id_ticket, include_deleted=False)
    if not db_ticket:
        raise AppError(404, "TICKET_NO_ENCONTRADO", "Ticket no encontrado")

    antes = _ticket_snapshot(db_ticket)
    db_ticket.eliminado = True
    db_ticket.estado = "ELIMINADO"
    saved = ticket_repository.save(db, db_ticket)

    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="BORRADO_LOGICO",
        entidad="ticket",
        entidad_id=saved.id,
        antes=antes,
        despues=_ticket_snapshot(saved),
    )


def listar_tickets(db: Session) -> list[models.Ticket]:
    return ticket_repository.list_active_history(db)


def obtener_ticket(db: Session, id_ticket: str) -> models.Ticket:
    db_ticket = ticket_repository.get_by_id(db, id_ticket, include_deleted=False)
    if not db_ticket:
        raise AppError(404, "TICKET_NO_ENCONTRADO", "Ticket no encontrado")
    return db_ticket


def listar_registros_paginados(
    db: Session,
    page: int = 1,
    limit: int = 50,
    estado: Optional[str] = None,
    placa: Optional[str] = None,
) -> dict[str, Any]:
    normalized_page = max(1, page)
    normalized_limit = min(100, max(1, limit))
    normalized_estado = estado.strip().upper() if estado and estado.strip() else None
    normalized_placa = placa.strip().upper() if placa and placa.strip() else None

    items, total = ticket_repository.list_paginated(
        db=db,
        page=normalized_page,
        limit=normalized_limit,
        estado=normalized_estado,
        placa=normalized_placa,
    )
    total_pages = math.ceil(total / normalized_limit) if total > 0 else 0
    return {
        "data": items,
        "page": normalized_page,
        "limit": normalized_limit,
        "total": total,
        "totalPages": total_pages,
    }
