"""Cliente minimo de Gemini (texto y embeddings) detras de una interfaz simple.

El resto del backend depende de ``LLMClient``; en los tests se reemplaza por un
cliente falso, asi que nada de esto necesita la API key para probarse.
"""

import logging
import math
from dataclasses import dataclass
from typing import Literal, Protocol

from src.config import Settings

logger = logging.getLogger(__name__)

EmbeddingTask = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


@dataclass(frozen=True)
class ChatTurn:
    role: Literal["user", "model"]
    text: str


class LLMClient(Protocol):
    def generate(
        self,
        system_instruction: str,
        turns: list[ChatTurn],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str: ...

    def embed(self, texts: list[str], task: EmbeddingTask, titles: list[str] | None = None) -> list[list[float]]: ...


class GeminiNotConfiguredError(RuntimeError):
    pass


class GeminiError(RuntimeError):
    pass


def normalize(vector: list[float]) -> list[float]:
    """gemini-embedding-001 solo devuelve vectores normalizados en 3072 dimensiones."""

    norm = math.sqrt(sum(value * value for value in vector))
    return vector if norm == 0 else [value / norm for value in vector]


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise GeminiNotConfiguredError("GEMINI_API_KEY no configurada")
        from google import genai

        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._settings = settings

    def generate(
        self,
        system_instruction: str,
        turns: list[ChatTurn],
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        from google.genai import types

        contents = [
            types.Content(role=turn.role, parts=[types.Part.from_text(text=turn.text)])
            for turn in turns
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=self._settings.gemini_temperature if temperature is None else temperature,
            max_output_tokens=max_output_tokens,
        )
        try:
            response = self._client.models.generate_content(
                model=self._settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as exc:  # noqa: BLE001 - errores de red, cuota o modelo
            raise GeminiError(f"Gemini no respondio: {type(exc).__name__}: {exc}") from exc
        text = (response.text or "").strip()
        if not text:
            raise GeminiError("Gemini devolvio una respuesta vacia")
        return text

    def embed(
        self,
        texts: list[str],
        task: EmbeddingTask,
        titles: list[str] | None = None,
    ) -> list[list[float]]:
        from google.genai import types

        vectors: list[list[float]] = []
        # La API acepta lotes; se envian de a 50 para no exceder limites.
        for start in range(0, len(texts), 50):
            batch = texts[start : start + 50]
            config = types.EmbedContentConfig(
                task_type=task,
                output_dimensionality=self._settings.embedding_dimensions,
            )
            try:
                response = self._client.models.embed_content(
                    model=self._settings.gemini_embedding_model,
                    contents=batch,
                    config=config,
                )
            except Exception as exc:  # noqa: BLE001
                raise GeminiError(f"Error al generar embeddings: {type(exc).__name__}: {exc}") from exc
            vectors.extend(normalize(list(item.values)) for item in response.embeddings)
        return vectors


def build_client(settings: Settings) -> LLMClient:
    return GeminiClient(settings)
