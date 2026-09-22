# Sistema-PARQUEADERO

Sistema POS (Punto de Venta) para el control de ingreso y salida de vehículos en un parqueadero, con generación e impresión de tickets. Backend en **FastAPI** con base de datos **SQLite**, y frontend web ligero (HTML/CSS/JS) pensado para operarse desde un computador en caja.

## Características

- Registro de **ingreso** de vehículos (placa + tipo de vehículo).
- Cálculo automático del **precio a cobrar** según el tiempo transcurrido (tarifa por hora, por día o por varios días).
- Registro de **salida** con opción de ajustar el precio manualmente.
- **Tipos de vehículo** configurables (tarifa por hora, por día y nocturna).
- **Listado de tickets** (activos e históricos).
- Interfaz web lista para imprimir el ticket físico.
- Pensado para correr 24/7 como servicio del sistema operativo (ver `GUIA.md`).

## Tecnologías

- Python 3 + [FastAPI](https://fastapi.tiangolo.com/)
- SQLAlchemy + SQLite
- Pydantic (validación de datos)
- HTML / CSS / JavaScript (frontend estático servido por FastAPI)

## Estructura del proyecto

```
Sistema-PARQUEADERO/
├── main.py              # Punto de entrada de la app FastAPI
├── database.py           # Configuración de la base de datos SQLite
├── models.py              # Modelos SQLAlchemy (TipoVehiculo, Ticket)
├── schemas.py              # Esquemas Pydantic
├── routers/
│   ├── tipos.py            # Endpoints de tipos de vehículo
│   └── tickets.py           # Endpoints de ingreso/salida de tickets
├── static/                 # Frontend (index, ticket, registros, configuración)
├── instalar_zorin.sh       # Instalador como servicio systemd (Zorin OS/Ubuntu)
├── GUIA.md                 # Guía de instalación en el PC del parqueadero
└── parqueadero.db          # Base de datos SQLite (se crea automáticamente)
```

## Instalación y ejecución local

```bash
# Clonar el repositorio
git clone https://github.com/BryanLizcano/Sistema-PARQUEADERO.git
cd Sistema-PARQUEADERO

# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate
pip install fastapi uvicorn pydantic sqlalchemy

# Ejecutar el servidor
uvicorn main:app --reload
```

La aplicación quedará disponible en `http://127.0.0.1:8000/`.

## Instalación en el punto de venta (producción)

Para dejar el sistema corriendo permanentemente en el computador del parqueadero (arranque automático, reinicio ante fallos, sin terminal visible), sigue la guía completa en [`GUIA.md`](./GUIA.md), que usa el script `instalar_zorin.sh` para registrar la aplicación como servicio de `systemd`.

## Endpoints principales

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/tipos-vehiculo` | Crear un tipo de vehículo (con tarifas) |
| `GET` | `/tipos-vehiculo` | Listar tipos de vehículo |
| `PUT` | `/tipos-vehiculo/{id_tipo}` | Actualizar tarifas de un tipo de vehículo |
| `POST` | `/ticket/ingreso` | Registrar el ingreso de un vehículo |
| `GET` | `/ticket/pre-salida/{identificador}` | Calcular el valor a cobrar (por ID o placa) |
| `PUT` | `/ticket/salida/{identificador}` | Registrar la salida y cerrar el cobro |
| `GET` | `/ticket` | Listar todos los tickets |
| `GET` | `/ticket/{id_ticket}` | Consultar un ticket específico |
| `DELETE` | `/ticket/{id_ticket}` | Eliminar un ticket |

> La documentación interactiva de la API (Swagger) está disponible en `http://127.0.0.1:8000/docs` una vez el servidor está corriendo.

## Lógica de tarifas

- **Menos de 12 horas:** se cobra `total_horas × tarifa_hora`.
- **Entre 12 y 24 horas:** se cobra la `tarifa_dia` completa.
- **Más de 24 horas:** se cobra `tarifa_dia × número de días` (redondeado hacia arriba).

## Roadmap / Próximas mejoras

- [ ] Módulo de descarga de registros (todos o por rango de fechas).
- [ ] Manejo de caja: apertura, cierres de caja y control por turnos.
- [ ] Registro de clientes recurrentes asociados a sus vehículos.
- [ ] Módulo de mensualidades.

## Autor

**Bryan Gonzalo Lizcano Duran**
📧 bryanlizcano80@gmail.com
