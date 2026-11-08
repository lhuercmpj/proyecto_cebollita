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
        f"- Estados estimados: {state_text}",
    ]
    thirsty = [m for m in measurements if m.prediction.state == "Preciso agua"]
    if thirsty:
        lines.append(f"- Última vez «Preciso agua»: {format_local(thirsty[-1].measured_at, settings)}")
    return "\n".join(lines)


def sensor_context(session: Session, settings: Settings, now: datetime | None = None) -> SensorContext:
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
    sensors = sensor_context(session, settings, now)
    documents: list[RetrievedChunk] = []
    if llm is not None:
        state = sensors.latest.prediction.state if sensors.latest else None
        documents = retrieve_documents(session, llm, question, settings, state)
    return RetrievedContext(sensors=sensors, documents=documents)


def format_documents(documents: list[RetrievedChunk]) -> str:
    if not documents:
        return "No hay fragmentos científicos indexados para esta pregunta."
    return "\n\n".join(
        f"[{index}] Fuente: {chunk.label} — {chunk.title}\n{chunk.content}"
        for index, chunk in enumerate(documents, start=1)
    )
