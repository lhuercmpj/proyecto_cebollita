"""Recuperacion de contexto para el chat: sensores (SQL) + documentos (pgvector)."""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db_models.rag import DocumentChunk
from src.schemas.measurement import MeasurementRead
from src.services.gemini_service import LLMClient
from src.services.measurement_service import latest_measurement, measurements_between
from src.services.report_service import format_local, is_stale


def _n(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


@dataclass
class SensorContext:
    text: str
    latest: MeasurementRead | None
    stale: bool = False


@dataclass
class RetrievedChunk:
    source_id: str
    title: str
    institution: str | None
    url: str | None
    topic: str | None
    content: str
    score: float

    @property
    def label(self) -> str:
        return self.institution or self.title


@dataclass
class RetrievedContext:
    sensors: SensorContext
    documents: list[RetrievedChunk] = field(default_factory=list)
    catalog: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for chunk in self.documents:
            if chunk.source_id not in seen:
                seen.append(chunk.source_id)
        return seen


# --- Sensores -------------------------------------------------------------


def describe_measurement(measurement: MeasurementRead, settings: Settings) -> str:
    sensors = measurement.sensors
    probabilities = ", ".join(
        f"{state} {_n(value * 100, 0)} %" for state, value in measurement.prediction.probabilities.items()
    )
    return (
        f"- Fecha y hora (Montevideo): {format_local(measurement.measured_at, settings)}\n"
        f"- Estado estimado por el modelo: {measurement.prediction.state} "
        f"(probabilidad {_n(measurement.prediction.confidence * 100, 0)} %; todas: {probabilities})\n"
        f"- Temperatura promedio: {_n(measurement.temp_promedio)} °C "
        f"(DHT11 {_n(sensors.temp_dht11)} °C, LM35 {_n(sensors.temp_lm35)} °C)\n"
        f"- Humedad del aire: {_n(sensors.humedad_aire, 0)} %\n"
        f"- Humedad de la tierra (cruda 0-4095): {_n(sensors.humedad_tierra, 0)}\n"
        f"- Luz (cruda 0-4095, mayor = más oscuro): {_n(sensors.luz, 0)}"
    )


def summarize_window(
    measurements: list[MeasurementRead],
    label: str,
    settings: Settings,
) -> str:
    if not measurements:
        return f"{label}: sin mediciones en ese período."

    def stats(values: list[float], decimals: int = 1, unit: str = "") -> str:
        return (
            f"promedio {_n(mean(values), decimals)}{unit}, mínimo {_n(min(values), decimals)}{unit}, "
            f"máximo {_n(max(values), decimals)}{unit}"
        )

    temps = [m.temp_promedio for m in measurements]
    air = [m.sensors.humedad_aire for m in measurements]
    soil = [m.sensors.humedad_tierra for m in measurements]
    light = [m.sensors.luz for m in measurements]
    states: dict[str, int] = {}
    for m in measurements:
        states[m.prediction.state] = states.get(m.prediction.state, 0) + 1
    state_text = ", ".join(f"{state}: {count}" for state, count in sorted(states.items(), key=lambda i: -i[1]))
    first, last = measurements[0], measurements[-1]
    lines = [
        f"{label} ({len(measurements)} mediciones, de {format_local(first.measured_at, settings)} "
        f"a {format_local(last.measured_at, settings)}):",
        f"- Temperatura: {stats(temps, unit=' °C')}",
        f"- Humedad del aire: {stats(air, 0, ' %')}",
        f"- Humedad de la tierra (cruda): {stats(soil, 0)}; "
        f"primera {_n(first.sensors.humedad_tierra, 0)} → última {_n(last.sensors.humedad_tierra, 0)}",
        f"- Luz (cruda, mayor = más oscuro): {stats(light, 0)}",
        f"- Estados estimados por el modelo: {state_text}",
    ]
    thirsty = [m for m in measurements if m.prediction.state == "Preciso agua"]
    if thirsty:
        lines.append(f"- Última vez «Preciso agua»: {format_local(thirsty[-1].measured_at, settings)}")
    return "\n".join(lines)


MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
MONTH_NAMES = {v: k for k, v in MONTHS.items() if k != "setiembre"}


def _normalize(text: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def requested_periods(question: str, now: datetime, settings: Settings) -> list[tuple[str, datetime, datetime]]:
    """Dias o meses que nombra la pregunta ("el 13 de octubre", "13/10", "en septiembre")."""

    import re
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(settings.timezone)
    local_now = now.astimezone(tz)
    text = _normalize(question)
    periods: list[tuple[str, datetime, datetime]] = []

    def year_for(month: int, day: int = 1) -> int:
        candidate = datetime(local_now.year, month, day, tzinfo=tz)
        return local_now.year if candidate <= local_now else local_now.year - 1

    def add_day(day: int, month: int) -> None:
        try:
            start = datetime(year_for(month, day), month, day, tzinfo=tz)
        except ValueError:
            return
        label = f"Día {start.strftime('%d/%m/%Y')}"
        if all(p[0] != label for p in periods):
            periods.append((label, start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)))

    for day, month in re.findall(r"\b(\d{1,2})/(\d{1,2})\b", text):
        if 1 <= int(month) <= 12:
            add_day(int(day), int(month))
    for day, name in re.findall(r"\b(\d{1,2}) de (" + "|".join(MONTHS) + r")\b", text):
        add_day(int(day), MONTHS[name])
    days_named = {p[0] for p in periods}
    for name, month in MONTHS.items():
        if re.search(rf"\b{name}\b", text) and not any(f"/{month:02d}/" in label for label in days_named):
            start = datetime(year_for(month), month, 1, tzinfo=tz)
            end = datetime(start.year + (month == 12), month % 12 + 1, 1, tzinfo=tz)
            label = f"Mes de {MONTH_NAMES[month]} {start.year}"
            if all(p[0] != label for p in periods):
                periods.append((label, start.astimezone(UTC), end.astimezone(UTC)))
    if re.search(r"\bayer\b", text):
        start = (local_now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        periods.append((f"Ayer ({start.strftime('%d/%m/%Y')})", start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)))
    return periods[:3]


def history_overview(session: Session, settings: Settings) -> str:
    """Resumen de TODO el historial guardado (dataset historico + lecturas de la ESP32), por mes."""

    from sqlalchemy import func

    from src.db_models.measurement import Measurement

    rows = session.execute(
        select(Measurement.source, func.count(), func.min(Measurement.measured_at), func.max(Measurement.measured_at))
        .where(Measurement.plant_id == settings.plant_id)
        .group_by(Measurement.source)
    ).all()
    if not rows:
        return "Historial completo: sin mediciones guardadas."
    names = {"esp32": "lecturas de la ESP32", "historico_tarea2": "dataset histórico de la Tarea 2 (limpio)"}
    lines = ["Historial completo guardado:"]
    first = min(as_utc_dt(r[2]) for r in rows)
    last = max(as_utc_dt(r[3]) for r in rows)
    for source, count, start, end in rows:
        lines.append(
            f"- {names.get(source, source)}: {count} mediciones, de {format_local(as_utc_dt(start), settings)} "
            f"a {format_local(as_utc_dt(end), settings)}"
        )
    everything = measurements_between(session, first, last, settings.plant_id)
    by_month: dict[str, list[MeasurementRead]] = {}
    for m in everything:
        local = m.measured_at.astimezone(_tz(settings))
        by_month.setdefault(f"{MONTH_NAMES[local.month].capitalize()} {local.year}", []).append(m)
    lines.append("Resumen por mes:")
    for label, items in by_month.items():
        states: dict[str, int] = {}
        for m in items:
            states[m.prediction.state] = states.get(m.prediction.state, 0) + 1
        state_text = ", ".join(f"{k} {v}" for k, v in sorted(states.items(), key=lambda i: -i[1]))
        lines.append(
            f"- {label}: {len(items)} mediciones; temp. promedio {_n(mean(m.temp_promedio for m in items))} °C; "
            f"humedad aire {_n(mean(m.sensors.humedad_aire for m in items), 0)} %; "
            f"tierra (cruda) {_n(mean(m.sensors.humedad_tierra for m in items), 0)}; "
            f"luz (cruda) {_n(mean(m.sensors.luz for m in items), 0)}; "
            f"estados estimados por el modelo actual: {state_text}"
        )
        start, end = items[0].measured_at, items[-1].measured_at + timedelta(seconds=1)
        labels = recorded_labels(session, start, end, settings)
        if labels:
            lines.append(f"  etiquetas registradas por el grupo en el dataset: {labels}")
    return "\n".join(lines)


def recorded_labels(session: Session, start: datetime, end: datetime, settings: Settings) -> str:
    """Etiquetas que el grupo registro en el dataset historico para ese periodo."""

    from src.db_models.measurement import Measurement

    rows = session.scalars(
        select(Measurement.raw_payload).where(
            Measurement.plant_id == settings.plant_id,
            Measurement.source == "historico_tarea2",
            Measurement.measured_at >= start,
            Measurement.measured_at < end,
        )
    )
    counts: dict[str, int] = {}
    for payload in rows:
        label = (payload or {}).get("estado_historico")
        if label:
            counts[label] = counts.get(label, 0) + 1
    if not counts:
        return ""
    return ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda i: -i[1]))


def _tz(settings: Settings):
    from zoneinfo import ZoneInfo

    return ZoneInfo(settings.timezone)


def as_utc_dt(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def sensor_context(
    session: Session,
    settings: Settings,
    now: datetime | None = None,
    question: str = "",
) -> SensorContext:
    now = now or datetime.now(UTC)
    latest = latest_measurement(session, settings.plant_id)
    if latest is None:
        return SensorContext(
            text="Todavía no hay ninguna medición guardada de los sensores.",
            latest=None,
        )
    stale = is_stale(latest, settings, now)
    parts = [
        f"Hora actual (Montevideo): {format_local(now, settings)}",
        "Última medición:" + (" (ATRASADA: no llegaron lecturas nuevas)" if stale else ""),
        describe_measurement(latest, settings),
        "",
        summarize_window(
            measurements_between(session, now - timedelta(hours=24), now, settings.plant_id),
            "Últimas 24 horas",
            settings,
        ),
        "",
        summarize_window(
            measurements_between(session, now - timedelta(days=7), now, settings.plant_id),
            "Últimos 7 días",
            settings,
        ),
    ]
    for label, start, end in requested_periods(question, now, settings):
        parts += ["", summarize_window(measurements_between(session, start, end, settings.plant_id), label, settings)]
        labels = recorded_labels(session, start, end, settings)
        if labels:
            parts.append(f"- Etiquetas registradas por el grupo en el dataset: {labels}")
    parts += ["", history_overview(session, settings)]
    return SensorContext(text="\n".join(parts), latest=latest, stale=stale)


# --- Documentos -------------------------------------------------------------


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 0.0 if norm == 0 else dot / norm


def _to_retrieved(row: DocumentChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        source_id=row.source_id,
        title=row.title,
        institution=row.institution,
        url=row.url,
        topic=row.topic,
        content=row.content,
        score=score,
    )


def search_chunks(session: Session, query_vector: list[float], k: int) -> list[RetrievedChunk]:
    if session.get_bind().dialect.name == "postgresql":
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = session.execute(select(DocumentChunk, distance.label("distance")).order_by(distance).limit(k))
        return [_to_retrieved(row.DocumentChunk, 1 - float(row.distance)) for row in rows]
    # SQLite (tests): busqueda exacta en Python.
    scored = [
        _to_retrieved(row, _cosine(list(row.embedding), query_vector))
        for row in session.scalars(select(DocumentChunk))
    ]
    return sorted(scored, key=lambda item: item.score, reverse=True)[:k]


def available_sources(session: Session) -> list[tuple[str, str, int]]:
    """(titulo, institucion, cantidad de fragmentos) de cada documento indexado."""

    from sqlalchemy import func

    rows = session.execute(
        select(DocumentChunk.title, DocumentChunk.institution, func.count())
        .group_by(DocumentChunk.title, DocumentChunk.institution)
        .order_by(DocumentChunk.institution)
    ).all()
    return [(title, institution or "", count) for title, institution, count in rows]


def has_documents(session: Session) -> bool:
    return session.scalar(select(DocumentChunk.id).limit(1)) is not None


def retrieve_documents(
    session: Session,
    llm: LLMClient,
    question: str,
    settings: Settings,
    current_state: str | None = None,
) -> list[RetrievedChunk]:
    if not has_documents(session):
        return []
    query = question if current_state is None else f"{question}\nEstado actual de la planta: {current_state}"
    vector = llm.embed([query], "RETRIEVAL_QUERY")[0]
    return search_chunks(session, vector, settings.rag_top_k)


def build_context(
    session: Session,
    llm: LLMClient | None,
    question: str,
    settings: Settings,
    now: datetime | None = None,
) -> RetrievedContext:
    sensors = sensor_context(session, settings, now, question)
    documents: list[RetrievedChunk] = []
    if llm is not None:
        state = sensors.latest.prediction.state if sensors.latest else None
        documents = retrieve_documents(session, llm, question, settings, state)
    return RetrievedContext(sensors=sensors, documents=documents, catalog=available_sources(session))


def format_catalog(catalog: list[tuple[str, str, int]]) -> str:
    if not catalog:
        return "Todavía no hay documentos científicos indexados (falta correr la indexación)."
    return "\n".join(f"- {institution}: {title} ({count} fragmentos)" for title, institution, count in catalog)


def format_documents(documents: list[RetrievedChunk]) -> str:
    if not documents:
        return "No hay fragmentos científicos indexados para esta pregunta."
    return "\n\n".join(
        f"[{index}] Fuente: {chunk.label} — {chunk.title}\n{chunk.content}"
        for index, chunk in enumerate(documents, start=1)
    )
