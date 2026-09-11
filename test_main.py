import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db

# ==========================================
# Configuración de Base de Datos para Testing
# ==========================================
# Usamos una base de datos en memoria para no afectar los datos reales
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crear las tablas en la base de datos de memoria
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Reemplazamos la dependencia original por la de testing
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# ==========================================
# Tests
# ==========================================

def test_crear_tipo_vehiculo():
    response = client.post(
        "/tipos-vehiculo",
        json={"nombre": "MOTO TEST", "tarifa_hora": 2000, "tarifa_dia": 10000, "tarifa_noche": 5000}
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["nombre"] == "MOTO TEST"
    assert "id" in data
    return data["id"]

def test_listar_tipos_vehiculo():
    # Aseguramos que haya al menos uno (depende del test anterior o creamos uno nuevo)
    client.post(
        "/tipos-vehiculo",
        json={"nombre": "CARRO TEST", "tarifa_hora": 5000, "tarifa_dia": 20000, "tarifa_noche": 10000}
    )
    response = client.get("/tipos-vehiculo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[-1]["nombre"] == "CARRO TEST"

def test_flujo_completo_ticket():
    # 1. Crear tipo de vehículo
    resp_tipo = client.post(
        "/tipos-vehiculo",
        json={"nombre": "BICI TEST", "tarifa_hora": 1000, "tarifa_dia": 5000, "tarifa_noche": 2500}
    )
    tipo_id = resp_tipo.json()["id"]

    # 2. Registrar Ingreso
    resp_ingreso = client.post(
        "/ticket/ingreso",
        json={"placa": "XYZ-999", "id_tipo_vehiculo": tipo_id}
    )
    assert resp_ingreso.status_code == 201, resp_ingreso.text
    ticket_in = resp_ingreso.json()
    assert ticket_in["placa"] == "XYZ-999"
    assert "id" in ticket_in
    ticket_id = ticket_in["id"]

    # 3. Obtener ticket por ID
    resp_get = client.get(f"/ticket/{ticket_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == ticket_id

    # 4. Listar tickets
    resp_list = client.get("/ticket")
    assert resp_list.status_code == 200
    assert isinstance(resp_list.json(), list)

    # 5. Registrar Salida
    resp_salida = client.put(f"/ticket/salida/{ticket_id}")
    assert resp_salida.status_code == 200, resp_salida.text
    ticket_out = resp_salida.json()
    
    assert ticket_out["fecha_salida"] is not None
    assert ticket_out["total_horas"] is not None
    assert ticket_out["precio_total"] is not None

    # 6. Intentar registrar salida de nuevo por ID (debe fallar)
    resp_salida_doble = client.put(f"/ticket/salida/{ticket_id}")
    assert resp_salida_doble.status_code == 400
    assert "ya tiene registrada una salida" in resp_salida_doble.json()["detail"]

def test_salida_por_placa():
    # Crear un tipo de vehículo único para esta prueba
    resp_tipo = client.post(
        "/tipos-vehiculo",
        json={"nombre": "CAMIONETA TEST", "tarifa_hora": 3000, "tarifa_dia": 15000, "tarifa_noche": 7000}
    )
    tipo_id = resp_tipo.json()["id"]

    # Crear ingreso
    resp_ingreso = client.post(
        "/ticket/ingreso",
        json={"placa": "MOTO-001", "id_tipo_vehiculo": tipo_id}
    )
    # Registrar salida usando la placa
    resp_salida = client.put("/ticket/salida/MOTO-001")
    assert resp_salida.status_code == 200
    assert resp_salida.json()["placa"] == "MOTO-001"
    
    # Otra salida con la misma placa debe fallar porque ya no hay placas activas con ese nombre
    resp_salida_doble = client.put("/ticket/salida/MOTO-001")
    assert resp_salida_doble.status_code == 404

