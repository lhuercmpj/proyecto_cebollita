"""Indexa los documentos cientificos en pgvector.

    python -m src.rag.ingest            # indexa lo nuevo o modificado
    python -m src.rag.ingest --force    # reindexa todo

Requiere GEMINI_API_KEY (los embeddings se generan con Gemini).
"""

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config import Settings, get_settings
from src.db_models.rag import DocumentChunk
from src.rag.documents import ReferenceDocument, chunk_document, load_references
from src.services.gemini_service import LLMClient, build_client

logger = logging.getLogger("cebollita.ingest")


def index_document(
    session: Session,
    document: ReferenceDocument,
    llm: LLMClient,
    settings: Settings,
    force: bool = False,
) -> int:
    """Indexa un documento. Devuelve la cantidad de fragmentos escritos (0 si no cambio)."""

    chunks = chunk_document(document.body)
    new_hashes = [chunk.sha256 for chunk in chunks]
    current = list(
        session.execute(
            select(DocumentChunk.content_sha256, DocumentChunk.embedding_model)
            .where(DocumentChunk.source_id == document.source_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )
    unchanged = [row.content_sha256 for row in current] == new_hashes and all(
        row.embedding_model == settings.gemini_embedding_model for row in current
    )
    if unchanged and not force:
        return 0

    texts = [chunk.content for chunk in chunks]
    vectors = llm.embed(texts, "RETRIEVAL_DOCUMENT", titles=[document.title] * len(texts))
    session.execute(delete(DocumentChunk).where(DocumentChunk.source_id == document.source_id))
    now = datetime.now(UTC)
    for chunk, vector in zip(chunks, vectors, strict=True):
        session.add(
            DocumentChunk(
                source_id=document.source_id,
                chunk_index=chunk.index,
                title=document.title,
                institution=document.institution,
                url=document.url,
                topic=chunk.topic,
                content=chunk.content,
                content_sha256=chunk.sha256,
                embedding_model=settings.gemini_embedding_model,
                embedding=vector,
                metadata_json=document.metadata,
                indexed_at=now,
            )
        )
    session.commit()
    return len(chunks)


def remove_missing(session: Session, source_ids: set[str]) -> int:
    stale = set(session.scalars(select(DocumentChunk.source_id).distinct())) - source_ids
    if stale:
        session.execute(delete(DocumentChunk).where(DocumentChunk.source_id.in_(stale)))
        session.commit()
    return len(stale)


def ingest_directory(
    session: Session,
    directory: Path,
    llm: LLMClient,
    settings: Settings,
    force: bool = False,
) -> dict[str, int]:
    documents = load_references(directory)
    written = {doc.source_id: index_document(session, doc, llm, settings, force) for doc in documents}
    removed = remove_missing(session, {doc.source_id for doc in documents})
    if removed:
        logger.info("Se eliminaron %s documentos que ya no estan en la carpeta", removed)
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="reindexar aunque no haya cambios")
    parser.add_argument("--dir", default=None, help="carpeta de referencias")
    args = parser.parse_args()

    from src.database import SessionLocal, create_tables

    settings = get_settings()
    create_tables()
    directory = Path(args.dir or settings.references_dir)
    llm = build_client(settings)
    with SessionLocal() as session:
        result = ingest_directory(session, directory, llm, settings, force=args.force)
    for source_id, count in result.items():
        logger.info("%-45s %s", source_id, f"{count} fragmentos" if count else "sin cambios")


if __name__ == "__main__":
    main()
