"""Medicion automatica y reporte a Telegram cada ``REPORT_INTERVAL_MINUTES``.

Ejecutar UNA sola instancia como proceso aparte:

    python -m src.jobs.sensor_report_job

En PostgreSQL se toma un advisory lock: si ya hay otra instancia activa, esta
termina sin hacer nada (evita reportes y alertas duplicados).
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings, get_settings
from src.database import as_utc
from src.db_models.notifications import JobRun
from src.schemas.measurement import DeviceMeasurement
from src.services.device_service import DeviceUnavailableError, request_measurement
from src.services.ingest_service import store_device_measurement
from src.services.notification_service import (
    notify_device_failure,
    notify_measurement,
    reset_device_failures,
)
from src.services.telegram_client import Notifier, TelegramNotifier

logger = logging.getLogger("cebollita.scheduler")

JOB_NAME = "sensor_report"
# Clave fija del advisory lock de PostgreSQL para este programador.
ADVISORY_LOCK_KEY = 0x0CEB0111

DeviceCall = Callable[[Settings], Awaitable[DeviceMeasurement]]


@dataclass
class CycleResult:
    status: str
    measurement_id: str | None = None
    created: bool | None = None
    detail: str = ""


async def _default_device(settings: Settings) -> DeviceMeasurement:
    return await request_measurement(settings)


async def run_cycle(
    session_factory: sessionmaker[Session],
    settings: Settings,
    notifier: Notifier,
    device: DeviceCall = _default_device,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CycleResult:
    """Una ejecucion: pedir medicion, guardarla, reportar y evaluar alertas.

    Si el dispositivo falla no se genera ninguna medicion: solo se registra el
    error. No se reintenta ``POST /api/medir`` porque cada llamada mide de nuevo.
    """

    with session_factory() as session:
        run = JobRun(job_name=JOB_NAME, started_at=now(), status="running")
        session.add(run)
        session.commit()

        try:
            payload = await device(settings)
        except DeviceUnavailableError as exc:
            failures = await notify_device_failure(session, settings, notifier)
            result = CycleResult(status="device_error", detail=f"{exc} (fallos seguidos: {failures})")
            logger.warning("Medicion fallida: %s", result.detail)
        except Exception as exc:  # noqa: BLE001 - el programador no debe caerse
            result = CycleResult(status="error", detail=f"{type(exc).__name__}: {exc}")
            logger.exception("Error inesperado al pedir la medicion")
        else:
            try:
                measurement, created = store_device_measurement(session, payload, settings)
                reset_device_failures(session, settings)
                summary = await notify_measurement(
                    session, measurement, settings, notifier, include_report=True, now=now()
                )
                result = CycleResult(
                    status="ok",
                    measurement_id=measurement.measurement_id,
                    created=created,
                    detail=f"estado={measurement.prediction.state}; {summary}",
                )
                logger.info("Medicion %s guardada: %s", measurement.measurement_id, result.detail)
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                result = CycleResult(status="error", detail=f"{type(exc).__name__}: {exc}")
                logger.exception("Error al guardar o notificar la medicion")

        run = session.get(JobRun, run.id)
        run.status = result.status
        run.measurement_id = result.measurement_id
        run.detail = result.detail[:2000]
        run.finished_at = now()
        session.commit()
        return result


def next_run_at(session: Session, settings: Settings, now: datetime) -> datetime:
    """Proxima ejecucion segun la ultima registrada.

    Al reiniciar no se recuperan los reportes omitidos: si ya paso el intervalo
    se ejecuta una sola vez ahora y se sigue con el ritmo normal.
    """

    last_started = session.scalar(
        select(JobRun.started_at)
        .where(JobRun.job_name == JOB_NAME)
        .order_by(JobRun.started_at.desc())
        .limit(1)
    )
    if last_started is None:
        return now
    candidate = as_utc(last_started) + timedelta(minutes=settings.report_interval_minutes)
    return max(candidate, now)


def _acquire_lock(connection: Connection) -> bool:
    if connection.dialect.name != "postgresql":
        return True
    return bool(
        connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": ADVISORY_LOCK_KEY}).scalar()
    )


async def run_forever(settings: Settings | None = None) -> None:
    from src.database import SessionLocal, create_tables, engine

    settings = settings or get_settings()
    create_tables()
    notifier = TelegramNotifier(settings.telegram_bot_token)
    if not notifier.enabled:
        logger.warning("TELEGRAM_BOT_TOKEN vacio: se mide y guarda, pero no se envian mensajes")

    # La conexion queda abierta mientras vive el proceso para conservar el lock.
    with engine.connect() as lock_connection:
        if not _acquire_lock(lock_connection):
            logger.error("Ya hay otro programador activo; esta instancia termina.")
            return
        lock_connection.commit()
        logger.info(
            "Programador iniciado: cada %s min contra %s",
            settings.report_interval_minutes,
            settings.sensor_device_url,
        )
        while True:
            with SessionLocal() as session:
                current = datetime.now(UTC)
                target = next_run_at(session, settings, current)
            wait_seconds = (target - current).total_seconds()
            if wait_seconds > 0:
                logger.info("Proxima medicion: %s UTC", target.isoformat(timespec="seconds"))
                await asyncio.sleep(wait_seconds)
            await run_cycle(SessionLocal, settings, notifier)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # sus logs incluyen la URL con el token
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        logger.info("Programador detenido")


if __name__ == "__main__":
    main()
