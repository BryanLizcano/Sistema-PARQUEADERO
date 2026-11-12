from datetime import datetime, timedelta
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
import models
from seeds import seed_usuarios
from services.rate_limit_service import login_rate_limiter


@pytest.fixture()
def ctx(monkeypatch):
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
            "engine": engine,
            "session_factory": TestingSessionLocal,
        }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        login_rate_limiter.reset()


def test_respuestas_error_uniformes(ctx):
    anon = ctx["anon"]
    cajero = ctx["cajero"]
    admin = ctx["admin"]

    r401 = anon.get("/api/registros")
    assert r401.status_code == 401
    assert r401.json() == {
        "error": {"codigo": "NO_AUTENTICADO", "mensaje": "No autenticado o sesión expirada"}
    }

    r403 = cajero.post(
        "/tipos-vehiculo",
        json={"nombre": "MOTO", "tarifa_hora": 1000, "tarifa_dia": 5000, "tarifa_noche": 3000},
    )
    assert r403.status_code == 403
    assert set(r403.json().keys()) == {"error"}
    assert r403.json()["error"]["codigo"] == "PROHIBIDO"
    assert isinstance(r403.json()["error"]["mensaje"], str)

    r404_ticket = admin.get("/ticket/no-existe-id")
    assert r404_ticket.status_code == 404
    assert r404_ticket.json()["error"]["codigo"] == "TICKET_NO_ENCONTRADO"

    r404_ruta = admin.get("/api/ruta-inexistente")
    assert r404_ruta.status_code == 404
    assert r404_ruta.json()["error"]["codigo"] == "NO_ENCONTRADO"

    r400 = admin.get("/api/registros?page=abc")
    assert r400.status_code == 400
    assert r400.json()["error"]["codigo"] == "PARAMETRO_INVALIDO"

    r422 = admin.post(
        "/ticket/ingreso",
        json={"placa": "invalid*placa", "id_tipo_vehiculo": ctx["tipo_id"]},
    )
    assert r422.status_code == 422
    assert r422.json()["error"]["codigo"] == "VALIDACION_ERROR"
    assert "mensaje" in r422.json()["error"]


def test_historial_paginado_limit_offset_indices_y_filtros(ctx):
    db = ctx["session_factory"]()
    base_time = datetime(2026, 10, 1, 8, 0, 0)
    try:
        tickets = []
        for i in range(125):
            es_eliminado = i >= 123
            es_finalizado = (i % 2 == 0) and not es_eliminado
            ingreso = base_time + timedelta(minutes=i)
            salida = ingreso + timedelta(hours=2) if es_finalizado else None
            estado = "ELIMINADO" if es_eliminado else ("FINALIZADO" if es_finalizado else "ACTIVO")
            tickets.append(
                models.Ticket(
                    placa=f"PLT-{i:03d}",
                    nombre_parqueadero="PARQUEADERO BAHONDO",
                    id_tipo_vehiculo=ctx["tipo_id"],
                    fecha_ingreso=ingreso,
                    fecha_salida=salida,
                    total_horas=2.0 if es_finalizado else None,
                    precio_total=4000.0 if es_finalizado else None,
                    precio_calculado=4000.0 if es_finalizado else None,
                    precio_final=4000.0 if es_finalizado else None,
                    eliminado=es_eliminado,
                    estado=estado,
                )
            )
        db.add_all(tickets)
        db.commit()
    finally:
        db.close()

    cajero = ctx["cajero"]

    # Parámetros vacíos como ?page=&limit=50&estado=&placa= deben usar defaults sin error
    executed_sql: list[str] = []

    def capture_sql(_conn, _cursor, statement, _parameters, _context, _executemany):
        executed_sql.append(statement)

    event.listen(ctx["engine"], "before_cursor_execute", capture_sql)
    try:
        res_default = cajero.get("/api/registros?page=&limit=50&estado=&placa=")
    finally:
        event.remove(ctx["engine"], "before_cursor_execute", capture_sql)

    assert res_default.status_code == 200
    body = res_default.json()
    assert body["page"] == 1
    assert body["limit"] == 50
    assert body["total"] == 123  # Excluye los 2 eliminados
    assert body["totalPages"] == 3
    assert len(body["data"]) == 50
    assert all(item["eliminado"] is False for item in body["data"])
    assert any("LIMIT" in sql.upper() and "OFFSET" in sql.upper() for sql in executed_sql)
    assert any("count(" in sql.lower() for sql in executed_sql)

    # Última página parcial
    res_p3 = cajero.get("/api/registros?page=3&limit=50")
    assert res_p3.status_code == 200
    assert len(res_p3.json()["data"]) == 23

    # Límite máximo 100 aunque soliciten 500
    res_max = cajero.get("/api/registros?page=1&limit=500")
    assert res_max.status_code == 200
    assert res_max.json()["limit"] == 100
    assert len(res_max.json()["data"]) == 100
    assert res_max.json()["totalPages"] == 2

    # Filtro por estado usando índice
    res_activos = cajero.get("/api/registros?estado=ACTIVO&limit=100")
    assert res_activos.status_code == 200
    assert res_activos.json()["total"] == 61
    assert all(t["estado"] == "ACTIVO" for t in res_activos.json()["data"])

    # Filtro por placa por prefijo e índice; excluye eliminados incluso con estado=ELIMINADO
    res_placa = cajero.get("/api/registros?placa=PLT-01")
    assert res_placa.status_code == 200
    assert res_placa.json()["total"] == 10  # PLT-010 .. PLT-019
    assert all(t["placa"].startswith("PLT-01") for t in res_placa.json()["data"])

    res_del = cajero.get("/api/registros?estado=ELIMINADO")
    assert res_del.status_code == 200
    assert res_del.json()["total"] == 0

    # Verificar que SQLite usa índice ix_tickets_fecha_ingreso / ix_tickets_placa
    with ctx["engine"].connect() as conn:
        plan = conn.exec_driver_sql(
            "EXPLAIN QUERY PLAN SELECT * FROM tickets WHERE eliminado = 0 AND placa >= 'PLT-01' AND placa < 'PLT-02' ORDER BY fecha_ingreso DESC LIMIT 50 OFFSET 0"
        ).fetchall()
        plan_text = " ".join(str(row) for row in plan).lower()
        assert "ix_tickets_" in plan_text


def test_permisos_cajero_salida_y_edicion_precio_con_motivo_y_auditoria(ctx):
    cajero = ctx["cajero"]
    tipo_id = ctx["tipo_id"]

    # Cajero registra ingreso
    res_in = cajero.post(
        "/ticket/ingreso",
        json={"placa": "CAJ-100", "id_tipo_vehiculo": tipo_id},
    )
    assert res_in.status_code == 201
    ticket_id = res_in.json()["id"]

    # No puede editar precio antes de salida
    res_early_edit = cajero.patch(
        f"/ticket/{ticket_id}/precio",
        json={"precio_final": 1500, "motivo_ajuste": "Convenio"},
    )
    assert res_early_edit.status_code == 400
    assert res_early_edit.json()["error"]["codigo"] == "TICKET_ACTIVO"

    # Salida con precio personalizado SIN motivo debe rechazarse
    res_no_motivo = cajero.put(
        f"/ticket/salida/{ticket_id}",
        json={"precio_personalizado": 1500},
    )
    assert res_no_motivo.status_code == 400
    assert res_no_motivo.json()["error"]["codigo"] == "MOTIVO_REQUERIDO"

    # Salida con precio personalizado CON motivo guarda precio_calculado original y precio_final
    res_salida = cajero.put(
        f"/ticket/salida/{ticket_id}",
        json={"precio_personalizado": 1500, "motivo_ajuste": "Descuento cliente frecuente"},
    )
    assert res_salida.status_code == 200
    t_out = res_salida.json()
    assert t_out["precio_calculado"] == 2000.0
    assert t_out["precio_final"] == 1500.0
    assert t_out["precio_total"] == 1500.0  # Sincronizado para ticket.html
    assert t_out["motivo_ajuste"] == "Descuento cliente frecuente"
    assert t_out["estado"] == "FINALIZADO"

    # Cajero puede editar precio final posterior conservando precio_calculado original
    res_edit_no_motivo = cajero.patch(
        f"/ticket/{ticket_id}/precio",
        json={"precio_final": 1000, "motivo_ajuste": "   "},
    )
    assert res_edit_no_motivo.status_code == 400
    assert res_edit_no_motivo.json()["error"]["codigo"] == "MOTIVO_REQUERIDO"

    res_edit_ok = cajero.patch(
        f"/ticket/{ticket_id}/precio",
        json={"precio_final": 1200, "motivo_ajuste": "Ajuste gerencia turno"},
    )
    assert res_edit_ok.status_code == 200
    t_edited = res_edit_ok.json()
    assert t_edited["precio_calculado"] == 2000.0
    assert t_edited["precio_final"] == 1200.0
    assert t_edited["precio_total"] == 1200.0
    assert t_edited["motivo_ajuste"] == "Ajuste gerencia turno"

    # Cajero NO puede editar tarifas, editar campos generales del ticket, eliminar ni consultar auditoría
    assert cajero.put(
        f"/tipos-vehiculo/{tipo_id}",
        json={"nombre": "CARRO", "tarifa_hora": 9999, "tarifa_dia": 20000, "tarifa_noche": 9000},
    ).status_code == 403
    assert cajero.put(
        f"/ticket/{ticket_id}",
        json={"placa": "CAJ-999"},
    ).status_code == 403
    assert cajero.delete(f"/ticket/{ticket_id}").status_code == 403
    assert cajero.get("/api/auditoria").status_code == 403

    # Verificar auditoría registrada para ajustes de precio
    db = ctx["session_factory"]()
    try:
        eventos = (
            db.query(models.Auditoria)
            .filter(models.Auditoria.entidad == "ticket", models.Auditoria.entidad_id == ticket_id)
            .order_by(models.Auditoria.fecha.asc())
            .all()
        )
        acciones = [e.accion for e in eventos]
        assert "AJUSTE_PRECIO" in acciones
        assert all(e.quien == "Cajero" for e in eventos)
        ultimo = eventos[-1]
        assert json.loads(ultimo.antes)["precio_final"] == 1500.0
        assert json.loads(ultimo.despues)["precio_final"] == 1200.0
    finally:
        db.close()


def test_permisos_admin_tarifas_editar_y_borrado_logico_auditados(ctx):
    admin = ctx["admin"]
    cajero = ctx["cajero"]
    tipo_id = ctx["tipo_id"]

    # Admin edita tarifa y queda auditado con antes/después
    res_tipo_edit = admin.put(
        f"/tipos-vehiculo/{tipo_id}",
        json={"nombre": "CARRO", "tarifa_hora": 3000, "tarifa_dia": 12000, "tarifa_noche": 7000},
    )
    assert res_tipo_edit.status_code == 200
    assert res_tipo_edit.json()["tarifa_hora"] == 3000.0

    # Crear ticket y luego Admin edita ticket y lo elimina lógicamente
    res_in = cajero.post(
        "/ticket/ingreso",
        json={"placa": "ADM-001", "id_tipo_vehiculo": tipo_id},
    )
    assert res_in.status_code == 201
    ticket_id = res_in.json()["id"]

    res_edit_ticket = admin.put(
        f"/ticket/{ticket_id}",
        json={"placa": "ADM-002", "nombre_parqueadero": "SEDE NORTE"},
    )
    assert res_edit_ticket.status_code == 200
    assert res_edit_ticket.json()["placa"] == "ADM-002"
    assert res_edit_ticket.json()["nombre_parqueadero"] == "SEDE NORTE"

    res_del = admin.delete(f"/ticket/{ticket_id}")
    assert res_del.status_code == 204

    # Borrado lógico: no aparece en GET ni registros ni pre-salida, pero sigue en BD
    assert admin.get(f"/ticket/{ticket_id}").status_code == 404
    assert admin.get(f"/ticket/pre-salida/{ticket_id}").status_code == 404
    assert all(t["id"] != ticket_id for t in admin.get("/ticket").json())
    assert admin.get("/api/registros?placa=ADM-002").json()["total"] == 0

    db = ctx["session_factory"]()
    try:
        row = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
        assert row is not None
        assert row.eliminado is True
        assert row.estado == "ELIMINADO"
    finally:
        db.close()

    # Consultar auditoría como Admin
    res_audit = admin.get("/api/auditoria?limit=50")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()["data"]
    acciones = {(a["entidad"], a["accion"]) for a in audit_data}
    assert ("tipo_vehiculo", "EDITAR") in acciones
    assert ("ticket", "EDITAR") in acciones
    assert ("ticket", "BORRADO_LOGICO") in acciones
