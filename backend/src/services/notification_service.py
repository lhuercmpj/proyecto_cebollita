"""Destinatarios, envio y registro de mensajes automaticos."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db_models.notifications import NotificationLog, TelegramSubscriber
from src.schemas.measurement import MeasurementRead
from src.services.alert_service import decide_alert, get_alert_state, mark_evaluated
from src.services.report_service import (
    format_alert,
    format_device_error,
    format_recovery,
    format_report,
)
from src.services.telegram_client import Notifier

logger = logging.getLogger(__name__)


@dataclass
class BroadcastResult:
    recipients: int
    delivered: int

    @property
    def any_delivered(self) -> bool:
        return self.delivered > 0


def recipients(session: Session, settings: Settings) -> list[str]:
    chat_ids = list(
        session.scalars(
            select(TelegramSubscriber.chat_id).where(TelegramSubscriber.active.is_(True))
        )
    )
    if settings.telegram_chat_id and settings.telegram_chat_id not in chat_ids:
        chat_ids.append(settings.telegram_chat_id)
    return chat_ids


async def broadcast(
    session: Session,
    settings: Settings,
    notifier: Notifier,
    text: str,
    kind: str,
) -> BroadcastResult:
    if not notifier.enabled:
        logger.warning("Telegram no configurado: no se envia el mensaje %s", kind)
        return BroadcastResult(recipients=0, delivered=0)

    targets = recipients(session, settings)
    if not targets:
        logger.info("No hay chats suscriptos: nadie recibe el mensaje %s", kind)
    delivered = 0
    for chat_id in targets:
        error: str | None = None
        try:
            await notifier.send(chat_id, text)
            delivered += 1
        except Exception as exc:  # noqa: BLE001 - se registra y se sigue con el resto
            error = str(exc)
            logger.warning("No se pudo enviar %s a %s: %s", kind, chat_id, error)
        session.add(
            NotificationLog(
                sent_at=datetime.now(UTC),
                chat_id=chat_id,
                kind=kind,
                ok=error is None,
                text=text,
                error=error,
            )
        )
    session.commit()
    return BroadcastResult(recipients=len(targets), delivered=delivered)


async def notify_measurement(
    session: Session,
    measurement: MeasurementRead,
    settings: Settings,
    notifier: Notifier,
    include_report: bool,
    now: datetime | None = None,
) -> dict[str, str]:
    """Envia el reporte (opcional) y evalua la alerta de una medicion nueva."""

    summary: dict[str, str] = {}
    if include_report:
        result = await broadcast(
            session, settings, notifier, format_report(measurement, settings, now), "report"
        )
        summary["report"] = f"{result.delivered}/{result.recipients}"

    row = get_alert_state(session, settings.plant_id)
    decision = decide_alert(row, measurement, settings, now)
    delivered = False
    if decision.kind in ("alert", "reminder"):
        text = format_alert(measurement, settings, reminder=decision.kind == "reminder")
        delivered = (await broadcast(session, settings, notifier, text, "alert")).any_delivered
    elif decision.kind == "recovery":
        delivered = (
            await broadcast(
                session, settings, notifier, format_recovery(measurement, settings), "recovery"
            )
        ).any_delivered
    mark_evaluated(session, row, measurement, decision, delivered, now)
    summary["alert"] = f"{decision.kind} ({decision.reason})"
    return summary


async def notify_device_failure(
    session: Session,
    settings: Settings,
    notifier: Notifier,
) -> int:
    """Cuenta el fallo y avisa solo en el primero de una racha."""

    row = get_alert_state(session, settings.plant_id)
    row.consecutive_failures = (row.consecutive_failures or 0) + 1
    session.commit()
    if row.consecutive_failures == 1:
        await broadcast(session, settings, notifier, format_device_error(settings), "device_error")
    return row.consecutive_failures


def reset_device_failures(session: Session, settings: Settings) -> None:
    row = get_alert_state(session, settings.plant_id)
    if row.consecutive_failures:
        row.consecutive_failures = 0
        session.commit()
