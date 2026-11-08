from src.simulator import MeasurementRequest, measure


def test_simulator_returns_known_sample() -> None:
    measurement = measure(
        request=MeasurementRequest(timestamp_unix=1_794_142_800),
        sample_index=0,
    )

    assert measurement.datos.humedad_tierra == 930.1
    assert measurement.estado == "Preciso agua"
    assert measurement.clase == 2
    assert measurement.timestamp_unix == 1_794_142_800
    assert measurement.calidad.solo_dht_para_temperatura is False

