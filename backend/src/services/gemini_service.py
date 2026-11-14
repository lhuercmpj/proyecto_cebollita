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

        from google.genai import types

        # Sin timeout, una llamada a un modelo saturado puede quedar colgada sin fin.
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(settings.gemini_timeout_seconds * 1000)),
        )
        self._settings = settings
        self._model = settings.gemini_model
        self._available: list[tuple[str, list[str]]] | None = None
        self._thinking_supported = True

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
            # Responder como la planta no requiere razonamiento largo: con el nivel
            # por defecto los Flash nuevos tardaban mas de 20 s por respuesta.
            thinking_config=(
                types.ThinkingConfig(thinking_level=self._settings.gemini_thinking_level)
                if self._thinking_supported and self._settings.gemini_thinking_level
                else None
            ),
        )
        try:
            response = self._generate_with_fallback(contents, config)
        except GeminiError:
            raise
        except Exception as exc:  # noqa: BLE001 - errores de red, cuota o modelo
            raise GeminiError(f"Gemini no respondio: {type(exc).__name__}: {exc}") from exc
        text = (response.text or "").strip()
        if not text:
            raise GeminiError("Gemini devolvio una respuesta vacia")
        return text

    def _generate_with_fallback(self, contents, config):
        """Llama al modelo con reintentos y, si no existe o esta saturado, prueba otro Flash."""

        import time

        tried: list[str] = []
        last_exc: Exception | None = None
        model = self._model
        deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
        while model and model not in tried and time.monotonic() < deadline:
            tried.append(model)
            attempt = 0
            while attempt <= RETRIES:
                try:
                    response = self._client.models.generate_content(model=model, contents=contents, config=config)
                    if model != self._model:
                        logger.warning(
                            "Se usa %s en lugar de %s. Fijalo con GEMINI_MODEL=%s", model, self._model, model
                        )
                        self._model = model
                    return response
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    code = getattr(exc, "code", None)
                    if code == 400 and "thinking" in str(exc).lower() and config.thinking_config is not None:
                        logger.warning("%s no acepta thinking_level; se llama sin esa opcion", model)
                        self._thinking_supported = False
                        config = config.model_copy(update={"thinking_config": None})
                        continue  # mismo modelo, sin consumir un reintento
                    if is_timeout(exc) or code in SWITCH_CODES:
                        logger.warning("Gemini %s no respondio a tiempo (%s); se prueba otro modelo", model, code)
                        break
                    if code in TRANSIENT_CODES and attempt < RETRIES and time.monotonic() < deadline:
                        logger.info("Gemini %s respondio %s; reintento %s", model, code, attempt + 1)
                        self._sleep(BACKOFF_SECONDS * (attempt + 1))
                        attempt += 1
                        continue
                    if code not in (404, *TRANSIENT_CODES, *SWITCH_CODES):
                        raise
                    break  # modelo inexistente o saturado: probar otro
            # Tras fallar el modelo configurado se prueba primero un Flash-Lite (menos
            # demanda); si no hay o tambien falla, los demas Flash.
            model = self._pick_available_model(exclude=tried, prefer_lite=len(tried) == 1)
        if last_exc is None:
            raise GeminiError("Gemini no respondio dentro del tiempo maximo")
        raise last_exc

    @staticmethod
    def _sleep(seconds: float) -> None:
        import time

        time.sleep(seconds)

    def _pick_available_model(self, exclude: list[str] | None = None, prefer_lite: bool = False) -> str | None:
        """Elige el Flash de texto mas nuevo que la key puede usar con generateContent."""

        exclude = exclude or []
        if self._available is None:
            try:
                self._available = [
                    ((m.name or "").removeprefix("models/"), list(m.supported_actions or []))
                    for m in self._client.models.list()
                ]
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo listar los modelos de Gemini: %s", exc)
                return None
        return choose_flash_model([m for m in self._available if m[0] not in exclude], prefer_lite=prefer_lite)

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


def is_timeout(exc: BaseException) -> bool:
    """Timeouts de httpx (o de cualquier capa) sin depender del paquete exacto."""

    current: BaseException | None = exc
    while current is not None:
        if "timeout" in type(current).__name__.lower():
            return True
        current = current.__cause__ or current.__context__
    return False


# Errores temporales de Gemini: saturacion (503), cuota por minuto (429), internos (500).
TRANSIENT_CODES = (429, 500, 503)
# Gateway/plazo vencido: reintentar el mismo modelo solo hace esperar mas; se cambia de modelo.
SWITCH_CODES = (502, 504)
# Sin reintentos sobre el mismo modelo: si esta saturado, es mas rapido probar otro.
RETRIES = 0
BACKOFF_SECONDS = 1.0
# Tiempo total maximo buscando respuesta (reintentos + cambios de modelo).
TOTAL_BUDGET_SECONDS = 45

EXCLUDED_MODEL_WORDS = ("image", "tts", "audio", "live", "embedding", "thinking", "exp", "preview", "8b")


def choose_flash_model(models: list[tuple[str, list[str]]], prefer_lite: bool = False) -> str | None:
    """De (nombre, acciones) elige un Flash estable de texto.

    Primero los Flash completos (version mas alta primero) y, como ultimo recurso,
    los Flash-Lite, que suelen estar menos saturados.
    """

    import re

    candidates = []
    for name, actions in models:
        if "generateContent" not in actions or "flash" not in name:
            continue
        if any(word in name for word in EXCLUDED_MODEL_WORDS):
            continue
        match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
        version = float(match.group(1)) if match else 0.0
        is_lite = "lite" in name
        candidates.append((is_lite if prefer_lite else not is_lite, version, "latest" not in name, -len(name), name))
    if not candidates:
        return None
    return max(candidates)[4]


def build_client(settings: Settings) -> LLMClient:
    return GeminiClient(settings)
