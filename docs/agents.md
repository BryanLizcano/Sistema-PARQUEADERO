# Reglas y Directrices para Agentes — Sistema-PARQUEADERO

Este documento establece las normas obligatorias de arquitectura, desarrollo, calidad y coordinación para todos los agentes (Líder/Arquitecto, Backend, Frontend y QA) que intervienen en el repositorio **Sistema-PARQUEADERO**.

---

## 1. Contexto Técnico Real del Repositorio

> **Nota tras inspección del repositorio:** Aunque en referencias externas se mencione un enfoque tipo Node/Express con arquitectura limpia, el código fuente actual del proyecto está implementado en **Python 3 + FastAPI + SQLAlchemy + Pydantic + SQLite** y sirve un frontend estático en `static/` (**HTML5, CSS3, Vanilla JS y Bootstrap 5**). Los principios de **Arquitectura Limpia (Clean Architecture)** se aplican directamente sobre esta base tecnológica sin reemplazar el stack existente ni introducir dependencias pesadas.

### Estructura Actual del Proyecto
- `main.py`: Punto de entrada de la aplicación FastAPI, configuración de CORS, registro de routers y montaje de archivos estáticos (`static/`).
- `database.py`: Configuración de conexión a SQLite (`parqueadero.db`), motor SQLAlchemy y dependencia `get_db`.
- `models.py`: Modelos ORM de SQLAlchemy (`TipoVehiculo`, `Ticket`).
- `schemas.py`: Esquemas de validación y serialización con Pydantic (`TipoVehiculo*`, `Ticket*`).
- `routers/`: Controladores/endpoints HTTP separados por dominio (`tipos.py`, `tickets.py`).
- `static/`: Interfaz gráfica de usuario para el punto de venta (`index.html`, `registros.html`, `configuracion.html`, `ticket.html`, `style.css`).
- `test_main.py`: Suite de pruebas automatizadas con `pytest` y `TestClient` sobre SQLite en memoria (`sqlite:///:memory:`).
- `instalar_zorin.sh` y `GUIA.md`: Script de despliegue y guía operativa para ejecución 24/7 como servicio `systemd` (`parqueadero.service`) en Zorin OS.

---

## 2. Reglas Obligatorias para Todos los Agentes

### Regla 1: Hardware Destino y Restricción de Recursos
- **Entorno de producción:**
  - **Sistema Operativo:** Zorin OS (basado en Ubuntu Linux).
  - **Procesador:** Intel Core i5 de 2da generación.
  - **Memoria:** 4 GB de RAM.
  - **Modo de ejecución:** Corriendo 24/7 en segundo plano como servicio de `systemd` (`parqueadero.service` ejecutando `uvicorn main:app --host 127.0.0.1 --port 8000`).
- **Prohibido usar dependencias pesadas:**
  - No agregar librerías de alto consumo de memoria o CPU (por ejemplo: `pandas`, motores de reportes pesados, navegadores headless como Playwright/Puppeteer en producción, u ORMs/frameworks adicionales).
  - Para exportación de datos o reportes, utilizar módulos nativos de la librería estándar de Python (`csv`, `io`, `datetime`) y respuestas en streaming o ligeras.
  - En Frontend, evitar bundlers pesados (`webpack`, `vite`), `node_modules` en producción, CDN externos y frameworks SPA pesados (Angular, React completo, Vue completo). Se permiten únicamente micro-librerías reactivas vendoreadas localmente sin paso de compilación (< 15 KB comprimidas en `static/vendor/`, como `Preact + htm + @preact/signals`) que mantengan bajo el consumo de RAM del navegador en el PC de caja.
- **Priorizar bajo consumo de RAM y CPU:**
  - Optimizar consultas en SQLite usando índices apropiados y filtros en base de datos en lugar de cargar tablas completas en memoria.
  - Cerrar siempre sesiones y cursores de base de datos (`Depends(get_db)`).

### Regla 2: Prohibición Estricta de Modificar la Impresión
- **NO modificar nada de la configuración ni del código de impresión.** Lograr que el formato y disparo de impresión funcionaran correctamente en la impresora térmica POS (80mm) fue difícil de conseguir.
- **Elementos intocables:**
  1. Archivo `static/ticket.html` completo (estructura DOM `#printable-ticket`, estilos inline, lógica de obtención de datos del ticket y el bloque `window.print()`).
  2. Reglas de impresión en `static/style.css`: bloque `@media print`, `#printable-ticket` (ancho `78mm`, márgenes `0`, visibilidad) y clases `.pos-ticket` (líneas 22 a 82).
  3. Invocaciones a la ventana de impresión `window.open('ticket.html?id=...', '_blank')` en `static/index.html` y `static/registros.html`.
  4. Campos requeridos por `static/ticket.html` en la respuesta de `GET /ticket/{id_ticket}` (`id`, `placa`, `nombre_parqueadero`, `fecha_ingreso`, `fecha_salida`, `total_horas`, `precio_total`).

### Regla 3: Pruebas Automatizadas Obligatorias
- **Toda feature, mejora o corrección de bug debe incluir pruebas automatizadas.**
- Las pruebas deben ejecutarse con `pytest` (`python -m pytest`) utilizando una base de datos SQLite en memoria (`sqlite:///:memory:`) aislada para no alterar `parqueadero.db`.
- Cada funcionalidad nueva debe cubrir:
  - Caso de éxito principal (happy path).
  - Casos borde (límites de horas/tarifas, filtros vacíos, rangos de fechas, turnos abiertos/cerrados).
  - Manejo de errores y códigos de estado HTTP (`400`, `404`, `422`).
- Ningún cambio puede romper las pruebas existentes.

### Regla 4: Diseño Pensando en Crecimiento (Arquitectura Limpia y Modular)
- **Separación en capas y módulos sin acoplamiento:**
  - **Capa de Presentación / Transporte (`routers/`, `schemas.py`):** Recibe peticiones HTTP, valida esquemas de entrada/salida con Pydantic y delega la operación. No debe contener cálculos complejos ni lógica de negocio embebida.
  - **Capa de Aplicación / Servicios (`services/`):** Contiene la lógica de negocio pura y casos de uso (cálculo de tarifas, gestión de turnos/caja, validación de mensualidades, clientes recurrentes, generación de exportaciones). Debe ser independiente de la interfaz web.
  - **Capa de Dominio y Persistencia (`models.py`, `repositories/`, `database.py`):** Definición de entidades y consultas encapsuladas hacia SQLite.
  - **Frontend (`static/`):** Código organizado por vista/módulo, funciones con responsabilidad única, sin lógica de negocio duplicada que corresponda al servidor.

### Regla 5: Política de Comentarios en el Código
- **Escribir comentarios única y exclusivamente donde sean necesarios para entender el *porqué*** de una decisión técnica, regla de negocio no evidente o restricción de hardware/impresión.
- **Prohibidos los comentarios obvios** que repitan lo que el código ya expresa por sí mismo (ej. `# Incrementa contador`, `# Retorna el ticket`, `# Importar librerías`).
- Preferir nombres descriptivos en funciones, variables, esquemas y endpoints antes que comentarios explicativos.

### Regla 6: Aprobación Obligatoria del Agente QA
- **Ninguna tarea termina sin la aprobación explícita del agente QA.**
- Flujo de estados de una tarea en `docs/avance.md`:
  1. `Por hacer` → Estado inicial.
  2. `En progreso` → El agente asignado (Backend o Frontend) está trabajando o ha entregado su implementación para revisión de QA.
  3. `Finalizada` → **Exclusivo del agente QA** tras verificar código, pruebas automatizadas pasando al 100%, cumplimiento de arquitectura limpia, bajo consumo de recursos e integridad del sistema de impresión.
  4. `Rechazada por QA` → **Exclusivo del agente QA** cuando detecta fallos de pruebas, incumplimiento de reglas, acoplamiento indebido o regresiones. El agente responsable debe corregir los puntos señalados.

### Regla 7: Frontera Estricta Backend / Frontend y Coordinación
- **Backend NO toca archivos de Frontend (`static/*`) y Frontend NO toca archivos de Backend (`main.py`, `database.py`, `models.py`, `schemas.py`, `routers/*`, `services/*`, `repositories/*`, `test_*.py`).**
- **Protocolo de comunicación:**
  - Si Backend necesita un ajuste en la interfaz o Frontend requiere un nuevo endpoint, cambio en un payload JSON, filtro o campo adicional, **debe solicitarlo registrando el requerimiento en `docs/ESTADO-COORDINACION.md` y esperar respuesta** del otro equipo antes de continuar con esa dependencia.
  - Toda solicitud en `docs/ESTADO-COORDINACION.md` debe especificar: Fecha/ID, Agente solicitante, Agente destino, Contrato/Endpoint propuesto (método, ruta, request/response) y Estado de la solicitud (`Pendiente`, `En atención`, `Resuelto`).

---

## 3. Documentos de Referencia Obligatoria en `/docs`

- [`docs/arquitectura.md`](./arquitectura.md): Estructura de carpetas objetivo (capas, repositorios, servicios, controladores, migraciones y seeds) y reglas de desacoplamiento.
- [`docs/esquema-bd-migraciones.md`](./esquema-bd-migraciones.md): Diseño de esquemas SQLite (`usuarios`, `sesiones`, `auditoria`, evolución de `tickets` e índices), migraciones reversibles (`up`/`down`), seed `bcrypt` (`Admin`/`Cajero`) y regla de cambio de contraseña desde Configuración.
- [`docs/ESTADO-COORDINACION.md`](./ESTADO-COORDINACION.md): Contratos HTTP iniciales y tablero de peticiones entre Backend y Frontend.
- [`docs/avance.md`](./avance.md): Registro maestro de tareas y estados (`Por hacer`, `En progreso`, `Finalizada`, `Rechazada por QA`).

