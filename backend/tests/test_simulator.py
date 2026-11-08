import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.simulator import MeasurementRequest, measure


def test_simulator_requires_sensor_key() -> None:
    with pytest.raises(HTTPException) as exc_info:
        measure(request=None, sample_index=0, x_api_key=None)

    assert exc_info.value.status_code == 401


def test_simulator_returns_known_sample() -> None:
    measurement = measure(
        request=MeasurementRequest(timestamp_unix=1_794_142_800),
        sample_index=0,
        x_api_key=get_settings().sensor_api_key,
    )

    assert measurement.datos.humedad_tierra == 930.1
    assert measurement.estado == "Preciso agua"
    assert measurement.clase == 2
    assert measurement.timestamp_unix == 1_794_142_800
    assert measurement.calidad.solo_dht_para_temperatura is False

