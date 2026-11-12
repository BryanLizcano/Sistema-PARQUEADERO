from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from migrations import apply_migrations, rollback_migration
import models
from seeds import seed_usuarios
from services.rate_limit_service import login_rate_limiter


@pytest.fixture()
def test_env(monkeypatch):
    # Usar rondas reducidas solo en pruebas para acelerar ejecución manteniendo bcrypt real.
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENV", raising=False)
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

    try:
        yield {
            "client": TestClient(app),
            "session_factory": TestingSessionLocal,
            "engine": engine,
        }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        login_rate_limiter.reset()


def test_seed_usuarios_idempotente_y_bcrypt(test_env):
    db = test_env["session_factory"]()
    try:
        created_again = seed_usuarios(db)
        assert created_again == []

        usuarios = db.query(models.Usuario).all()
        assert len(usuarios) == 2
        by_name = {u.nombre: u for u in usuarios}

        assert by_name["Admin"].rol == "admin"
        assert by_name["Admin"].hash.startswith("$2")
        assert by_name["Admin"].hash != "admin"

        assert by_name["Cajero"].rol == "cajero"
        assert by_name["Cajero"].hash.startswith("$2")
        assert by_name["Cajero"].hash != "123456"
    finally:
        db.close()


def test_login_unico_ambos_roles_y_cookie_httponly(test_env):
    client = test_env["client"]

    res_admin = client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"})
    assert res_admin.status_code == 200
    body_admin = res_admin.json()
    assert body_admin["usuario"]["nombre"] == "Admin"
    assert body_admin["usuario"]["rol"] == "admin"
    assert "hash" not in body_admin["usuario"]
    assert "token" not in body_admin

    set_cookie = res_admin.headers.get("set-cookie", "")
    assert "session_id=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()
    assert "secure" not in set_cookie.lower()

    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 200
    assert res_me.json()["nombre"] == "Admin"
    assert res_me.json()["rol"] == "admin"

    client_cajero = TestClient(app)
    res_cajero = client_cajero.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"})
    assert res_cajero.status_code == 200
    assert res_cajero.json()["usuario"]["rol"] == "cajero"

    res_me_cajero = client_cajero.get("/api/auth/me")
    assert res_me_cajero.status_code == 200
    assert res_me_cajero.json()["rol"] == "cajero"


def test_cookie_secure_segun_entorno(test_env, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    https_client = TestClient(app, base_url="https://testserver")

    res = https_client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"})
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=strict" in set_cookie
    assert "secure" in set_cookie
    assert "strict-transport-security" in res.headers

    res_me = https_client.get("/api/auth/me")
    assert res_me.status_code == 200


def test_login_credenciales_invalidas_y_usuario_inactivo(test_env):
    client = test_env["client"]

    res_bad_pass = client.post("/api/auth/login", json={"nombre": "Admin", "password": "wrong"})
    assert res_bad_pass.status_code == 401

    res_no_user = client.post("/api/auth/login", json={"nombre": "NoExiste", "password": "admin"})
    assert res_no_user.status_code == 401

    db = test_env["session_factory"]()
    try:
        cajero = db.query(models.Usuario).filter(models.Usuario.nombre == "Cajero").first()
        cajero.activo = False
        db.commit()
    finally:
        db.close()

    res_inactive = client.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"})
    assert res_inactive.status_code == 403


def test_logout_invalida_sesion_en_bd_y_cookie(test_env):
    client = test_env["client"]

    res_login = client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"})
    assert res_login.status_code == 200
    cookie_val = client.cookies.get("session_id")
    assert cookie_val

    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.json()["detail"] == "Sesión cerrada"

    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 401

    # Reenviar la cookie antigua manualmente tampoco debe autenticar porque la sesión se borró de BD.
    res_replay = client.get("/api/auth/me", headers={"Cookie": f"session_id={cookie_val}"})
    assert res_replay.status_code == 401


def test_sesion_expirada_rechazada(test_env):
    client = test_env["client"]
    res_login = client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"})
    assert res_login.status_code == 200
    session_id = client.cookies.get("session_id")

    db = test_env["session_factory"]()
    try:
        sesion = db.query(models.Sesion).filter(models.Sesion.id == session_id).first()
        sesion.expira = models.get_utc_now() - timedelta(minutes=5)
        db.commit()
    finally:
        db.close()

    res_me = client.get("/api/auth/me")
    assert res_me.status_code == 401


def test_rate_limit_en_login(test_env, monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT_MAX", "5")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW", "60")
    client = test_env["client"]

    for _ in range(5):
        res = client.post("/api/auth/login", json={"nombre": "Admin", "password": "wrong"})
        assert res.status_code == 401

    res_limited = client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"})
    assert res_limited.status_code == 429
    assert "Retry-After" in res_limited.headers


def test_security_headers_helmet(test_env):
    client = test_env["client"]

    res_static = client.get("/ticket.html")
    assert res_static.status_code == 200
    assert res_static.headers.get("x-content-type-options") == "nosniff"
    assert res_static.headers.get("x-frame-options") == "SAMEORIGIN"
    assert res_static.headers.get("x-xss-protection") == "0"
    assert res_static.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert res_static.headers.get("cross-origin-opener-policy") == "same-origin"
    assert res_static.headers.get("cross-origin-resource-policy") == "same-origin"
    assert "content-security-policy" in res_static.headers

    res_unauth = client.get("/api/auth/me")
    assert res_unauth.status_code == 401
    assert res_unauth.headers.get("cache-control") == "no-store"
    assert res_unauth.headers.get("x-content-type-options") == "nosniff"


def test_middleware_autorizacion_por_rol_admin_vs_cajero(test_env):
    anon_client = test_env["client"]
    assert anon_client.get("/tipos-vehiculo").status_code == 401
    assert anon_client.get("/ticket").status_code == 401
    assert anon_client.post(
        "/tipos-vehiculo",
        json={"nombre": "MOTO", "tarifa_hora": 1000, "tarifa_dia": 5000, "tarifa_noche": 3000},
    ).status_code == 401

    admin_client = TestClient(app)
    assert admin_client.post("/api/auth/login", json={"nombre": "Admin", "password": "admin"}).status_code == 200

    res_tipo = admin_client.post(
        "/tipos-vehiculo",
        json={"nombre": "CARRO", "tarifa_hora": 2000, "tarifa_dia": 10000, "tarifa_noche": 6000},
    )
    assert res_tipo.status_code == 201
    tipo_id = res_tipo.json()["id"]

    cajero_client = TestClient(app)
    assert cajero_client.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"}).status_code == 200

    assert cajero_client.get("/tipos-vehiculo").status_code == 200
    assert cajero_client.post(
        "/tipos-vehiculo",
        json={"nombre": "MOTO", "tarifa_hora": 1000, "tarifa_dia": 5000, "tarifa_noche": 3000},
    ).status_code == 403
    assert cajero_client.put(
        f"/tipos-vehiculo/{tipo_id}",
        json={"nombre": "CARRO", "tarifa_hora": 2500, "tarifa_dia": 12000, "tarifa_noche": 7000},
    ).status_code == 403

    res_ingreso = cajero_client.post(
        "/ticket/ingreso",
        json={"placa": "ABC-123", "id_tipo_vehiculo": tipo_id},
    )
    assert res_ingreso.status_code == 201
    ticket_id = res_ingreso.json()["id"]

    assert cajero_client.get(f"/ticket/{ticket_id}").status_code == 200
    assert cajero_client.delete(f"/ticket/{ticket_id}").status_code == 403
    assert admin_client.delete(f"/ticket/{ticket_id}").status_code == 204


def test_cambiar_password_exige_actual_e_invalida_otras_sesiones(test_env):
    client1 = TestClient(app)
    client2 = TestClient(app)

    assert client1.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"}).status_code == 200
    assert client2.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"}).status_code == 200

    # Sin sesión -> 401
    assert test_env["client"].post(
        "/api/auth/cambiar-password",
        json={"password_actual": "123456", "password_nueva": "nueva123"},
    ).status_code == 401

    # Contraseña actual incorrecta -> 400
    res_wrong = client1.post(
        "/api/auth/cambiar-password",
        json={"password_actual": "incorrecta", "password_nueva": "nueva123"},
    )
    assert res_wrong.status_code == 400

    # Cambio exitoso
    res_ok = client1.post(
        "/api/auth/cambiar-password",
        json={"password_actual": "123456", "password_nueva": "nueva123"},
    )
    assert res_ok.status_code == 200

    # Sesión actual sigue activa, otras sesiones del mismo usuario fueron invalidadas
    assert client1.get("/api/auth/me").status_code == 200
    assert client2.get("/api/auth/me").status_code == 401

    # Contraseña anterior ya no funciona; la nueva sí
    client3 = TestClient(app)
    assert client3.post("/api/auth/login", json={"nombre": "Cajero", "password": "123456"}).status_code == 401
    assert client3.post("/api/auth/login", json={"nombre": "Cajero", "password": "nueva123"}).status_code == 200

    # Verificar que la auditoría no guarde contraseñas en texto plano
    db = test_env["session_factory"]()
    try:
        eventos = db.query(models.Auditoria).filter(models.Auditoria.accion == "CAMBIO_CLAVE").all()
        assert len(eventos) == 1
        assert "123456" not in (eventos[0].despues or "")
        assert "nueva123" not in (eventos[0].despues or "")
    finally:
        db.close()


def test_migracion_reversible_preserva_datos_legacy():
    legacy_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with legacy_engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE tipos_vehiculo (
                id VARCHAR NOT NULL PRIMARY KEY,
                nombre VARCHAR NOT NULL,
                tarifa_hora FLOAT NOT NULL,
                tarifa_dia FLOAT NOT NULL,
                tarifa_noche FLOAT NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE tickets (
                id VARCHAR NOT NULL PRIMARY KEY,
                placa VARCHAR NOT NULL,
                nombre_parqueadero VARCHAR,
                id_tipo_vehiculo VARCHAR NOT NULL,
                fecha_ingreso DATETIME NOT NULL,
                fecha_salida DATETIME,
                total_horas FLOAT,
                precio_total FLOAT
            )
            """
        )
        conn.exec_driver_sql(
            "INSERT INTO tipos_vehiculo VALUES ('t1', 'CARRO', 2000, 5000, 5000)"
        )
        conn.exec_driver_sql(
            "INSERT INTO tickets VALUES ('tk1', 'ABC123', 'PARQ', 't1', '2026-09-10 10:00:00', '2026-09-10 11:00:00', 1.0, 2000.0)"
        )

    assert apply_migrations(legacy_engine) == ["001"]
    assert apply_migrations(legacy_engine) == []

    with legacy_engine.connect() as conn:
        ticket_row = conn.exec_driver_sql(
            "SELECT precio_calculado, precio_final, eliminado, estado FROM tickets WHERE id = 'tk1'"
        ).fetchone()
        assert ticket_row == (2000.0, 2000.0, 0, "FINALIZADO")

        indexes = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='tickets'"
            ).fetchall()
        }
        assert {"ix_tickets_fecha_ingreso", "ix_tickets_estado", "ix_tickets_placa"}.issubset(indexes)

    assert rollback_migration(legacy_engine, "001") is True
    with legacy_engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(tickets)").fetchall()}
        assert "precio_calculado" not in cols
        assert "eliminado" not in cols
        preserved = conn.exec_driver_sql(
            "SELECT id, placa, precio_total FROM tickets WHERE id = 'tk1'"
        ).fetchone()
        assert preserved == ("tk1", "ABC123", 2000.0)
