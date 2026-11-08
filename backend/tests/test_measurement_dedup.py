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
