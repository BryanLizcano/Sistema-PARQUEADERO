from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./parqueadero.db"

# connect_args={"check_same_thread": False, "timeout": 5.0} optimiza concurrencia local en SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 5.0},
)


@event.listens_for(engine, "connect")
def _configure_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    # Modo WAL y límite de caché de 8 MB evitan bloqueos lectura/escritura y cuidan los 4 GB de RAM
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=5000;")
        cursor.execute("PRAGMA cache_size=-8000;")
        cursor.execute("PRAGMA foreign_keys=ON;")
    finally:
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
