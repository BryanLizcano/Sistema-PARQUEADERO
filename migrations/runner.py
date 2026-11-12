from sqlalchemy.engine import Connection, Engine
from migrations import v001_auth_auditoria_tickets

MIGRATIONS = [v001_auth_auditoria_tickets]


def _ensure_migrations_table(conn: Connection) -> None:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(32) PRIMARY KEY,
            nombre VARCHAR(120) NOT NULL,
            aplicada_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def apply_migrations(engine: Engine) -> list[str]:
    applied: list[str] = []
    with engine.begin() as conn:
        _ensure_migrations_table(conn)
        rows = conn.exec_driver_sql("SELECT version FROM schema_migrations").fetchall()
        existing = {row[0] for row in rows}

        for migration in MIGRATIONS:
            if migration.VERSION not in existing:
                migration.up(conn)
                conn.exec_driver_sql(
                    "INSERT INTO schema_migrations (version, nombre) VALUES (?, ?)",
                    (migration.VERSION, migration.NAME),
                )
                applied.append(migration.VERSION)
    return applied


def rollback_migration(engine: Engine, version: str) -> bool:
    target = next((m for m in MIGRATIONS if m.VERSION == version), None)
    if target is None:
        return False

    with engine.begin() as conn:
        _ensure_migrations_table(conn)
        row = conn.exec_driver_sql(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (version,),
        ).fetchone()
        if row is None:
            return False

        target.down(conn)
        conn.exec_driver_sql(
            "DELETE FROM schema_migrations WHERE version = ?",
            (version,),
        )
    return True
