import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from seeds import seed_usuarios
from services.rate_limit_service import login_rate_limiter

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def auth_client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        seed_usuarios(db)
    finally:
        db.close()

    login_rate_limiter.reset()
    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    resp_login = client.post(
        "/api/auth/login",
        json={"nombre": "Admin", "password": "admin"},
    )
    assert resp_login.status_code == 200, resp_login.text

    try:
        yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        login_rate_limiter.reset()


def test_crear_tipo_vehiculo(auth_client):
    response = auth_client.post(
        "/tipos-vehiculo",
        json={"nombre": "MOTO TEST", "tarifa_hora": 2000, "tarifa_dia": 10000, "tarifa_noche": 5000},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["nombre"] == "MOTO TEST"
    assert "id" in data


def test_listar_tipos_vehiculo(auth_client):
    auth_client.post(
        "/tipos-vehiculo",
        json={"nombre": "CARRO TEST", "tarifa_hora": 5000, "tarifa_dia": 20000, "tarifa_noche": 10000},
    )
    response = auth_client.get("/tipos-vehiculo")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[-1]["nombre"] == "CARRO TEST"


def test_flujo_completo_ticket(auth_client):
    resp_tipo = auth_client.post(
        "/tipos-vehiculo",
        json={"nombre": "BICI TEST", "tarifa_hora": 1000, "tarifa_dia": 5000, "tarifa_noche": 2500},
    )
    tipo_id = resp_tipo.json()["id"]

    resp_ingreso = auth_client.post(
        "/ticket/ingreso",
        json={"placa": "XYZ-999", "id_tipo_vehiculo": tipo_id},
    )
    assert resp_ingreso.status_code == 201, resp_ingreso.text
    ticket_in = resp_ingreso.json()
    assert ticket_in["placa"] == "XYZ-999"
    assert "id" in ticket_in
    ticket_id = ticket_in["id"]

    resp_get = auth_client.get(f"/ticket/{ticket_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["id"] == ticket_id

    resp_list = auth_client.get("/ticket")
    assert resp_list.status_code == 200
    assert isinstance(resp_list.json(), list)

    resp_salida = auth_client.put(f"/ticket/salida/{ticket_id}")
    assert resp_salida.status_code == 200, resp_salida.text
    ticket_out = resp_salida.json()

    assert ticket_out["fecha_salida"] is not None
    assert ticket_out["total_horas"] is not None
    assert ticket_out["precio_total"] is not None

    resp_salida_doble = auth_client.put(f"/ticket/salida/{ticket_id}")
    assert resp_salida_doble.status_code == 400
    err = resp_salida_doble.json()["error"]
    assert err["codigo"] == "TICKET_YA_FINALIZADO"
    assert "ya tiene registrada una salida" in err["mensaje"]


def test_salida_por_placa(auth_client):
    resp_tipo = auth_client.post(
        "/tipos-vehiculo",
        json={"nombre": "CAMIONETA TEST", "tarifa_hora": 3000, "tarifa_dia": 15000, "tarifa_noche": 7000},
    )
    tipo_id = resp_tipo.json()["id"]

    auth_client.post(
        "/ticket/ingreso",
        json={"placa": "MOTO-001", "id_tipo_vehiculo": tipo_id},
    )
    resp_salida = auth_client.put("/ticket/salida/MOTO-001")
    assert resp_salida.status_code == 200
    assert resp_salida.json()["placa"] == "MOTO-001"

    resp_salida_doble = auth_client.put("/ticket/salida/MOTO-001")
    assert resp_salida_doble.status_code == 404
