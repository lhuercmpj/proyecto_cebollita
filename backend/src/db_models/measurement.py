from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Measurement(Base):
    __tablename__ = "measurements"
    # Una medicion queda identificada por la planta y el instante en que la
    # placa la tomo: repetir el mismo payload no crea una fila nueva.
    __table_args__ = (
        UniqueConstraint("plant_id", "measured_at", name="uq_measurement_plant_time"),
    )

    measurement_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    plant_id: Mapped[str] = mapped_column(String(50), index=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # esp32 | historico_tarea2 (procedencia de la lectura)
    source: Mapped[str] = mapped_column(String(30), default="esp32", index=True)

    humedad_tierra: Mapped[float] = mapped_column(Float)
    luz: Mapped[float] = mapped_column(Float)
    humedad_aire: Mapped[float] = mapped_column(Float)
    temp_dht11: Mapped[float] = mapped_column(Float)
    temp_lm35: Mapped[float] = mapped_column(Float)
    temp_promedio: Mapped[float] = mapped_column(Float)

    predicted_class: Mapped[int] = mapped_column(Integer)
    predicted_state: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    probabilities: Mapped[dict[str, float]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(50))
    backend_prediction_matches: Mapped[bool] = mapped_column(Boolean)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON)

