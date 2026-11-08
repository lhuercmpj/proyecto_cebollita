from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database import SessionLocal, get_session
from src.schemas.measurement import (
    DeviceMeasurement,
    MeasurementIngestResponse,
    MeasurementRead,
)
from src.services.device_service import DeviceUnavailableError, request_measurement
from src.services.ingest_service import prediction_matches, store_device_measurement
from src.services.measurement_service import latest_measurement, list_measurements
from src.services.notification_service import notify_measurement
from src.services.telegram_client import TelegramNotifier

router = APIRouter(prefix="/api/measurements", tags=["measurements"])
SessionDependency = Annotated[Session, Depends(get_session)]

__all__ = ["prediction_matches", "router"]


async def evaluate_alerts(measurement: MeasurementRead) -> None:
    """Las alertas se evaluan al llegar la lectura, sin esperar al reporte."""

    settings = get_settings()
    with SessionLocal() as session:
        await notify_measurement(
            session,
            measurement,
            settings,
            TelegramNotifier(settings.telegram_bot_token),
            include_report=False,
        )


@router.post(
    "/request",
    response_model=MeasurementIngestResponse,
)
async def request_and_store_measurement(
    session: SessionDependency,
    background_tasks: BackgroundTasks,
    sample_index: Annotated[int | None, Query(ge=0, le=11)] = None,
) -> MeasurementIngestResponse:
    """Solicita una medicion a la ESP32 (o al simulador) y la persiste."""

    settings = get_settings()
    try:
        payload = await request_measurement(settings, sample_index=sample_index)
    except DeviceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    measurement, created = store_device_measurement(session, payload, settings)
    if created:
        background_tasks.add_task(evaluate_alerts, measurement)
    return MeasurementIngestResponse(created=created, measurement=measurement)


@router.post(
    "",
    response_model=MeasurementIngestResponse,
)
def ingest_measurement(
    payload: DeviceMeasurement,
    session: SessionDependency,
    background_tasks: BackgroundTasks,
) -> MeasurementIngestResponse:
    """Entrada alternativa para una ESP32 configurada en modo push."""

    measurement, created = store_device_measurement(session, payload, get_settings())
    if created:
        background_tasks.add_task(evaluate_alerts, measurement)
    return MeasurementIngestResponse(created=created, measurement=measurement)


@router.get("/latest", response_model=MeasurementRead)
def get_latest_measurement(session: SessionDependency) -> MeasurementRead:
    measurement = latest_measurement(session)
    if measurement is None:
        raise HTTPException(status_code=404, detail="Todavia no hay mediciones")
    return measurement


@router.get("", response_model=list[MeasurementRead])
def get_measurements(
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[MeasurementRead]:
    return list_measurements(session, limit=limit)

