"""Lectura y fragmentacion de los documentos de ``data/references``."""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

SKIPPED_FILES = {"que_va_aca.md", "fuentes.md", "readme.md"}


@dataclass
class ReferenceDocument:
    source_id: str
    title: str
    body: str
    institution: str | None = None
    url: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class Chunk:
    index: int
    topic: str | None
    content: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


def parse_reference(path: Path) -> ReferenceDocument:
    """Lee un .md con encabezado ``---`` clave: valor ``---``."""

    raw = path.read_text(encoding="utf-8")
    metadata: dict[str, str] = {}
    body = raw
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, flags=re.DOTALL)
    if match:
        header, body = match.groups()
        for line in header.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
    return ReferenceDocument(
        source_id=metadata.get("source_id") or path.stem,
        title=metadata.get("title") or path.stem,
        institution=metadata.get("institution") or None,
        url=metadata.get("url") or None,
        body=body.strip(),
        metadata=metadata,
    )


def load_references(directory: Path) -> list[ReferenceDocument]:
    return [
        parse_reference(path)
        for path in sorted(directory.glob("*.md"))
        if path.name.lower() not in SKIPPED_FILES
    ]


def chunk_document(body: str, max_chars: int = 900, overlap_paragraphs: int = 1) -> list[Chunk]:
    """Divide por secciones (``# titulo``) y, si una seccion es larga, por parrafos.

    Cada fragmento lleva el titulo de su seccion para que conserve contexto al
    recuperarse aislado.
    """

    sections: list[tuple[str | None, list[str]]] = []
    topic: str | None = None
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block:
            continue
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", block.splitlines()[0])
        if heading:
            if paragraphs:
                sections.append((topic, paragraphs))
            topic = heading.group(1)
            paragraphs = []
            rest = "\n".join(block.splitlines()[1:]).strip()
            if rest:
                paragraphs.append(rest)
        else:
            paragraphs.append(block)
    if paragraphs:
        sections.append((topic, paragraphs))

    chunks: list[Chunk] = []
    for section_topic, section_paragraphs in sections:
        prefix = f"{section_topic}: " if section_topic else ""
        current: list[str] = []
        for paragraph in section_paragraphs:
            candidate = "\n".join([*current, paragraph])
            if current and len(prefix) + len(candidate) > max_chars:
                chunks.append(Chunk(len(chunks), section_topic, prefix + "\n".join(current)))
                current = current[-overlap_paragraphs:] if overlap_paragraphs else []
            current.append(paragraph)
        if current:
            chunks.append(Chunk(len(chunks), section_topic, prefix + "\n".join(current)))
    return chunks
