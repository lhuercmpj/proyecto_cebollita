from datetime import timedelta

from src.services.ingest_service import store_device_measurement
from src.services.report_service import format_report, is_stale
from tests.conftest import BASE_TIME, SAMPLE_AGUA, make_payload


def test_report_uses_stored_numbers_and_local_time(session, settings):
    measurement, _ = store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME), settings)

    text = format_report(measurement, settings, now=BASE_TIME)

    assert "08/11/2026 12:00" in text  # 15:00 UTC = 12:00 en Montevideo
    assert "20,4 °C" in text
    assert "930" in text and "sin calibrar" in text
    assert "%" not in text.split("Humedad de la tierra")[1].split("\n")[0]
    assert "atrasada" not in text


def test_stale_report_is_flagged(session, settings):
    measurement, _ = store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME), settings)
    later = BASE_TIME + timedelta(minutes=41)

    assert is_stale(measurement, settings, later)
    assert "atrasada" in format_report(measurement, settings, now=later)
