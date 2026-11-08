from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class TelegramSubscriber(Base):
    """Chats que hicieron /start y reciben reportes y alertas."""

    __tablename__ = "telegram_subscribers"

    chat_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertState(Base):
    """Ultima alerta enviada por planta, para no repetirla continuamente."""

    __tablename__ = "alert_states"

    plant_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    last_alert_state: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_measurement_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Cantidad de fallos seguidos al pedir una medicion al dispositivo.
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)


class JobRun(Base):
    """Registro de cada ejecucion del programador de mediciones."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # ok | device_error | error
    measurement_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationLog(Base):
    """Cada mensaje automatico enviado (o fallido) a Telegram."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    chat_id: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20))  # report | alert | device_error
    ok: Mapped[bool] = mapped_column(Boolean)
    text: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
