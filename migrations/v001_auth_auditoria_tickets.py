from sqlalchemy.engine import Connection

VERSION = "001"
NAME = "auth_auditoria_tickets"

_TICKET_NEW_COLUMNS = (
    ("precio_calculado", "FLOAT"),
    ("precio_final", "FLOAT"),
    ("motivo_ajuste", "VARCHAR(255)"),
    ("eliminado", "BOOLEAN NOT NULL DEFAULT 0"),
    ("estado", "VARCHAR(20) NOT NULL DEFAULT 'ACTIVO'"),
)


def _table_exists(conn: Connection, table_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _get_columns(conn: Connection, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def up(conn: Connection) -> None:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id VARCHAR(36) PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            hash VARCHAR(255) NOT NULL,
            rol VARCHAR(20) NOT NULL CHECK (rol IN ('admin', 'cajero')),
            activo BOOLEAN NOT NULL DEFAULT 1,
            creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_nombre ON usuarios (nombre)"
    )

    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS sesiones (
            id VARCHAR(64) PRIMARY KEY,
            usuario_id VARCHAR(36) NOT NULL,
            expira DATETIME NOT NULL,
            creado DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
        )
        """
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_sesiones_usuario_id ON sesiones (usuario_id)"
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_sesiones_expira ON sesiones (expira)"
    )

    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS auditoria (
            id VARCHAR(36) PRIMARY KEY,
            quien VARCHAR(100) NOT NULL,
            accion VARCHAR(50) NOT NULL,
            entidad VARCHAR(50) NOT NULL,
            entidad_id VARCHAR(36),
            antes TEXT,
            despues TEXT,
            fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_auditoria_fecha ON auditoria (fecha)"
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_auditoria_entidad ON auditoria (entidad, entidad_id)"
    )

    if _table_exists(conn, "tickets"):
        existing_cols = _get_columns(conn, "tickets")
        for col_name, col_def in _TICKET_NEW_COLUMNS:
            if col_name not in existing_cols:
                conn.exec_driver_sql(
                    f"ALTER TABLE tickets ADD COLUMN {col_name} {col_def}"
                )

        # Conservar datos históricos intactos rellenando columnas nuevas desde precio_total/fecha_salida.
        conn.exec_driver_sql(
            """
            UPDATE tickets
            SET precio_calculado = COALESCE(precio_calculado, precio_total),
                precio_final = COALESCE(precio_final, precio_total),
                estado = CASE
                    WHEN eliminado = 1 THEN 'ELIMINADO'
                    WHEN fecha_salida IS NOT NULL THEN 'FINALIZADO'
                    ELSE 'ACTIVO'
                END
            """
        )

        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_tickets_fecha_ingreso ON tickets (fecha_ingreso)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_tickets_estado ON tickets (estado)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_tickets_placa ON tickets (placa)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_tickets_activo_placa ON tickets (placa, eliminado, fecha_salida)"
        )


def down(conn: Connection) -> None:
    if _table_exists(conn, "tickets"):
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_tickets_activo_placa")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_tickets_estado")
        conn.exec_driver_sql("DROP INDEX IF EXISTS ix_tickets_fecha_ingreso")

        existing_cols = _get_columns(conn, "tickets")
        cols_to_drop = [col for col, _ in reversed(_TICKET_NEW_COLUMNS) if col in existing_cols]
        if cols_to_drop:
            try:
                for col_name in cols_to_drop:
                    conn.exec_driver_sql(f"ALTER TABLE tickets DROP COLUMN {col_name}")
            except Exception:
                # Respaldo compatible con SQLite < 3.35 si ALTER TABLE DROP COLUMN no está disponible.
                conn.exec_driver_sql(
                    """
                    CREATE TABLE tickets_backup (
                        id VARCHAR NOT NULL PRIMARY KEY,
                        placa VARCHAR NOT NULL,
                        nombre_parqueadero VARCHAR,
                        id_tipo_vehiculo VARCHAR NOT NULL,
                        fecha_ingreso DATETIME NOT NULL,
                        fecha_salida DATETIME,
                        total_horas FLOAT,
                        precio_total FLOAT,
                        FOREIGN KEY(id_tipo_vehiculo) REFERENCES tipos_vehiculo (id)
                    )
                    """
                )
                conn.exec_driver_sql(
                    """
                    INSERT INTO tickets_backup (
                        id, placa, nombre_parqueadero, id_tipo_vehiculo,
                        fecha_ingreso, fecha_salida, total_horas, precio_total
                    )
                    SELECT id, placa, nombre_parqueadero, id_tipo_vehiculo,
                           fecha_ingreso, fecha_salida, total_horas, precio_total
                    FROM tickets
                    """
                )
                conn.exec_driver_sql("DROP TABLE tickets")
                conn.exec_driver_sql("ALTER TABLE tickets_backup RENAME TO tickets")
                conn.exec_driver_sql(
                    "CREATE INDEX IF NOT EXISTS ix_tickets_placa ON tickets (placa)"
                )

    conn.exec_driver_sql("DROP TABLE IF EXISTS auditoria")
    conn.exec_driver_sql("DROP TABLE IF EXISTS sesiones")
    conn.exec_driver_sql("DROP TABLE IF EXISTS usuarios")
