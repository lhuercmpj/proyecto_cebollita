from src.services.ingest_service import store_device_measurement
from src.services.measurement_service import latest_measurement
from tests.conftest import BASE_TIME, SAMPLE_AGUA, make_payload


def test_same_payload_is_not_duplicated(session, settings):
    payload = make_payload(SAMPLE_AGUA, BASE_TIME)

    first, created_first = store_device_measurement(session, payload, settings)
    second, created_second = store_device_measurement(session, payload, settings)

    assert created_first is True
    assert created_second is False
    assert first.measurement_id == second.measurement_id
    assert latest_measurement(session).measurement_id == first.measurement_id
    assert first.backend_prediction_matches is True


def test_simulator_readings_are_marked_and_hidden_once_real_data_exists(session, settings):
    from datetime import timedelta

    from src.services.measurement_service import latest_measurement, measurements_between

    settings.sensor_device_url = "http://simulator:8081"
    sim, _ = store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME), settings)
    assert sim.source == "simulador"
    # Solo simulador (modo demo): se usa igual.
    assert latest_measurement(session).source == "simulador"

    settings.sensor_device_url = "http://192.168.68.109"
    real, _ = store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME - timedelta(hours=1)), settings)
    assert real.source == "esp32"
    # Con datos reales, el simulador queda afuera aunque sea mas nuevo.
    assert latest_measurement(session).source == "esp32"
    window = measurements_between(session, BASE_TIME - timedelta(days=1), BASE_TIME + timedelta(days=1))
    assert {m.source for m in window} == {"esp32"}
