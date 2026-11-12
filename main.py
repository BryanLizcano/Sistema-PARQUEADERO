import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import Base, SessionLocal, engine
from middlewares import (
    AuthContextMiddleware,
    SecurityHeadersMiddleware,
    register_exception_handlers,
)
from migrations import apply_migrations
from routers import auditoria, auth, docs, exportar, registros, tickets, tipos
from seeds import seed_usuarios
from services import openapi_service


def initialize_database() -> None:
    apply_migrations(engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_usuarios(db)
    finally:
        db.close()


initialize_database()

app = FastAPI(
    title="Parqueadero POS API",
    description="API con SQLite para tickets de parqueadero",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.openapi = lambda: openapi_service.build_openapi_schema(app)

register_exception_handlers(app)

_raw_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
_cors_origins = [origin.strip() for origin in _raw_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthContextMiddleware)
# SecurityHeadersMiddleware va al final para envolver también respuestas de error, auth y CORS.
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router)
app.include_router(tipos.router)
app.include_router(tickets.router)
app.include_router(registros.router)
app.include_router(exportar.router)
app.include_router(auditoria.router)
app.include_router(docs.router)

# html=True hace que index.html se sirva en "/" automáticamente; debe montarse al final.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
