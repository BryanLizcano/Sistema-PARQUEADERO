from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from database import Base
import uuid
from datetime import datetime, timezone

def generate_uuid():
    return str(uuid.uuid4())

def get_local_now():
    return datetime.now() # Usa hora local o timezone.utc según prefieras

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

