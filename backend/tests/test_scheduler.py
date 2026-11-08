import asyncio
from datetime import timedelta

from sqlalchemy import func, select

from src.db_models import JobRun, Measurement, NotificationLog, TelegramSubscriber
from src.jobs.sensor_report_job import next_run_at, run_cycle
from src.services.device_service import DeviceUnavailableError
from tests.conftest import (
    BASE_TIME,
    SAMPLE_AGUA,
    SAMPLE_BIEN,
    SAMPLE_MAL,
    FakeNotifier,
    make_payload,
)


class Clock:
    def __init__(self, start):
        self.value = start

    def __call__(self):
        return self.value

    def advance(self, minutes: float) -> None:
        self.value += timedelta(minutes=minutes)


def device_returning(samples, clock):
    """Dispositivo falso: devuelve la muestra indicada con la hora actual del reloj."""

    queue = list(samples)

    async def device(_settings):
        sample = queue.pop(0)
        if sample is None:
            raise DeviceUnavailableError("No se pudo obtener la medicion: timeout")
        return make_payload(sample, clock())

    return device


def run(coro):
    return asyncio.run(coro)


def count(session, model, *where):
    return session.scalar(select(func.count()).select_from(model).where(*where))


def test_cycle_saves_measurement_reports_and_alerts(session_factory, settings, notifier):
    clock = Clock(BASE_TIME)
    device = device_returning([SAMPLE_AGUA], clock)

    result = run(run_cycle(session_factory, settings, notifier, device, clock))

    assert result.status == "ok"
    assert result.created is True
    texts = [text for _, text in notifier.sent]
    assert len(texts) == 2
    assert texts[0].startswith("🌱 Reporte de Cebollita")
    assert "Preciso agua" in texts[0]
    assert "Alerta de riego" in texts[1]
    with session_factory() as session:
        assert count(session, Measurement) == 1
        run_row = session.scalar(select(JobRun))
        assert run_row.status == "ok"
        assert run_row.finished_at is not None


def test_alert_is_not_repeated_until_repeat_window(session_factory, settings, notifier):
    clock = Clock(BASE_TIME)
    device = device_returning([SAMPLE_AGUA] * 8, clock)

    for _ in range(6):  # 6 ciclos = 2,5 h con el mismo estado
        run(run_cycle(session_factory, settings, notifier, device, clock))
        clock.advance(30)
    alerts = [text for _, text in notifier.sent if "Alerta de riego" in text]
    assert len(alerts) == 1

    # A las 3 h de la primera alerta llega un recordatorio.
    run(run_cycle(session_factory, settings, notifier, device, clock))
    alerts = [text for _, text in notifier.sent if "Alerta de riego" in text]
    assert len(alerts) == 2
    assert "Recordatorio" in alerts[1]

    reports = [text for _, text in notifier.sent if text.startswith("🌱 Reporte")]
    assert len(reports) == 7  # el reporte de cada 30 min se envia siempre


def test_state_change_alerts_and_recovery(session_factory, settings, notifier):
    clock = Clock(BASE_TIME)
    device = device_returning([SAMPLE_AGUA, SAMPLE_MAL, SAMPLE_BIEN, SAMPLE_BIEN], clock)

    for _ in range(4):
        run(run_cycle(session_factory, settings, notifier, device, clock))
        clock.advance(30)

    non_reports = [text for _, text in notifier.sent if not text.startswith("🌱 Reporte")]
    assert len(non_reports) == 3
    assert "Alerta de riego" in non_reports[0]
    assert "no está bien" in non_reports[1]
    assert "Ya estoy mejor" in non_reports[2]


def test_device_error_does_not_create_measurement(session_factory, settings, notifier):
    clock = Clock(BASE_TIME)
    device = device_returning([None, None, SAMPLE_BIEN, None], clock)

    statuses = []
    for _ in range(4):
        statuses.append(run(run_cycle(session_factory, settings, notifier, device, clock)).status)
        clock.advance(30)

    assert statuses == ["device_error", "device_error", "ok", "device_error"]
    with session_factory() as session:
        assert count(session, Measurement) == 1
        assert count(session, JobRun, JobRun.status == "device_error") == 3
    device_warnings = [text for _, text in notifier.sent if "No pude leer mis sensores" in text]
    # Un aviso por racha de fallos: el primero y el que sigue a la recuperacion.
    assert len(device_warnings) == 2


def test_failed_alert_delivery_is_retried(session_factory, settings):
    clock = Clock(BASE_TIME)
    device = device_returning([SAMPLE_AGUA, SAMPLE_AGUA], clock)
    failing = FakeNotifier(fail_for={"1000"})

    run(run_cycle(session_factory, settings, failing, device, clock))
    assert failing.sent == []

    clock.advance(30)
    working = FakeNotifier()
    run(run_cycle(session_factory, settings, working, device, clock))
    assert any("Alerta de riego" in text for _, text in working.sent)
    with session_factory() as session:
        assert count(session, NotificationLog, NotificationLog.ok.is_(False)) == 2


def test_reports_go_to_every_active_subscriber(session_factory, settings, notifier):
    with session_factory() as session:
        session.add_all(
            [
                TelegramSubscriber(chat_id="2000", active=True, subscribed_at=BASE_TIME),
                TelegramSubscriber(chat_id="3000", active=False, subscribed_at=BASE_TIME),
            ]
        )
        session.commit()
    clock = Clock(BASE_TIME)

    run(run_cycle(session_factory, settings, notifier, device_returning([SAMPLE_BIEN], clock), clock))

    assert {chat_id for chat_id, _ in notifier.sent} == {"1000", "2000"}


def test_without_telegram_token_still_measures(session_factory, settings):
    clock = Clock(BASE_TIME)
    disabled = FakeNotifier(enabled=False)

    result = run(
        run_cycle(session_factory, settings, disabled, device_returning([SAMPLE_AGUA], clock), clock)
    )

    assert result.status == "ok"
    with session_factory() as session:
        assert count(session, Measurement) == 1


def test_next_run_does_not_catch_up_missed_reports(session_factory, settings, notifier):
    clock = Clock(BASE_TIME)
    run(run_cycle(session_factory, settings, notifier, device_returning([SAMPLE_BIEN], clock), clock))

    with session_factory() as session:
        soon = BASE_TIME + timedelta(minutes=10)
        assert next_run_at(session, settings, soon) == BASE_TIME + timedelta(minutes=30)
        # Tras 5 h apagado se ejecuta una sola vez ahora, sin recuperar los 10 omitidos.
        late = BASE_TIME + timedelta(hours=5)
        assert next_run_at(session, settings, late) == late


def test_next_run_is_now_on_first_start(session, settings):
    assert next_run_at(session, settings, BASE_TIME) == BASE_TIME
