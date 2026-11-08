from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.api.chat import router as chat_router
from src.api.measurements import router as measurements_router
from src.config import get_settings
from src.database import SessionLocal, create_tables
from src.services.model_data import MODEL_VERSION


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
app.include_router(measurements_router)
app.include_router(chat_router)


@app.get("/health", tags=["system"])
def health() -> dict[str, str | bool]:
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
        "gemini_configured": bool(settings.gemini_api_key),
        "telegram_configured": bool(settings.telegram_bot_token),
    }
