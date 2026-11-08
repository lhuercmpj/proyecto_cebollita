"""Politica de alertas: avisar al cambiar de estado y no repetir continuamente."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from src.config import Settings
from src.database import as_utc
from src.db_models.notifications import AlertState
from src.schemas.measurement import MeasurementRead
from src.services.report_service import ALERT_STATES, OK_STATE

DecisionKind = Literal["alert", "reminder", "recovery", "none"]


@dataclass(frozen=True)
class AlertDecision:
    kind: DecisionKind
    state: str
    reason: str


def get_alert_state(session: Session, plant_id: str) -> AlertState:
    row = session.get(AlertState, plant_id)
    if row is None:
        row = AlertState(plant_id=plant_id, consecutive_failures=0)
        session.add(row)
        session.flush()
    return row


def decide_alert(
    row: AlertState,
    measurement: MeasurementRead,
    settings: Settings,
    now: datetime | None = None,
) -> AlertDecision:
    """Decide sin efectos secundarios si corresponde avisar por esta medicion."""

    now = now or datetime.now(UTC)
    state = measurement.prediction.state

    if row.last_measurement_id == measurement.measurement_id:
        return AlertDecision("none", state, "medicion ya evaluada")

    if state in ALERT_STATES:
        if row.last_alert_state != state:
            return AlertDecision("alert", state, "cambio de estado")
        repeat_after = timedelta(minutes=settings.alert_repeat_minutes)
        if row.last_alert_at is None or now - as_utc(row.last_alert_at) >= repeat_after:
            return AlertDecision("reminder", state, "persiste el estado")
        return AlertDecision("none", state, "alerta reciente del mismo estado")

    if state == OK_STATE and row.last_alert_state is not None:
        return AlertDecision("recovery", state, "volvio a estar bien")

    return AlertDecision("none", state, "sin alerta")


def mark_evaluated(
    session: Session,
    row: AlertState,
    measurement: MeasurementRead,
    decision: AlertDecision,
    delivered: bool,
    now: datetime | None = None,
) -> None:
    """Persiste el resultado. Si una alerta no se pudo entregar, se reintenta luego."""

    now = now or datetime.now(UTC)
    if decision.kind in ("alert", "reminder"):
        if not delivered:
            session.commit()
            return
        row.last_alert_state = decision.state
        row.last_alert_at = now
    elif decision.kind == "recovery":
        row.last_alert_state = None
        row.last_alert_at = None
    row.last_measurement_id = measurement.measurement_id
    session.commit()
