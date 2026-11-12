# Estado de Coordinación Backend ↔ Frontend — Sistema-PARQUEADERO

Este archivo es el único canal autorizado para que **Backend** y **Frontend** soliciten endpoints, cambios de contratos o ajustes entre capas (según la **Regla 7** de `docs/agents.md`).

> **Recordatorio:** Backend NO modifica archivos en `static/*` y Frontend NO modifica archivos de Backend (`*.py`).  
> **Impresión protegida:** Frontend NO debe modificar `static/ticket.html`, ni el bloque `@media print` / `.pos-ticket` de `static/style.css`, ni las llamadas `window.open('ticket.html?id=...', '_blank')`.

---

## 1. Guía de Integración Final para Frontend (`Fases 2A + 2B + 2C`)

1. **Sesión por Cookie `HttpOnly` (sin JWT):**
   - El login (`POST /api/auth/login`) emite la cookie `session_id` (`HttpOnly`, `SameSite=Strict`, `Secure` según entorno).
   - Al servirse Frontend y API desde el mismo origen (`http://127.0.0.1:8000`), el navegador envía la cookie automáticamente en cada `fetch(..., { credentials: 'same-origin' })` y en `static/ticket.html`.
   - Al cargar cualquier página operativa (`index.html`, `registros.html`, `configuracion.html`), consultar `GET /api/auth/me`:
     - Si responde `401`, redirigir al login (`login.html`).
     - Si responde `200`, usar `rol` (`"admin"` | `"cajero"`) para mostrar/ocultar acciones administrativas (tarifas, edición/eliminación de tickets, exportación XLSX/PDF, bitácora de auditoría).
2. **Formato Uniforme de Errores:**
   - Todos los errores HTTP (`400`, `401`, `403`, `404`, `422`, `429`, `500`) retornan exactamente:
     ```json
     {"error": {"codigo": "CODIGO_SEMANTICO", "mensaje": "Descripción legible para mostrar al usuario"}}
     ```
   - Leer siempre `data.error?.mensaje` en los `alert(...)` o mensajes de error de UI (en lugar de `data.detail`).
3. **Documentación Interactiva:**
   - Especificación OpenAPI completa disponible en `docs/openapi.yaml`, `/api/openapi.yaml`, `/api/openapi.json` y UI ligera en `/api/docs`.

---

## 2. Contratos Finales de API para Frontend

| ID | Endpoint | Método | Entrada (Body JSON o Query Params) | Respuesta Exitosa | Roles | Notas de Integración |
|---|---|---|---|---|---|---|
| **C-01** | `/api/auth/login` | `POST` | `{"nombre": "Admin", "password": "admin"}` *(acepta alias `username`)* | `200`: `{"usuario": {"id", "nombre", "rol", "activo", "creado"}, "expira": "..."}` | Público | Rate limit (`429` `LIMITE_EXCEDIDO` con `Retry-After`). Usuarios seed: `Admin`/`admin`, `Cajero`/`123456`. |
| **C-02** | `/api/auth/logout` | `POST` | *(Cookie `session_id`)* | `200`: `{"detail": "Sesión cerrada"}` | Público / Auth | Invalida sesión en SQLite y expira cookie. |
| **C-03** | `/api/auth/me` | `GET` | *(Cookie `session_id`)* | `200`: `{"id", "nombre", "rol", "activo", "expira"}` | `admin` \| `cajero` | `401` si no hay sesión o expiró. |
| **C-04** | `/api/auth/cambiar-password` | `POST` | `{"password_actual": "...", "password_nueva": "..."}` *(acepta alias `password_anterior`)* | `200`: `{"detail": "Contraseña actualizada correctamente"}` | `admin` \| `cajero` | Exige contraseña actual (`400` `PASSWORD_INCORRECTA` si falla). Mínimo 4 caracteres. |
| **C-05** | `/tipos-vehiculo` | `GET` | - | `200`: `[{"id", "nombre", "tarifa_hora", "tarifa_dia", "tarifa_noche"}]` | `admin` \| `cajero` | Carga selector de tipos en ingreso y tabla en configuración. |
| **C-06** | `/tipos-vehiculo` | `POST` | `{"nombre": "CARRO", "tarifa_hora": 2000, "tarifa_dia": 10000, "tarifa_noche": 6000}` | `201`: Objeto `TipoVehiculo` | **Solo `admin`** | `403` para `cajero`. Auditado en `auditoria`. |
| **C-07** | `/tipos-vehiculo/{id_tipo}` | `PUT` | `{"nombre": "CARRO", "tarifa_hora": 2500, "tarifa_dia": 12000, "tarifa_noche": 7000}` | `200`: Objeto `TipoVehiculo` | **Solo `admin`** | `403` para `cajero`. Auditado (`antes`/`despues`). |
| **C-08** | `/ticket/ingreso` | `POST` | `{"placa": "ABC-123", "id_tipo_vehiculo": "..."}` | `201`: Objeto `Ticket` (`estado: "ACTIVO"`) | `admin` \| `cajero` | Usar `data.id` para abrir `ticket.html?id=${data.id}&tipo=ingreso`. |
| **C-09** | `/ticket/pre-salida/{identificador}` | `GET` | Path: `id` del ticket o `placa` activa | `200`: `{"id", "placa", "total_horas", "precio_total", "precio_calculado"}` | `admin` \| `cajero` | Excluye eliminados. `400` si ya salió, `404` si no existe. |
| **C-10** | `/ticket/salida/{identificador}` | `PUT` | `{}` o `{"precio_personalizado": 5000, "motivo_ajuste": "Convenio"}` | `200`: Objeto `Ticket` (`precio_calculado`, `precio_final`, `precio_total`, `motivo_ajuste`, `estado: "FINALIZADO"`) | `admin` \| `cajero` | **Si se envía precio personalizado, `motivo_ajuste` es obligatorio (`400` `MOTIVO_REQUERIDO`).** |
| **C-11** | `/ticket/{id_ticket}/precio` | `PATCH` / `PUT` | `{"precio_final": 4000, "motivo_ajuste": "Descuento gerencia"}` | `200`: Objeto `Ticket` actualizado | `admin` \| `cajero` | Solo sobre tickets con salida registrada. Conserva `precio_calculado` original. Auditado. |
| **C-12** | `/ticket/{id_ticket}` | `GET` | Path: `id_ticket` | `200`: Objeto `Ticket` | `admin` \| `cajero` | Consumido por `static/ticket.html`. `404` si está eliminado. |
| **C-13** | `/ticket/{id_ticket}` | `PUT` | `{"placa"?, "id_tipo_vehiculo"?, "nombre_parqueadero"?, "precio_final"?, "motivo_ajuste"?}` | `200`: Objeto `Ticket` actualizado | **Solo `admin`** | `403` para `cajero`. Auditado (`antes`/`despues`). |
| **C-14** | `/ticket/{id_ticket}` | `DELETE` | Path: `id_ticket` | `204 No Content` | **Solo `admin`** | Borrado lógico (`eliminado = true`, `estado = "ELIMINADO"`) + auditoría. `403` para `cajero`. |
| **C-15** | `/api/registros` | `GET` | Query: `?page=1&limit=50&estado=&placa=` (`limit` máx `100`, `estado`: `ACTIVO`\|`FINALIZADO`, `placa` prefijo) | `200`: `{"data": [Ticket...], "page": 1, "limit": 50, "total": N, "totalPages": M}` | `admin` \| `cajero` | Paginación SQL indexada; usar en `static/registros.html` en lugar de `/ticket` sin paginar. |
| **C-16** | `/api/exportar` | `GET` | Query: `?formato=xlsx\|pdf&tipo=dias\|semanas\|mes\|anio&desde=YYYY-MM-DD&hasta=YYYY-MM-DD` | `200`: Stream binario `.xlsx` o `.pdf` (`Content-Disposition: attachment`) | **Solo `admin`** | Límites: `dias` ≤ 20, `semanas` ≤ 10 (70d), `mes` ≤ 1 (31d), `anio` ≤ 1 (366d). `403` para `cajero`. |
| **C-17** | `/api/auditoria` | `GET` | Query: `?page=1&limit=50&entidad=&accion=` (`limit` máx `100`) | `200`: `{"data": [Auditoria...], "page": 1, "limit": 50, "total": N, "totalPages": M}` | **Solo `admin`** | Bitácora de trazabilidad. |
| **C-18** | `/api/docs` / `/api/openapi.yaml` | `GET` | - | UI HTML ligera / Especificación OpenAPI YAML | Público | Documentación interactiva del API. |
| **C-19** | `/api/exportar/anios` | `GET` | *(Cookie `session_id`)* | `200`: `{"anios": [2026, ...]}` | **Solo `admin`** | Lista años distintos con registros no eliminados (`DISTINCT strftime('%Y', fecha_ingreso)`) ordenados desc. |

---

## 3. Solicitudes Entre Agentes

*(Cuando Backend o Frontend necesiten algo de la otra capa, deben agregar una fila en la siguiente tabla y esperar respuesta).*

| ID Solicitud | Fecha | De | Para | Descripción del Requerimiento | Estado (`Pendiente` / `En atención` / `Resuelto`) | Respuesta / Detalle |
|---|---|---|---|---|---|---|
| *(Sin solicitudes pendientes)* | - | - | - | - | - | - |
