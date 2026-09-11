from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import tipos, tickets

# Crear las tablas en SQLite si no existen
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Parqueadero POS API", description="API con SQLite para tickets de parqueadero")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir las rutas separadas
app.include_router(tipos.router)
app.include_router(tickets.router)

# Montar los archivos estáticos (Frontend) al final
# html=True hace que index.html se sirva en "/" automáticamente
app.mount("/", StaticFiles(directory="static", html=True), name="static")
