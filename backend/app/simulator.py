from datetime import UTC, datetime
from hmac import compare_digest
from itertools import count
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Body, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas.measurement import (
    DeviceData,
    DeviceMeasurement,
    DeviceProbability,
    DeviceQuality,
)
from app.services.model_data import TEST_X
from app.services.prediction_service import predict

app = FastAPI(title="Cebollita ESP32 Simulator", version="0.2.0")
settings = get_settings()
counter = count()
counter_lock = Lock()
started_at = monotonic()


class MeasurementRequest(BaseModel):
    timestamp_unix: int | None = Field(default=None, ge=1_577_836_800, le=4_102_444_799)


def authorize(x_api_key: str | None) -> None:
    if x_api_key is None or not compare_digest(x_api_key, settings.sensor_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clave invalida",
        )


@app.get("/api/salud", tags=["system"])
def health(
    x_api_key: Annotated[str | None, Header()] = None,
) -> dict[str, str | int | bool]:
    authorize(x_api_key)
    return {
        "ok": True,
        "ip": "simulator",
        "hora_disponible": True,
        "usa_periodo": False,
        "uptime_ms": int((monotonic() - started_at) * 1000),
    }


@app.post("/api/medir", response_model=DeviceMeasurement, tags=["device"])
def measure(
    request: Annotated[MeasurementRequest | None, Body()] = None,
    sample_index: Annotated[
        int | None,
        Query(ge=0, le=len(TEST_X) - 1),
    ] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> DeviceMeasurement:
    authorize(x_api_key)

    with counter_lock:
        sequence = next(counter)
    selected_index = sequence % len(TEST_X) if sample_index is None else sample_index
    humedad_tierra, luz, humedad_aire, temp_promedio = TEST_X[selected_index]
    prediction = predict(
        humedad_tierra=humedad_tierra,
        luz=luz,
        humedad_aire=humedad_aire,
        temp_promedio=temp_promedio,
    )
    timestamp_unix = (
        int(datetime.now(UTC).timestamp())
        if request is None or request.timestamp_unix is None
        else request.timestamp_unix
    )

    return DeviceMeasurement(
        ok=True,
        clase=prediction.class_index,
        estado=prediction.state,
        confianza=prediction.confidence,
        timestamp_unix=timestamp_unix,
        duracion_ms=9_000,
        muestras=30,
        datos=DeviceData(
            humedad_tierra=humedad_tierra,
            luz=luz,
            humedad_aire=humedad_aire,
            temp_promedio=temp_promedio,
            temp_dht11=temp_promedio - 0.01,
            temp_lm35=temp_promedio + 0.01,
            periodo=None,
        ),
        probabilidades=[
            DeviceProbability(
                clase=class_index,
                estado=state,
                probabilidad=probability,
            )
            for class_index, (state, probability) in enumerate(
                prediction.probabilities.items()
            )
        ],
        calidad=DeviceQuality(
            llamadas_dht_validas=30,
            lecturas_lm35_validas=30,
            lm35_sospechoso=False,
            solo_dht_para_temperatura=False,
        ),
    )
