from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# ==========================================
# Tipos de Vehículo
# ==========================================
class TipoVehiculoBase(BaseModel):
    nombre: str = Field(..., pattern=r"^[A-ZÑ\s]+$")
    tarifa_hora: float = Field(..., ge=0)
    tarifa_dia: float = Field(..., ge=0)
    tarifa_noche: float = Field(..., ge=0)

class TipoVehiculoCreate(TipoVehiculoBase):
    pass

class TipoVehiculo(TipoVehiculoBase):
    id: str

    class Config:
        from_attributes = True # Permite que Pydantic lea desde modelos de SQLAlchemy

# ==========================================
# Tickets
# ==========================================
class TicketBase(BaseModel):
    placa: str = Field(..., pattern=r"^[A-Z0-9-]+$")
    id_tipo_vehiculo: str

class TicketSalida(BaseModel):
    precio_personalizado: Optional[float] = None

class TicketCreate(TicketBase):
    nombre_parqueadero: Optional[str] = "PARQUEADERO BAHONDO"

class Ticket(TicketBase):
    id: str
    nombre_parqueadero: str
    fecha_ingreso: datetime
    fecha_salida: Optional[datetime] = None
    total_horas: Optional[float] = None
    precio_total: Optional[float] = None

    class Config:
        from_attributes = True

