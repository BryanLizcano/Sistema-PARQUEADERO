# Diseño de Esquemas de Base de Datos, Migraciones Reversibles y Seed — Sistema-PARQUEADERO

Este documento define el diseño técnico de evolución de la base de datos SQLite (`parqueadero.db`), asegurando **cero pérdida de datos existentes**, **migraciones reversibles (`up` / `down`)**, **compatibilidad total con el sistema de impresión POS** y **bajo consumo de recursos** en el hardware destino (Zorin OS, Core i5 2da gen, 4 GB RAM).

---

## 1. Principios de Migración y Preservación de Datos

1. **No destructividad:** `parqueadero.db` ya contiene registros productivos en `tipos_vehiculo` y `tickets`. Queda prohibido ejecutar `DROP TABLE` sobre tablas existentes durante una migración `up`.
2. **Reversibilidad (`up` / `down`):**
   - Se utiliza una tabla de control `schema_migrations` para registrar cada versión aplicada:
     ```sql
     CREATE TABLE IF NOT EXISTS schema_migrations (
         version VARCHAR(32) PRIMARY KEY,
         nombre VARCHAR(120) NOT NULL,
         aplicada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
     );
     ```
   - Toda migración expone dos operaciones transaccionales atómicas:
     - `up(conn)`: Aplica los cambios de esquema, crea índices y realiza el backfill de datos existentes.
     - `down(conn)`: Revierte los cambios dejando los datos previos intactos.
3. **Inmutabilidad del contrato de impresión:**
   - `static/ticket.html` consume `GET /ticket/{id_ticket}` y lee `precio_total`. Por lo tanto, la columna `precio_total` se conserva en `tickets` y se mantiene sincronizada con `precio_final` (`precio_total = precio_final`), evitando tocar cualquier archivo de impresión.

---

## 2. Diseño de Esquemas de Base de Datos

### 2.1. Tabla `usuarios`
Almacena las cuentas de operadores y administradores del parqueadero.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUID v4 generado automáticamente. |
| `nombre` | `VARCHAR(100)` | `NOT NULL UNIQUE` | Nombre de usuario único (ej. `"Admin"`, `"Cajero"`). |
| `hash` | `VARCHAR(255)` | `NOT NULL` | Hash `bcrypt` de la contraseña (`$2b$12$...`). |
| `rol` | `VARCHAR(20)` | `NOT NULL CHECK (rol IN ('admin', 'cajero'))` | Rol de autorización en el sistema. |
| `activo` | `BOOLEAN` (`INTEGER`) | `NOT NULL DEFAULT 1` | `1` = activo, `0` = deshabilitado. |
| `creado` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Fecha y hora local de creación. |

**DDL (`up`):**
```sql
CREATE TABLE IF NOT EXISTS usuarios (
    id VARCHAR(36) PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    hash VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('admin', 'cajero')),
    activo BOOLEAN NOT NULL DEFAULT 1,
    creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_nombre ON usuarios (nombre);
```

---

### 2.2. Tabla `sesiones`
Controla las sesiones activas de usuarios autenticados sin requerir servidores de caché externos (como Redis), manteniendo el bajo consumo de RAM.

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(64)` | `PRIMARY KEY` | Identificador único / token de sesión (UUID v4 o token hex). |
| `usuario_id` | `VARCHAR(36)` | `NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE` | Usuario propietario de la sesión. |
| `expira` | `DATETIME` | `NOT NULL` | Fecha y hora de expiración de la sesión. |
| `creado` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Fecha y hora de inicio de sesión. |

**DDL (`up`):**
```sql
CREATE TABLE IF NOT EXISTS sesiones (
    id VARCHAR(64) PRIMARY KEY,
    usuario_id VARCHAR(36) NOT NULL,
    expira DATETIME NOT NULL,
    creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sesiones_usuario_id ON sesiones (usuario_id);
CREATE INDEX IF NOT EXISTS ix_sesiones_expira ON sesiones (expira);
```

---

### 2.3. Tabla `auditoria`
Registra la trazabilidad completa de acciones críticas en el sistema (creación/edición de tarifas, ingresos, salidas con o sin ajuste de precio, borrado lógico de tickets, inicios de sesión y cambios de contraseña).

| Columna | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
|---|---|---|---|
| `id` | `VARCHAR(36)` | `PRIMARY KEY` | UUID v4 del evento de auditoría. |
| `quien` | `VARCHAR(100)` | `NOT NULL` | Identificador o nombre del usuario que ejecutó la acción (`usuarios.id` / `usuarios.nombre`). |
| `accion` | `VARCHAR(50)` | `NOT NULL` | Acción realizada (ej. `CREAR`, `ACTUALIZAR`, `SALIDA`, `AJUSTE_PRECIO`, `BORRADO_LOGICO`, `CAMBIO_CLAVE`, `LOGIN`). |
| `entidad` | `VARCHAR(50)` | `NOT NULL` | Nombre de la entidad afectada (`ticket`, `tipo_vehiculo`, `usuario`, `sesion`). |
| `entidad_id` | `VARCHAR(36)` | `NULL` | ID del registro afectado. |
| `antes` | `TEXT` | `NULL` | Estado anterior serializado en JSON (`NULL` en creaciones). |
| `despues` | `TEXT` | `NULL` | Estado posterior serializado en JSON (`NULL` en cierres/eliminaciones). |
| `fecha` | `DATETIME` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Marca de tiempo local del evento. |

**DDL (`up`):**
```sql
CREATE TABLE IF NOT EXISTS auditoria (
    id VARCHAR(36) PRIMARY KEY,
    quien VARCHAR(100) NOT NULL,
    accion VARCHAR(50) NOT NULL,
    entidad VARCHAR(50) NOT NULL,
    entidad_id VARCHAR(36),
    antes TEXT,
    despues TEXT,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_auditoria_fecha ON auditoria (fecha);
CREATE INDEX IF NOT EXISTS ix_auditoria_entidad ON auditoria (entidad, entidad_id);
```

---

### 2.4. Evolución de la Tabla `tickets`
Se conservan todas las columnas originales (`id`, `placa`, `nombre_parqueadero`, `id_tipo_vehiculo`, `fecha_ingreso`, `fecha_salida`, `total_horas`, `precio_total`) y se añaden las siguientes columnas:

| Columna Nueva | Tipo SQLite / SQLAlchemy | Restricciones | Descripción |
|---|---|---|---|
| `precio_calculado` | `FLOAT` | `NULL` | Valor calculado automáticamente según las horas y la tarifa del tipo de vehículo. |
| `precio_final` | `FLOAT` | `NULL` | Valor efectivamente cobrado al cerrar el ticket (igual a `precio_calculado` o al valor ajustado). |
| `motivo_ajuste` | `VARCHAR(255)` | `NULL` | Motivo obligatorio cuando `precio_final != precio_calculado`. |
| `eliminado` | `BOOLEAN` (`INTEGER`) | `NOT NULL DEFAULT 0` | Indicador de borrado lógico (`0` = visible/activo, `1` = eliminado lógicamente). |
| `estado` | `VARCHAR(20)` | `NOT NULL DEFAULT 'ACTIVO'` | Estado del ticket (`ACTIVO`, `FINALIZADO`, `ELIMINADO`) para indexación y filtrado rápido. |

**DDL y Backfill de Datos Existentes (`up`):**
```sql
ALTER TABLE tickets ADD COLUMN precio_calculado FLOAT;
ALTER TABLE tickets ADD COLUMN precio_final FLOAT;
ALTER TABLE tickets ADD COLUMN motivo_ajuste VARCHAR(255);
ALTER TABLE tickets ADD COLUMN eliminado BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE tickets ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'ACTIVO';

-- Sincronizar registros históricos sin perder datos existentes
UPDATE tickets
SET precio_calculado = precio_total,
    precio_final = precio_total,
    estado = CASE
        WHEN eliminado = 1 THEN 'ELIMINADO'
        WHEN fecha_salida IS NOT NULL THEN 'FINALIZADO'
        ELSE 'ACTIVO'
    END;
```

---

### 2.5. Índices en `tickets` para Consultas Rápidas
Para garantizar tiempos de respuesta inmediatos en el Core i5 de 2da generación a medida que crezca el historial:

```sql
CREATE INDEX IF NOT EXISTS ix_tickets_fecha_ingreso ON tickets (fecha_ingreso);
CREATE INDEX IF NOT EXISTS ix_tickets_estado ON tickets (estado);
CREATE INDEX IF NOT EXISTS ix_tickets_placa ON tickets (placa);
CREATE INDEX IF NOT EXISTS ix_tickets_activo_placa ON tickets (placa, eliminado, fecha_salida);
```

---

## 3. Reversibilidad de la Migración (`down`)

La operación `down(conn)` revierte de forma limpia la migración `v001_auth_auditoria_tickets`:

```sql
-- 1. Eliminar índices añadidos en tickets
DROP INDEX IF EXISTS ix_tickets_activo_placa;
DROP INDEX IF EXISTS ix_tickets_estado;
DROP INDEX IF EXISTS ix_tickets_fecha_ingreso;

-- 2. Revertir columnas añadidas en tickets preservando todas las filas originales
ALTER TABLE tickets DROP COLUMN estado;
ALTER TABLE tickets DROP COLUMN eliminado;
ALTER TABLE tickets DROP COLUMN motivo_ajuste;
ALTER TABLE tickets DROP COLUMN precio_final;
ALTER TABLE tickets DROP COLUMN precio_calculado;

-- 3. Eliminar tablas nuevas en orden inverso de dependencias
DROP TABLE IF EXISTS auditoria;
DROP TABLE IF EXISTS sesiones;
DROP TABLE IF EXISTS usuarios;

-- 4. Eliminar registro de versión en schema_migrations
DELETE FROM schema_migrations WHERE version = '001';
```
*(Nota: Si la versión de SQLite del entorno fuera anterior a 3.35.0 y no soportara `ALTER TABLE DROP COLUMN`, el runner ejecuta el patrón estándar de SQLite: crear `tickets_backup` con las 8 columnas originales, copiar `SELECT id, placa, nombre_parqueadero, id_tipo_vehiculo, fecha_ingreso, fecha_salida, total_horas, precio_total FROM tickets`, reemplazar la tabla y recrear `ix_tickets_placa`).*

---

## 4. Seed de Usuarios y Cambio de Contraseña

### 4.1. Usuarios Iniciales (Seed Idempotente)
El script de seed verifica por `nombre` si los usuarios existen antes de insertarlos. Las contraseñas se almacenan exclusivamente hasheadas con **bcrypt** (factor de costo 12, ligero y seguro):

| Usuario (`nombre`) | Contraseña Inicial | Rol (`rol`) | Activo (`activo`) | Algoritmo de Hash |
|---|---|---|---|---|
| `Admin` | `admin` | `admin` | `True` (`1`) | `bcrypt` (`$2b$12$...`) |
| `Cajero` | `123456` | `cajero` | `True` (`1`) | `bcrypt` (`$2b$12$...`) |

### 4.2. Regla de Cambio de Contraseña desde Configuración
1. **Validación obligatoria de contraseña anterior:**
   - Para cambiar la contraseña desde la vista de **Configuración** (`static/configuracion.html`), el usuario debe enviar:
     - `password_anterior`: Contraseña vigente.
     - `password_nueva`: Nueva contraseña (mínimo 4 caracteres).
   - El servicio `auth_service.cambiar_password()` verifica `bcrypt.checkpw(password_anterior.encode('utf-8'), usuario.hash.encode('utf-8'))`.
   - Si `password_anterior` no coincide, se rechaza la operación con `HTTP 400 Bad Request` (`"La contraseña anterior es incorrecta"`).
2. **Actualización y Auditoría:**
   - Si coincide, se genera el nuevo hash `bcrypt`, se actualiza `usuarios.hash` y se registra en `auditoria` la acción `'CAMBIO_CLAVE'` sobre la entidad `'usuario'` (registrando únicamente metadatos, nunca contraseñas en texto plano).
