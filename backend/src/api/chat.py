from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.config import get_settings
from src.database import get_session
from src.services.chat_service import answer_message
from src.services.gemini_service import GeminiNotConfiguredError, build_client

router = APIRouter(prefix="/api/chat", tags=["chat"])
SessionDependency = Annotated[Session, Depends(get_session)]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=50)


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    in_domain: bool
    sources: list[str]
    used_llm: bool


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest, session: SessionDependency) -> ChatResponse:
    """Chat web con Cebollita (mismo servicio que Telegram)."""

    settings = get_settings()
    try:
        llm = build_client(settings)
    except GeminiNotConfiguredError:
        llm = None
    conversation_id = request.conversation_id or f"web-{uuid4().hex[:12]}"
    answer = answer_message(session, settings, llm, conversation_id, request.message, channel="web")
    return ChatResponse(
        conversation_id=conversation_id,
        reply=answer.text,
        in_domain=answer.in_domain,
        sources=answer.sources,
        used_llm=answer.used_llm,
    )
