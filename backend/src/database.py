from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables(bind: Engine | None = None) -> None:
    """Crea la extension pgvector (si corresponde) y las tablas faltantes.

    ``create_all`` no altera tablas existentes: si cambia el esquema durante el
    desarrollo, recrear la base con ``docker compose down -v``.
    """

    import src.db_models  # noqa: F401 - registra todas las tablas

    target = bind or engine
    if target.dialect.name == "postgresql":
        with target.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=target)


def get_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def as_utc(value: datetime) -> datetime:
    """Normaliza fechas: SQLite devuelve fechas sin zona horaria."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
