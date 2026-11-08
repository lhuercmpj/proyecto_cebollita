import pytest
from pydantic import ValidationError

from src.schemas.measurement import DeviceMeasurement
from src.services.model_data import CLASS_NAMES, TEST_X
from src.services.prediction_service import predict


def valid_payload() -> dict[str, object]:
    humedad_tierra, luz, humedad_aire, temp_promedio = TEST_X[0]
    prediction = predict(*TEST_X[0])
    return {
        "ok": True,
        "clase": prediction.class_index,
        "estado": prediction.state,
        "confianza": prediction.confidence,
        "timestamp_unix": 1_794_142_800,
        "duracion_ms": 9_000,
        "muestras": 30,
        "datos": {
            "humedad_tierra": humedad_tierra,
            "luz": luz,
            "humedad_aire": humedad_aire,
            "temp_promedio": temp_promedio,
            "temp_dht11": temp_promedio - 0.01,
            "temp_lm35": temp_promedio + 0.01,
            "periodo": None,
        },
        "probabilidades": [
            {
                "clase": class_index,
                "estado": state,
                "probabilidad": probability,
            }
            for class_index, (state, probability) in enumerate(
                prediction.probabilities.items()
            )
        ],
        "calidad": {
            "llamadas_dht_validas": 30,
            "lecturas_lm35_validas": 30,
            "lm35_sospechoso": False,
            "solo_dht_para_temperatura": False,
        },
    }


def test_accepts_exact_firmware_measurement() -> None:
    measurement = DeviceMeasurement.model_validate(valid_payload())

    assert measurement.estado == "Preciso agua"
    assert measurement.datos.temp_lm35 is not None


def test_rejects_missing_lm35_reading() -> None:
    payload = valid_payload()
    payload["datos"]["temp_lm35"] = None  # type: ignore[index]

    with pytest.raises(ValidationError, match="temp_lm35"):
        DeviceMeasurement.model_validate(payload)


def test_rejects_incorrect_average_temperature() -> None:
    payload = valid_payload()
    payload["datos"]["temp_promedio"] = 99.0  # type: ignore[index]

    with pytest.raises(ValidationError, match="temp_promedio"):
        DeviceMeasurement.model_validate(payload)


def test_rejects_mismatched_prediction_state() -> None:
    payload = valid_payload()
    payload["estado"] = CLASS_NAMES[0]

    with pytest.raises(ValidationError, match="estado no coincide"):
        DeviceMeasurement.model_validate(payload)
