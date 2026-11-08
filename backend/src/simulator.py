from datetime import UTC, datetime
from itertools import count
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Body, FastAPI, Query
from pydantic import BaseModel, Field

from src.config import get_settings
from src.schemas.measurement import (
    DeviceData,
    DeviceMeasurement,
    DeviceProbability,
    DeviceQuality,
)
from src.services.model_data import TEST_X
from src.services.prediction_service import predict

app = FastAPI(title="Cebollita ESP32 Simulator", version="0.2.0")
settings = get_settings()
counter = count()
counter_lock = Lock()
started_at = monotonic()


class MeasurementRequest(BaseModel):
    timestamp_unix: int | None = Field(default=None, ge=1_577_836_800, le=4_102_444_799)


@app.get("/api/salud", tags=["system"])
def health() -> dict[str, str | int | bool]:
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
) -> DeviceMeasurement:
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
