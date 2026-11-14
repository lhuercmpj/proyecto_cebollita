from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.database import as_utc
from src.db_models.measurement import Measurement
from src.schemas.measurement import DeviceMeasurement, MeasurementRead
from src.services.model_data import MODEL_VERSION

PLANT_ID = "cebollita"


def to_read(model: Measurement) -> MeasurementRead:
    return MeasurementRead(
        measurement_id=model.measurement_id,
        plant_id=model.plant_id,
        source=model.source,
        measured_at=as_utc(model.measured_at),
        received_at=as_utc(model.received_at),
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


def measurement_id_for(plant_id: str, timestamp_unix: int, source: str = "esp32") -> str:
    """Identificador deterministico: el mismo instante de medicion da el mismo id."""

    return f"{source}-{plant_id}-{timestamp_unix}"


def find_measurement(session: Session, plant_id: str, measured_at: datetime) -> Measurement | None:
    statement = select(Measurement).where(
        Measurement.plant_id == plant_id,
        Measurement.measured_at == measured_at,
    )
    return session.scalar(statement)


def save_measurement(
    session: Session,
    payload: DeviceMeasurement,
    backend_prediction_matches: bool,
    plant_id: str = PLANT_ID,
    source: str = "esp32",
) -> tuple[MeasurementRead, bool]:
    """Guarda una medicion. Devuelve ``(medicion, creada)``.

    Si ya existe una medicion de la misma planta en el mismo instante (por
    ejemplo, la placa reenvio el mismo JSON), se devuelve la existente con
    ``creada=False`` en lugar de duplicarla.
    """

    measured_at = datetime.fromtimestamp(payload.timestamp_unix, tz=UTC)
    existing = find_measurement(session, plant_id, measured_at)
    if existing is not None:
        return to_read(existing), False

    sensors = payload.datos
    probabilities = {item.estado: item.probabilidad for item in payload.probabilidades}
    model = Measurement(
        measurement_id=measurement_id_for(plant_id, payload.timestamp_unix, source),
        plant_id=plant_id,
        source=source,
        measured_at=measured_at,
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
        # Otro proceso guardo la misma medicion en paralelo.
        session.rollback()
        existing = find_measurement(session, plant_id, measured_at)
        if existing is None:
            raise
        return to_read(existing), False
    session.refresh(model)
    return to_read(model), True


def _real_sources(session: Session, plant_id: str):
    """Si hay lecturas reales (ESP32 o historico), se ignoran las del simulador."""

    has_real = session.scalar(
        select(Measurement.measurement_id)
        .where(Measurement.plant_id == plant_id, Measurement.source != "simulador")
        .limit(1)
    )
    return Measurement.source != "simulador" if has_real else Measurement.source.is_not(None)


def latest_measurement(session: Session, plant_id: str = PLANT_ID) -> MeasurementRead | None:
    statement = (
        select(Measurement)
        .where(Measurement.plant_id == plant_id, _real_sources(session, plant_id))
        .order_by(Measurement.measured_at.desc())
        .limit(1)
    )
    model = session.scalar(statement)
    return None if model is None else to_read(model)


def list_measurements(
    session: Session,
    limit: int,
    plant_id: str = PLANT_ID,
) -> list[MeasurementRead]:
    statement = (
        select(Measurement)
        .where(Measurement.plant_id == plant_id, _real_sources(session, plant_id))
        .order_by(Measurement.measured_at.desc())
        .limit(limit)
    )
    return [to_read(model) for model in session.scalars(statement)]


def measurements_between(
    session: Session,
    start: datetime,
    end: datetime,
    plant_id: str = PLANT_ID,
) -> list[MeasurementRead]:
    """Mediciones en ``[start, end]`` ordenadas de la mas antigua a la mas nueva."""

    statement = (
        select(Measurement)
        .where(
            Measurement.plant_id == plant_id,
            _real_sources(session, plant_id),
            Measurement.measured_at >= start,
            Measurement.measured_at <= end,
        )
        .order_by(Measurement.measured_at.asc())
    )
    return [to_read(model) for model in session.scalars(statement)]
