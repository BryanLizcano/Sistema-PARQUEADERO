from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def get_local_now() -> datetime:
    return datetime.now()


def get_utc_now() -> datetime:
    # SQLite almacena fechas sin tzinfo; normalizar a UTC naive evita errores al comparar expiración.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TipoVehiculo(Base):
    __tablename__ = "tipos_vehiculo"

    id = Column(String, primary_key=True, default=generate_uuid)
    nombre = Column(String, unique=True, index=True, nullable=False)
    tarifa_hora = Column(Float, nullable=False)
    tarifa_dia = Column(Float, nullable=False)
    tarifa_noche = Column(Float, nullable=False)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String, primary_key=True, default=generate_uuid)
    placa = Column(String, index=True, nullable=False)
    nombre_parqueadero = Column(String, default="PARQUEADERO BAHONDO")
    id_tipo_vehiculo = Column(String, ForeignKey("tipos_vehiculo.id"), nullable=False)
    fecha_ingreso = Column(DateTime, default=get_local_now, nullable=False)
    fecha_salida = Column(DateTime, nullable=True)
    total_horas = Column(Float, nullable=True)
    precio_total = Column(Float, nullable=True)
    precio_calculado = Column(Float, nullable=True)
    precio_final = Column(Float, nullable=True)
    motivo_ajuste = Column(String(255), nullable=True)
    eliminado = Column(Boolean, nullable=False, default=False)
    estado = Column(String(20), nullable=False, default="ACTIVO")

    __table_args__ = (
        Index("ix_tickets_fecha_ingreso", "fecha_ingreso"),
        Index("ix_tickets_estado", "estado"),
        Index("ix_tickets_activo_placa", "placa", "eliminado", "fecha_salida"),
    )


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    nombre = Column(String(100), unique=True, index=True, nullable=False)
    hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    creado = Column(DateTime, nullable=False, default=get_utc_now)

    __table_args__ = (
        CheckConstraint("rol IN ('admin', 'cajero')", name="ck_usuarios_rol"),
    )


class Sesion(Base):
    __tablename__ = "sesiones"

    id = Column(String(64), primary_key=True)
    usuario_id = Column(
        String(36), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expira = Column(DateTime, nullable=False, index=True)
    creado = Column(DateTime, nullable=False, default=get_utc_now)


class Auditoria(Base):
    __tablename__ = "auditoria"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    quien = Column(String(100), nullable=False)
    accion = Column(String(50), nullable=False)
    entidad = Column(String(50), nullable=False)
    entidad_id = Column(String(36), nullable=True)
    antes = Column(Text, nullable=True)
    despues = Column(Text, nullable=True)
    fecha = Column(DateTime, nullable=False, default=get_local_now, index=True)

    __table_args__ = (Index("ix_auditoria_entidad", "entidad", "entidad_id"),)
