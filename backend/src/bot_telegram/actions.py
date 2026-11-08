"""Logica de los comandos del bot, independiente de python-telegram-bot."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.config import Settings
from src.db_models.notifications import TelegramSubscriber
from src.services.measurement_service import latest_measurement, measurements_between
from src.services.personality import GREETING
from src.services.rag_service import summarize_window
from src.services.report_service import format_report


def subscribe(session: Session, settings: Settings, chat_id: str, username: str | None) -> str:
    allowed = settings.allowed_chat_ids
    if allowed and chat_id not in allowed:
        return (
            "¡Hola! Soy Cebollita 🌿 Por ahora solo mando reportes a los chats autorizados. "
            f"Pedile a quien me cuida que agregue este chat ({chat_id}) a TELEGRAM_ALLOWED_CHAT_IDS."
        )
    row = session.get(TelegramSubscriber, chat_id)
    if row is None:
        session.add(
            TelegramSubscriber(
                chat_id=chat_id,
                username=username,
                active=True,
                subscribed_at=datetime.now(UTC),
            )
        )
    else:
        row.active = True
        row.username = username
    session.commit()
    return GREETING


def unsubscribe(session: Session, chat_id: str) -> str:
    row = session.get(TelegramSubscriber, chat_id)
    if row is not None and row.active:
        row.active = False
        session.commit()
    return "Listo, dejo de mandarte reportes y alertas 🥲 Si me extrañás, escribí /start."


def status_text(session: Session, settings: Settings, now: datetime | None = None) -> str:
    measurement = latest_measurement(session, settings.plant_id)
    if measurement is None:
        return "Todavía no tengo mediciones guardadas 🌱 En cuanto la maceta mida, te cuento."
    return format_report(measurement, settings, now)


def history_text(session: Session, settings: Settings, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    day = measurements_between(session, now - timedelta(hours=24), now, settings.plant_id)
    week = measurements_between(session, now - timedelta(days=7), now, settings.plant_id)
    if not week:
        return "No tengo mediciones de la última semana 🌱"
    return (
        "📈 Mi historial\n\n"
        + summarize_window(day, "Últimas 24 horas", settings)
        + "\n\n"
        + summarize_window(week, "Últimos 7 días", settings)
        + "\n\nHumedad de tierra y luz son lecturas crudas (0–4095); en la luz, más alto = más oscuro."
    )
