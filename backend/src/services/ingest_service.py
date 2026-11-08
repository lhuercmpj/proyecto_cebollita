"""Punto unico para guardar una medicion recibida del dispositivo."""

from math import isclose

from sqlalchemy.orm import Session

from src.config import Settings
from src.schemas.measurement import DeviceMeasurement, MeasurementRead
from src.services.measurement_service import save_measurement
from src.services.prediction_service import predict


def prediction_matches(payload: DeviceMeasurement) -> bool:
    """Compara la prediccion del firmware con la implementacion de referencia."""

    sensors = payload.datos
    backend_prediction = predict(
        humedad_tierra=sensors.humedad_tierra,
        luz=sensors.luz,
        humedad_aire=sensors.humedad_aire,
        temp_promedio=sensors.temp_promedio,
    )
    device_probabilities = {item.estado: item.probabilidad for item in payload.probabilidades}
    return backend_prediction.class_index == payload.clase and all(
        isclose(
            backend_prediction.probabilities[class_name],
            device_probabilities[class_name],
            abs_tol=1e-5,
        )
        for class_name in backend_prediction.probabilities
    )


def store_device_measurement(
    session: Session,
    payload: DeviceMeasurement,
    settings: Settings,
) -> tuple[MeasurementRead, bool]:
    return save_measurement(
        session,
        payload,
        backend_prediction_matches=prediction_matches(payload),
        plant_id=settings.plant_id,
    )
