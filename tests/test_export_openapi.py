from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
import models
from seeds import seed_usuarios
from services.rate_limit_service import login_rate_limiter


@pytest.fixture()
def export_ctx(monkeypatch):
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        seed_usuarios(db)
        tipo = models.TipoVehiculo(
            nombre="CARRO",
            tarifa_hora=2000.0,
            tarifa_dia=10000.0,
            tarifa_noche=6000.0,
        )
        db.add(tipo)
        db.commit()
        db.refresh(tipo)
        tipo_id = tipo.id
    finally:
        db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    login_rate_limiter.reset()
    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db

    admin_client = TestClient(app)
    assert admin_client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"}).status_code == 200

    cajero_client = TestClient(app)
    assert cajero_client.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"}).status_code == 200

    anon_client = TestClient(app)

    try:
        yield {
            "admin": admin_client,
            "cajero": cajero_client,
            "anon": anon_client,
            "tipo_id": tipo_id,
            "session_factory": TestingSessionLocal,
        }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        login_rate_limiter.reset()


def test_exportar_solo_admin(export_ctx):
    params = "?formato=xlsx&tipo=dias&desde=2026-10-01&hasta=2026-10-05"
    assert export_ctx["anon"].get(f"/api/exportar{params}").status_code == 401
    r_cajero = export_ctx["cajero"].get(f"/api/exportar{params}")
    assert r_cajero.status_code == 403
    assert r_cajero.json()["error"]["codigo"] == "PROHIBIDO"


def test_exportar_validaciones_formato_y_limites_rango(export_ctx):
    admin = export_ctx["admin"]

    # Formato y tipo inválidos
    r_fmt = admin.get("/api/exportar?formato=csv&tipo=dias&desde=2026-10-01&hasta=2026-10-02")
    assert r_fmt.status_code == 400
    assert r_fmt.json()["error"]["codigo"] == "FORMATO_INVALIDO"

    r_tipo = admin.get("/api/exportar?formato=xlsx&tipo=horas&desde=2026-10-01&hasta=2026-10-02")
    assert r_tipo.status_code == 400
    assert r_tipo.json()["error"]["codigo"] == "TIPO_RANGO_INVALIDO"

    # Fechas vacías, inválidas o invertidas
    assert admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=&hasta=").status_code == 400
    assert admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=2026-99-99&hasta=2026-10-02").status_code == 400
    r_inv = admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=2026-10-10&hasta=2026-10-01")
    assert r_inv.status_code == 400
    assert r_inv.json()["error"]["codigo"] == "RANGO_INVALIDO"

    # Días: máx 20 (20 pasa, 21 falla)
    assert admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=2026-10-01&hasta=2026-10-20").status_code == 200
    r_dias_ex = admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=2026-10-01&hasta=2026-10-21")
    assert r_dias_ex.status_code == 400
    assert r_dias_ex.json()["error"]["codigo"] == "RANGO_EXCEDIDO"

    # Semanas: máx 10 = 70 días (70 pasa, 71 falla)
    assert admin.get("/api/exportar?formato=xlsx&tipo=semanas&desde=2026-08-01&hasta=2026-10-09").status_code == 200
    r_sem_ex = admin.get("/api/exportar?formato=xlsx&tipo=semanas&desde=2026-08-01&hasta=2026-10-10")
    assert r_sem_ex.status_code == 400
    assert r_sem_ex.json()["error"]["codigo"] == "RANGO_EXCEDIDO"

    # Mes: máx 1 = 31 días (31 pasa, 32 falla)
    assert admin.get("/api/exportar?formato=pdf&tipo=mes&desde=2026-10-01&hasta=2026-10-31").status_code == 200
    r_mes_ex = admin.get("/api/exportar?formato=pdf&tipo=mes&desde=2026-10-01&hasta=2026-11-01")
    assert r_mes_ex.status_code == 400
    assert r_mes_ex.json()["error"]["codigo"] == "RANGO_EXCEDIDO"

    # Año: máx 1 = 365/366 días (bisiesto 366 pasa, 367 falla)
    assert admin.get("/api/exportar?formato=xlsx&tipo=anio&desde=2024-01-01&hasta=2024-12-31").status_code == 200
    r_anio_ex = admin.get("/api/exportar?formato=xlsx&tipo=anio&desde=2025-01-01&hasta=2026-01-02")
    assert r_anio_ex.status_code == 400
    assert r_anio_ex.json()["error"]["codigo"] == "RANGO_EXCEDIDO"


def test_exportar_xlsx_y_pdf_streaming_y_contenido(export_ctx):
    db = export_ctx["session_factory"]()
    try:
        rows = [
            models.Ticket(
                placa="EXP-001",
                nombre_parqueadero="PARQUEADERO BAHONDO",
                id_tipo_vehiculo=export_ctx["tipo_id"],
                fecha_ingreso=datetime(2026, 10, 5, 9, 0),
                fecha_salida=datetime(2026, 10, 5, 11, 0),
                total_horas=2.0,
                precio_total=3500.0,
                precio_calculado=4000.0,
                precio_final=3500.0,
                motivo_ajuste="Convenio",
                eliminado=False,
                estado="FINALIZADO",
            ),
            # Ticket fuera de rango (no debe aparecer)
            models.Ticket(
                placa="OUT-999",
                nombre_parqueadero="PARQUEADERO BAHONDO",
                id_tipo_vehiculo=export_ctx["tipo_id"],
                fecha_ingreso=datetime(2026, 9, 1, 9, 0),
                eliminado=False,
                estado="ACTIVO",
            ),
            # Ticket eliminado dentro de rango (no debe aparecer)
            models.Ticket(
                placa="DEL-888",
                nombre_parqueadero="PARQUEADERO BAHONDO",
                id_tipo_vehiculo=export_ctx["tipo_id"],
                fecha_ingreso=datetime(2026, 10, 6, 9, 0),
                eliminado=True,
                estado="ELIMINADO",
            ),
        ]
        # Añadir 50 filas adicionales para probar paginación PDF multi-página por streaming
        for idx in range(50):
            rows.append(
                models.Ticket(
                    placa=f"PDF-{idx:03d}",
                    nombre_parqueadero="PARQUEADERO BAHONDO",
                    id_tipo_vehiculo=export_ctx["tipo_id"],
                    fecha_ingreso=datetime(2026, 10, 7, 8, 0) + timedelta(minutes=idx),
                    fecha_salida=datetime(2026, 10, 7, 9, 0) + timedelta(minutes=idx),
                    total_horas=1.0,
                    precio_total=2000.0,
                    precio_calculado=2000.0,
                    precio_final=2000.0,
                    eliminado=False,
                    estado="FINALIZADO",
                )
            )
        db.add_all(rows)
        db.commit()
    finally:
        db.close()

    admin = export_ctx["admin"]

    res_xlsx = admin.get("/api/exportar?formato=xlsx&tipo=dias&desde=2026-10-01&hasta=2026-10-10")
    assert res_xlsx.status_code == 200
    assert (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        in res_xlsx.headers["content-type"]
    )
    assert ".xlsx" in res_xlsx.headers["content-disposition"]

    wb = openpyxl.load_workbook(BytesIO(res_xlsx.content))
    ws = wb["Registros"]
    all_values = [[cell.value for cell in row] for row in ws.iter_rows()]
    placas = [r[1] for r in all_values[1:] if r[1]]
    assert "EXP-001" in placas
    assert "OUT-999" not in placas
    assert "DEL-888" not in placas
    exp_row = next(r for r in all_values if r[1] == "EXP-001")
    assert exp_row[7] == 4000.0
    assert exp_row[8] == 3500.0
    assert exp_row[9] == "Convenio"

    res_pdf = admin.get("/api/exportar?formato=pdf&tipo=dias&desde=2026-10-01&hasta=2026-10-10")
    assert res_pdf.status_code == 200
    assert "application/pdf" in res_pdf.headers["content-type"]
    assert ".pdf" in res_pdf.headers["content-disposition"]
    assert res_pdf.content.startswith(b"%PDF")
    assert b"%%EOF" in res_pdf.content
    assert res_pdf.content.count(b"/Type /Page") >= 2  # Multi-página real

    # Auditoría de exportación registrada
    db = export_ctx["session_factory"]()
    try:
        eventos = db.query(models.Auditoria).filter(models.Auditoria.accion == "EXPORTAR").all()
        assert len(eventos) == 2
    finally:
        db.close()


def test_openapi_yaml_y_ui_ligera(export_ctx):
    client = export_ctx["anon"]

    res_docs = client.get("/api/docs")
    assert res_docs.status_code == 200
    assert "text/html" in res_docs.headers["content-type"]
    assert "Parqueadero POS" in res_docs.text
    assert "/api/openapi.json" in res_docs.text

    res_json = client.get("/api/openapi.json")
    assert res_json.status_code == 200
    spec = res_json.json()
    expected_paths = {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/cambiar-password",
        "/api/registros",
        "/api/exportar",
        "/api/exportar/anios",
        "/api/auditoria",
        "/tipos-vehiculo",
        "/ticket/ingreso",
        "/ticket/salida/{identificador}",
        "/ticket/{id_ticket}/precio",
        "/ticket/{id_ticket}",
    }
    assert expected_paths.issubset(set(spec["paths"].keys()))
    assert "cookieAuth" in spec["components"]["securitySchemes"]
    assert "ErrorResponse" in spec["components"]["schemas"]

    res_yaml = client.get("/api/openapi.yaml")
    assert res_yaml.status_code == 200
    assert "yaml" in res_yaml.headers["content-type"]
    assert "/api/exportar:" in res_yaml.text

    yaml_file = Path("docs/openapi.yaml")
    assert yaml_file.exists()
    disk_yaml = yaml_file.read_text(encoding="utf-8")
    for p in expected_paths:
        assert f"  {p}:" in disk_yaml


def test_exportar_anios_con_registros(export_ctx):
    assert export_ctx["anon"].get("/api/exportar/anios").status_code == 401
    assert export_ctx["cajero"].get("/api/exportar/anios").status_code == 403

    admin = export_ctx["admin"]
    assert admin.get("/api/exportar/anios").json() == {"anios": []}

    db = export_ctx["session_factory"]()
    try:
        db.add_all(
            [
                models.Ticket(
                    placa="YR-2024",
                    nombre_parqueadero="PARQUEADERO BAHONDO",
                    id_tipo_vehiculo=export_ctx["tipo_id"],
                    fecha_ingreso=datetime(2024, 5, 10, 8, 0),
                    eliminado=False,
                    estado="FINALIZADO",
                ),
                models.Ticket(
                    placa="YR-2026",
                    nombre_parqueadero="PARQUEADERO BAHONDO",
                    id_tipo_vehiculo=export_ctx["tipo_id"],
                    fecha_ingreso=datetime(2026, 11, 11, 9, 0),
                    eliminado=False,
                    estado="ACTIVO",
                ),
                # Año con solo ticket eliminado no debe incluirse
                models.Ticket(
                    placa="YR-2023-DEL",
                    nombre_parqueadero="PARQUEADERO BAHONDO",
                    id_tipo_vehiculo=export_ctx["tipo_id"],
                    fecha_ingreso=datetime(2023, 3, 1, 9, 0),
                    eliminado=True,
                    estado="ELIMINADO",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    res = admin.get("/api/exportar/anios")
    assert res.status_code == 200
    assert res.json() == {"anios": [2026, 2024]}
