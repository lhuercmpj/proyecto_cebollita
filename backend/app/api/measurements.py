from math import isclose
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import verify_app_api_key
from app.config import get_settings
from app.database import get_session
from app.schemas.measurement import (
    DeviceMeasurement,
    MeasurementIngestResponse,
    MeasurementRead,
)
from app.services.device_service import DeviceUnavailableError, request_measurement
from app.services.measurement_service import (
    latest_measurement,
    list_measurements,
    save_measurement,
)
from app.services.prediction_service import predict

router = APIRouter(prefix="/api/measurements", tags=["measurements"])
SessionDependency = Annotated[Session, Depends(get_session)]


def prediction_matches(payload: DeviceMeasurement) -> bool:
    sensors = payload.datos
    backend_prediction = predict(
        humedad_tierra=sensors.humedad_tierra,
        luz=sensors.luz,
        humedad_aire=sensors.humedad_aire,
        temp_promedio=sensors.temp_promedio,
    )
    device_probabilities = {
        item.estado: item.probabilidad for item in payload.probabilidades
    }
    return (
        backend_prediction.class_index == payload.clase
        and all(
            isclose(
                backend_prediction.probabilities[class_name],
                device_probabilities[class_name],
                abs_tol=1e-5,
            )
            for class_name in backend_prediction.probabilities
        )
    )


@router.post(
    "/request",
    response_model=MeasurementIngestResponse,
    dependencies=[Depends(verify_app_api_key)],
)
async def request_and_store_measurement(
    session: SessionDependency,
    sample_index: Annotated[int | None, Query(ge=0, le=11)] = None,
) -> MeasurementIngestResponse:
    """Solicita una medicion a la ESP32 (o al simulador) y la persiste."""

    try:
        payload = await request_measurement(get_settings(), sample_index=sample_index)
    except DeviceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    measurement, created = save_measurement(
        session,
        payload,
        backend_prediction_matches=prediction_matches(payload),
    )
    return MeasurementIngestResponse(created=created, measurement=measurement)


@router.post(
    "",
    response_model=MeasurementIngestResponse,
    dependencies=[Depends(verify_app_api_key)],
)
def ingest_measurement(
    payload: DeviceMeasurement,
    session: SessionDependency,
) -> MeasurementIngestResponse:
    """Entrada alternativa para una ESP32 configurada en modo push."""

    measurement, created = save_measurement(
        session,
        payload,
        backend_prediction_matches=prediction_matches(payload),
    )
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

