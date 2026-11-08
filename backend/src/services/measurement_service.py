from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db_models.measurement import Measurement
from src.schemas.measurement import DeviceMeasurement, MeasurementRead
from src.services.model_data import MODEL_VERSION


def to_read(model: Measurement) -> MeasurementRead:
    return MeasurementRead(
        measurement_id=model.measurement_id,
        plant_id=model.plant_id,
        measured_at=model.measured_at,
        received_at=model.received_at,
        sensors={
            "humedad_tierra": model.humedad_tierra,
            "luz": model.luz,
            "humedad_aire": model.humedad_aire,
            "temp_dht11": model.temp_dht11,
            "temp_lm35": model.temp_lm35,
        },
        temp_promedio=model.temp_promedio,
        prediction={
            "class_index": model.predicted_class,
            "state": model.predicted_state,
            "confidence": model.confidence,
            "probabilities": model.probabilities,
            "model_version": model.model_version,
        },
        backend_prediction_matches=model.backend_prediction_matches,
    )


def save_measurement(
    session: Session,
    payload: DeviceMeasurement,
    backend_prediction_matches: bool,
) -> tuple[MeasurementRead, bool]:
    measurement_id = f"esp32-{uuid4()}"
    sensors = payload.datos
    probabilities = {
        item.estado: item.probabilidad for item in payload.probabilidades
    }
    model = Measurement(
        measurement_id=measurement_id,
        plant_id="cebollita",
        measured_at=datetime.fromtimestamp(payload.timestamp_unix, tz=UTC),
        received_at=datetime.now(UTC),
        humedad_tierra=sensors.humedad_tierra,
        luz=sensors.luz,
        humedad_aire=sensors.humedad_aire,
        temp_dht11=sensors.temp_dht11,
        temp_lm35=sensors.temp_lm35,
        temp_promedio=sensors.temp_promedio,
        predicted_class=payload.clase,
        predicted_state=payload.estado,
        confidence=payload.confianza,
        probabilities=probabilities,
        model_version=MODEL_VERSION,
        backend_prediction_matches=backend_prediction_matches,
        raw_payload=payload.model_dump(mode="json"),
    )
    session.add(model)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise
    session.refresh(model)
    return to_read(model), True


def latest_measurement(session: Session) -> MeasurementRead | None:
    statement = select(Measurement).order_by(Measurement.measured_at.desc()).limit(1)
    model = session.scalar(statement)
    return None if model is None else to_read(model)


def list_measurements(session: Session, limit: int) -> list[MeasurementRead]:
    statement = select(Measurement).order_by(Measurement.measured_at.desc()).limit(limit)
    return [to_read(model) for model in session.scalars(statement)]

