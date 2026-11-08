from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.config import get_settings
from src.database import Base

EMBEDDING_DIMENSIONS = get_settings().embedding_dimensions


class DocumentChunk(Base):
    """Fragmento de un documento cientifico indexado con su embedding."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_chunk_source_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(100), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300))
    institution: Mapped[str | None] = mapped_column(String(300), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64))
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    """Historial de conversacion (memoria corta del chat y logs para el informe)."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(60), index=True)
    channel: Mapped[str] = mapped_column(String(20))  # telegram | web
    role: Mapped[str] = mapped_column(String(10))  # user | model
    text: Mapped[str] = mapped_column(Text)
    in_domain: Mapped[bool | None] = mapped_column(nullable=True)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
