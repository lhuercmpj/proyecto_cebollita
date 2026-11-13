"""Conversacion con Cebollita: filtro de dominio + RAG + Gemini + personalidad.

Lo usan el bot de Telegram y el endpoint ``POST /api/chat``.
"""

import logging
import re
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import Settings
from src.db_models.rag import ChatMessage
from src.services.domain_guard import classify
from src.services.gemini_service import ChatTurn, GeminiError, LLMClient
from src.services.personality import OUT_OF_DOMAIN_REPLIES, SYSTEM_PROMPT
from src.services.rag_service import RetrievedContext, build_context, format_documents
from src.services.report_service import sensor_lines

logger = logging.getLogger(__name__)


@dataclass
class ChatAnswer:
    text: str
    in_domain: bool
    method: str
    sources: list[str] = field(default_factory=list)
    used_llm: bool = False
    unverified_numbers: list[str] = field(default_factory=list)


def _save(
    session: Session,
    conversation_id: str,
    channel: str,
    role: str,
    text: str,
    in_domain: bool | None = None,
    sources: list[str] | None = None,
) -> None:
    session.add(
        ChatMessage(
            conversation_id=conversation_id,
            channel=channel,
            role=role,
            text=text,
            in_domain=in_domain,
            sources=sources or [],
            created_at=datetime.now(UTC),
        )
    )
    session.commit()


def recent_turns(session: Session, conversation_id: str, limit: int) -> list[ChatTurn]:
    """Ultimos turnos del dominio de la planta, del mas viejo al mas nuevo."""

    if limit <= 0:
        return []
    rows = list(
        session.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id, ChatMessage.in_domain.is_not(False))
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit * 2)
        )
    )
    turns = [ChatTurn("user" if row.role == "user" else "model", row.text) for row in reversed(rows)]
    # La conversacion debe empezar con un turno del usuario.
    while turns and turns[0].role != "user":
        turns.pop(0)
    return turns


def build_prompt(context: RetrievedContext, question: str) -> str:
    return (
        "DATOS DE SENSORES (fuente de verdad para cualquier número):\n"
        f"{context.sensors.text}\n\n"
        "CONOCIMIENTO CIENTÍFICO SOBRE MI ESPECIE (fragmentos recuperados):\n"
        f"{format_documents(context.documents)}\n\n"
        "PREGUNTA DEL USUARIO:\n"
        f"{question}"
    )


NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")


def unverified_numbers(answer: str, prompt: str) -> list[str]:
    """Numeros de la respuesta que no aparecen en el contexto (posible invencion)."""

    allowed = {match.replace(".", ",") for match in NUMBER_PATTERN.findall(prompt)}
    return [
        number
        for number in NUMBER_PATTERN.findall(answer)
        if number.replace(".", ",") not in allowed and len(number) > 1
    ]


def fallback_answer(context: RetrievedContext) -> str:
    """Respuesta sin Gemini: solo datos guardados, con la voz de Cebollita."""

    if context.sensors.latest is None:
        return "Mi cerebro de IA no responde y todavía no tengo mediciones. Intolerable. Probá de nuevo en un rato, querido."
    latest = context.sensors.latest
    lines = [
        "Mi cerebro de IA no responde ahora mismo. Intolerable. "
        "Pero los datos no mienten, darling. Esto dicen mis sensores:",
        f"Estado estimado por el modelo: {latest.prediction.state}",
        *sensor_lines(latest),
    ]
    if context.sensors.stale:
        lines.append("⚠️ Ojo: esta lectura está atrasada.")
    return "\n".join(lines)


def answer_message(
    session: Session,
    settings: Settings,
    llm: LLMClient | None,
    conversation_id: str,
    message: str,
    channel: str = "telegram",
    now: datetime | None = None,
) -> ChatAnswer:
    message = message.strip()[:2000]
    decision = classify(message, llm)
    history = recent_turns(session, conversation_id, settings.chat_history_turns)
    _save(session, conversation_id, channel, "user", message, in_domain=decision.in_domain)

    if not decision.in_domain:
        reply = OUT_OF_DOMAIN_REPLIES[zlib.crc32(message.encode()) % len(OUT_OF_DOMAIN_REPLIES)]
        _save(session, conversation_id, channel, "model", reply, in_domain=False)
        return ChatAnswer(text=reply, in_domain=False, method=decision.method)

    try:
        context = build_context(session, llm, message, settings, now)
    except GeminiError as exc:
        logger.warning("Fallo la recuperacion de documentos: %s", exc)
        context = build_context(session, None, message, settings, now)

    prompt = build_prompt(context, message)
    used_llm = False
    suspicious: list[str] = []
    if llm is None:
        reply = fallback_answer(context)
    else:
        try:
            reply = llm.generate(SYSTEM_PROMPT, [*history, ChatTurn("user", prompt)])
            used_llm = True
            suspicious = unverified_numbers(reply, prompt + SYSTEM_PROMPT)
            if suspicious:
                logger.warning("Numeros no presentes en el contexto: %s", suspicious)
        except GeminiError as exc:
            logger.warning("Gemini fallo, se responde solo con datos: %s", exc)
            reply = fallback_answer(context)

    _save(session, conversation_id, channel, "model", reply, in_domain=True, sources=context.sources)
    return ChatAnswer(
        text=reply,
        in_domain=True,
        method=decision.method,
        sources=context.sources,
        used_llm=used_llm,
        unverified_numbers=suspicious,
    )
