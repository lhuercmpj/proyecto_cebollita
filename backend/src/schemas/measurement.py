from datetime import datetime
from math import isclose
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.services.model_data import CLASS_NAMES


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class SensorReadings(BaseModel):
    """Lecturas normalizadas que devuelve la API y se guardan en la base."""

    model_config = ConfigDict(extra="forbid")

    humedad_tierra: Annotated[FiniteFloat, Field(ge=0, le=4095)]
    luz: Annotated[FiniteFloat, Field(ge=0, le=4095)]
    humedad_aire: Annotated[FiniteFloat, Field(ge=0, le=100)]
    temp_dht11: Annotated[FiniteFloat, Field(ge=-40, le=80)]
    temp_lm35: Annotated[FiniteFloat, Field(ge=-55, le=150)]


class Prediction(BaseModel):
    """Prediccion normalizada que devuelve la API y se guarda en la base."""

    model_config = ConfigDict(extra="forbid")

    class_index: Annotated[int, Field(ge=0, lt=len(CLASS_NAMES))]
    state: str
    confidence: Annotated[FiniteFloat, Field(ge=0, le=1)]
    probabilities: dict[str, float]
    model_version: str

    @model_validator(mode="after")
    def validate_prediction(self) -> "Prediction":
        expected_state = CLASS_NAMES[self.class_index]
        if self.state != expected_state:
            raise ValueError(
                f"state no coincide con class_index: se esperaba {expected_state!r}"
            )
        if set(self.probabilities) != set(CLASS_NAMES):
            raise ValueError("probabilities debe contener exactamente las cuatro clases")
        if any(not 0 <= probability <= 1 for probability in self.probabilities.values()):
            raise ValueError("cada probabilidad debe estar entre 0 y 1")
        if not isclose(sum(self.probabilities.values()), 1.0, abs_tol=1e-5):
            raise ValueError("las probabilidades deben sumar 1")
        if not isclose(self.confidence, self.probabilities[self.state], abs_tol=1e-5):
            raise ValueError("confidence debe coincidir con la probabilidad del estado")
        return self


class DeviceData(BaseModel):
    """Objeto ``datos`` enviado por el firmware de la ESP32."""

    model_config = ConfigDict(extra="forbid")

    humedad_tierra: Annotated[FiniteFloat, Field(ge=0, le=4095)]
    luz: Annotated[FiniteFloat, Field(ge=0, le=4095)]
    humedad_aire: Annotated[FiniteFloat, Field(ge=0, le=100)]
    temp_promedio: FiniteFloat
    temp_dht11: Annotated[FiniteFloat, Field(ge=-40, le=80)]
    temp_lm35: Annotated[FiniteFloat, Field(ge=-55, le=150)]
    periodo: Literal["Manana", "Tarde", "Noche"] | None

    @model_validator(mode="after")
    def validate_average_temperature(self) -> "DeviceData":
        calculated = (self.temp_dht11 + self.temp_lm35) / 2
        if not isclose(self.temp_promedio, calculated, abs_tol=0.02):
            raise ValueError("temp_promedio no coincide con las temperaturas recibidas")
        return self


class DeviceProbability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clase: Annotated[int, Field(ge=0, lt=len(CLASS_NAMES))]
    estado: str
    probabilidad: Annotated[FiniteFloat, Field(ge=0, le=1)]


class DeviceQuality(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llamadas_dht_validas: Annotated[int, Field(ge=1)]
    lecturas_lm35_validas: Annotated[int, Field(ge=1)]
    lm35_sospechoso: bool
    solo_dht_para_temperatura: Literal[False]


class DeviceMeasurement(BaseModel):
    """Contrato de respuesta exacto de ``POST /api/medir`` en la ESP32."""

    model_config = ConfigDict(extra="forbid")

    ok: Literal[True]
    clase: Annotated[int, Field(ge=0, lt=len(CLASS_NAMES))]
    estado: str
    confianza: Annotated[FiniteFloat, Field(ge=0, le=1)]
    timestamp_unix: Annotated[int, Field(ge=1_577_836_800, le=4_102_444_799)]
    duracion_ms: Annotated[int, Field(ge=0)]
    muestras: Annotated[int, Field(ge=1)]
    datos: DeviceData
    probabilidades: list[DeviceProbability]
    calidad: DeviceQuality

    @model_validator(mode="after")
    def validate_device_prediction(self) -> "DeviceMeasurement":
        if self.estado != CLASS_NAMES[self.clase]:
            raise ValueError("estado no coincide con clase")
        if len(self.probabilidades) != len(CLASS_NAMES):
            raise ValueError("probabilidades debe contener exactamente las cuatro clases")

        by_class = {item.clase: item for item in self.probabilidades}
        if set(by_class) != set(range(len(CLASS_NAMES))):
            raise ValueError("probabilidades debe contener cada clase una sola vez")
        for class_index, class_name in enumerate(CLASS_NAMES):
            if by_class[class_index].estado != class_name:
                raise ValueError("estado invalido en probabilidades")
        if not isclose(
            sum(item.probabilidad for item in self.probabilidades),
            1.0,
            abs_tol=1e-5,
        ):
            raise ValueError("las probabilidades deben sumar 1")
        if not isclose(
            self.confianza,
            by_class[self.clase].probabilidad,
            abs_tol=1e-5,
        ):
            raise ValueError("confianza debe coincidir con la probabilidad del estado")
        return self


class MeasurementRead(BaseModel):
    measurement_id: str
    plant_id: str
    source: str = "esp32"
    measured_at: datetime
    received_at: datetime
    sensors: SensorReadings
    temp_promedio: FiniteFloat
    prediction: Prediction
    backend_prediction_matches: bool


class MeasurementIngestResponse(BaseModel):
    created: bool
    measurement: MeasurementRead
