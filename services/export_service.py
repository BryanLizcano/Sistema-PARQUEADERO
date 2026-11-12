from datetime import date, datetime, time
import tempfile
from typing import Iterator, Optional
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
import xlsxwriter
import models
from repositories import ticket_repository, tipo_repository
from services import auditoria_service
from services.errors import AppError

_STREAM_CHUNK_SIZE = 65536
_SPOOL_MAX_BYTES = 512 * 1024

_MAX_DAYS_BY_TYPE = {
    "dias": (20, "Para tipo 'dias', el rango máximo permitido es de 20 días"),
    "semanas": (70, "Para tipo 'semanas', el rango máximo permitido es de 10 semanas (70 días)"),
    "mes": (31, "Para tipo 'mes', el rango máximo permitido es de 1 mes (31 días)"),
    "anio": (366, "Para tipo 'anio', el rango máximo permitido es de 1 año (366 días)"),
}


def _parse_date(raw: Optional[str], field_name: str) -> date:
    if not raw or not raw.strip():
        raise AppError(
            400,
            "RANGO_FECHAS_REQUERIDO",
            "Debe especificar las fechas 'desde' y 'hasta' en formato YYYY-MM-DD",
        )
    text = raw.strip()
    try:
        if "T" in text or " " in text:
            return datetime.fromisoformat(text).date()
        return date.fromisoformat(text)
    except ValueError as exc:
        raise AppError(
            400,
            "FECHA_INVALIDA",
            f"Formato de fecha inválido para '{field_name}'. Use YYYY-MM-DD",
        ) from exc


def validate_export_params(
    formato: Optional[str],
    tipo: Optional[str],
    desde: Optional[str],
    hasta: Optional[str],
) -> tuple[str, str, date, date]:
    fmt = (formato or "").strip().lower()
    if fmt not in {"xlsx", "pdf"}:
        raise AppError(
            400,
            "FORMATO_INVALIDO",
            "El parámetro 'formato' debe ser 'xlsx' o 'pdf'",
        )

    raw_tipo = (tipo or "").strip().lower()
    kind = "anio" if raw_tipo == "año" else raw_tipo
    if kind not in _MAX_DAYS_BY_TYPE:
        raise AppError(
            400,
            "TIPO_RANGO_INVALIDO",
            "El parámetro 'tipo' debe ser 'dias', 'semanas', 'mes' o 'anio'",
        )

    d_desde = _parse_date(desde, "desde")
    d_hasta = _parse_date(hasta, "hasta")
    if d_desde > d_hasta:
        raise AppError(
            400,
            "RANGO_INVALIDO",
            "La fecha 'desde' no puede ser posterior a 'hasta'",
        )

    dias_rango = (d_hasta - d_desde).days + 1
    max_days, error_msg = _MAX_DAYS_BY_TYPE[kind]
    if dias_rango > max_days:
        raise AppError(400, "RANGO_EXCEDIDO", error_msg)

    return fmt, kind, d_desde, d_hasta


def _format_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "-"


def _format_money(val: Optional[float]) -> str:
    return f"${val:,.0f}" if val is not None else "-"


def _effective_price(ticket: models.Ticket) -> Optional[float]:
    if ticket.precio_final is not None:
        return ticket.precio_final
    return ticket.precio_total


def _build_xlsx_spooled(
    rows: Iterator[models.Ticket],
    tipos_map: dict[str, str],
) -> tuple[tempfile.SpooledTemporaryFile, int, float]:
    tmp = tempfile.SpooledTemporaryFile(max_size=_SPOOL_MAX_BYTES)
    count = 0
    total_recaudado = 0.0

    # constant_memory=True escribe cada fila al stream sin retener la hoja completa en RAM.
    workbook = xlsxwriter.Workbook(tmp, {"constant_memory": True, "in_memory": False})
    try:
        worksheet = workbook.add_worksheet("Registros")
        bold = workbook.add_format({"bold": True})
        headers = [
            "ID",
            "Placa",
            "Tipo Vehículo",
            "Parqueadero",
            "Ingreso",
            "Salida",
            "Horas",
            "Precio Calculado",
            "Precio Final",
            "Motivo Ajuste",
            "Estado",
        ]
        worksheet.write_row(0, 0, headers, bold)

        row_idx = 1
        for ticket in rows:
            precio_final = _effective_price(ticket)
            precio_calc = (
                ticket.precio_calculado
                if ticket.precio_calculado is not None
                else ticket.precio_total
            )
            worksheet.write_row(
                row_idx,
                0,
                [
                    ticket.id,
                    ticket.placa,
                    tipos_map.get(ticket.id_tipo_vehiculo, ticket.id_tipo_vehiculo),
                    ticket.nombre_parqueadero or "",
                    _format_dt(ticket.fecha_ingreso),
                    _format_dt(ticket.fecha_salida),
                    ticket.total_horas if ticket.total_horas is not None else "",
                    precio_calc if precio_calc is not None else "",
                    precio_final if precio_final is not None else "",
                    ticket.motivo_ajuste or "",
                    ticket.estado,
                ],
            )
            row_idx += 1
            count += 1
            if precio_final is not None:
                total_recaudado += float(precio_final)

        worksheet.write_row(
            row_idx + 1,
            0,
            ["TOTAL REGISTROS", count, "", "", "", "", "", "TOTAL RECAUDADO", total_recaudado],
            bold,
        )
    finally:
        workbook.close()

    tmp.seek(0)
    return tmp, count, total_recaudado


def _draw_pdf_header(
    c: canvas.Canvas,
    page_width: float,
    page_height: float,
    desde: date,
    hasta: date,
    tipo: str,
) -> float:
    c.setFont("Helvetica-Bold", 13)
    c.drawString(30, page_height - 32, "REPORTE DE REGISTROS - PARQUEADERO POS")
    c.setFont("Helvetica", 9)
    c.drawString(
        30,
        page_height - 48,
        f"Rango: {desde.isoformat()} a {hasta.isoformat()} | Tipo: {tipo}",
    )

    y = page_height - 70
    c.setFont("Helvetica-Bold", 8)
    columns = [
        (30, "Placa"),
        (100, "Tipo"),
        (185, "Ingreso"),
        (295, "Salida"),
        (405, "Horas"),
        (450, "P. Calc"),
        (515, "P. Final"),
        (580, "Estado"),
        (650, "Motivo Ajuste"),
    ]
    for x, label in columns:
        c.drawString(x, y, label)
    c.line(30, y - 4, page_width - 30, y - 4)
    c.setFont("Helvetica", 8)
    return y - 18


def _build_pdf_spooled(
    rows: Iterator[models.Ticket],
    tipos_map: dict[str, str],
    desde: date,
    hasta: date,
    tipo: str,
) -> tuple[tempfile.SpooledTemporaryFile, int, float]:
    tmp = tempfile.SpooledTemporaryFile(max_size=_SPOOL_MAX_BYTES)
    page_width, page_height = landscape(letter)
    c = canvas.Canvas(tmp, pagesize=(page_width, page_height))

    count = 0
    total_recaudado = 0.0
    y = _draw_pdf_header(c, page_width, page_height, desde, hasta, tipo)

    for ticket in rows:
        if y < 50:
            c.showPage()
            y = _draw_pdf_header(c, page_width, page_height, desde, hasta, tipo)

        precio_final = _effective_price(ticket)
        precio_calc = (
            ticket.precio_calculado
            if ticket.precio_calculado is not None
            else ticket.precio_total
        )
        tipo_nombre = tipos_map.get(ticket.id_tipo_vehiculo, "-")[:14]
        motivo = (ticket.motivo_ajuste or "-")[:24]

        c.drawString(30, y, ticket.placa[:12])
        c.drawString(100, y, tipo_nombre)
        c.drawString(185, y, _format_dt(ticket.fecha_ingreso))
        c.drawString(295, y, _format_dt(ticket.fecha_salida))
        c.drawString(405, y, f"{ticket.total_horas:g}" if ticket.total_horas is not None else "-")
        c.drawString(450, y, _format_money(precio_calc))
        c.drawString(515, y, _format_money(precio_final))
        c.drawString(580, y, ticket.estado[:12])
        c.drawString(650, y, motivo)

        y -= 14
        count += 1
        if precio_final is not None:
            total_recaudado += float(precio_final)

    if y < 60:
        c.showPage()
        y = page_height - 50

    c.line(30, y, page_width - 30, y)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(
        30,
        y - 16,
        f"Total registros: {count} | Total recaudado: {_format_money(total_recaudado)}",
    )
    c.save()

    tmp.seek(0)
    return tmp, count, total_recaudado


def _stream_spooled_file(tmp: tempfile.SpooledTemporaryFile) -> Iterator[bytes]:
    try:
        while True:
            chunk = tmp.read(_STREAM_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        tmp.close()


def generar_exportacion(
    db: Session,
    formato: Optional[str],
    tipo: Optional[str],
    desde: Optional[str],
    hasta: Optional[str],
    actor: models.Usuario,
) -> tuple[Iterator[bytes], str, str]:
    fmt, kind, d_desde, d_hasta = validate_export_params(formato, tipo, desde, hasta)

    dt_desde = datetime.combine(d_desde, time.min)
    dt_hasta = datetime.combine(d_hasta, time.max)

    tipos_map = {t.id: t.nombre for t in tipo_repository.list_all(db)}
    rows_iter = ticket_repository.iter_tickets_for_export(db, dt_desde, dt_hasta)

    if fmt == "xlsx":
        spooled, count, total = _build_xlsx_spooled(rows_iter, tipos_map)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"registros_{kind}_{d_desde.isoformat()}_{d_hasta.isoformat()}.xlsx"
    else:
        spooled, count, total = _build_pdf_spooled(rows_iter, tipos_map, d_desde, d_hasta, kind)
        media_type = "application/pdf"
        filename = f"registros_{kind}_{d_desde.isoformat()}_{d_hasta.isoformat()}.pdf"

    auditoria_service.registrar_evento(
        db=db,
        quien=actor.nombre,
        accion="EXPORTAR",
        entidad="ticket",
        despues={
            "formato": fmt,
            "tipo": kind,
            "desde": d_desde.isoformat(),
            "hasta": d_hasta.isoformat(),
            "registros": count,
            "total_recaudado": total,
        },
    )

    return _stream_spooled_file(spooled), media_type, filename


def listar_anios_con_registros(db: Session) -> list[int]:
    return ticket_repository.list_distinct_years(db)
