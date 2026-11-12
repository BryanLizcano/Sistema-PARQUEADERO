from datetime import datetime
from typing import List, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Tickets y Registros
# ==========================================
class TicketBase(BaseModel):
    placa: str = Field(..., pattern=r"^[A-Z0-9-]+$")
    id_tipo_vehiculo: str


class TicketSalida(BaseModel):
    precio_personalizado: Optional[float] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("precio_personalizado", "precio_final"),
    )
    motivo_ajuste: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("motivo_ajuste", "motivo"),
    )


class TicketEditarPrecio(BaseModel):
    precio_final: float = Field(
        ...,
        ge=0,
        validation_alias=AliasChoices("precio_final", "precio_personalizado"),
    )
    motivo_ajuste: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("motivo_ajuste", "motivo"),
    )


class TicketUpdateAdmin(BaseModel):
    placa: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9-]+$")
    id_tipo_vehiculo: Optional[str] = None
    nombre_parqueadero: Optional[str] = Field(default=None, min_length=1, max_length=120)
    precio_final: Optional[float] = Field(default=None, ge=0)
    motivo_ajuste: Optional[str] = Field(default=None, max_length=255)


class TicketCreate(TicketBase):
    nombre_parqueadero: Optional[str] = "PARQUEADERO BAHONDO"


class Ticket(TicketBase):
    id: str
    nombre_parqueadero: str
    fecha_ingreso: datetime
    fecha_salida: Optional[datetime] = None
    total_horas: Optional[float] = None
    precio_total: Optional[float] = None
    precio_calculado: Optional[float] = None
    precio_final: Optional[float] = None
    motivo_ajuste: Optional[str] = None
    eliminado: bool = False
    estado: str = "ACTIVO"

    model_config = ConfigDict(from_attributes=True)


class RegistrosPaginadosResponse(BaseModel):
    data: List[Ticket]
    page: int
    limit: int
    total: int
    totalPages: int


# ==========================================
# Auditoría
# ==========================================
class AuditoriaOut(BaseModel):
    id: str
    quien: str
    accion: str
    entidad: str
    entidad_id: Optional[str] = None
    antes: Optional[str] = None
    despues: Optional[str] = None
    fecha: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditoriaPaginadaResponse(BaseModel):
    data: List[AuditoriaOut]
    page: int
    limit: int
    total: int
    totalPages: int


# ==========================================
# Autenticación y Usuarios
# ==========================================
class LoginRequest(BaseModel):
    nombre: str = Field(
        ...,
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("nombre", "username"),
    )
    password: str = Field(..., min_length=1, max_length=72)


class UsuarioOut(BaseModel):
    id: str
    nombre: str
    rol: str
    activo: bool
    creado: datetime

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    usuario: UsuarioOut
    expira: datetime


class MeResponse(BaseModel):
    id: str
    nombre: str
    rol: str
    activo: bool
    expira: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CambiarPasswordRequest(BaseModel):
    password_actual: str = Field(
        ...,
        min_length=1,
        max_length=72,
        validation_alias=AliasChoices("password_actual", "password_anterior"),
    )
    password_nueva: str = Field(..., min_length=4, max_length=72)


class MessageResponse(BaseModel):
    detail: str


class AniosDisponiblesResponse(BaseModel):
    anios: List[int]
