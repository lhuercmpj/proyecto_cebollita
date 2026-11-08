from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import app.db_models  # noqa: F401 - registra las tablas en Base.metadata
from app.api.measurements import router as measurements_router
from app.config import get_settings
from app.database import SessionLocal, create_tables
from app.services.model_data import MODEL_VERSION


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(measurements_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    database_status = "available"
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_status = "unavailable"

    return {
        "status": "ok" if database_status == "available" else "degraded",
        "database": database_status,
        "model": "loaded",
        "model_version": MODEL_VERSION,
        "sensor_device_url": settings.sensor_device_url,
    }

