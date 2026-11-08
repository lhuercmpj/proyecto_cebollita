"""Fixtures compartidas.

Por defecto los tests usan SQLite en un archivo temporal. Para probar contra
PostgreSQL + pgvector (incluida la busqueda vectorial) definir:

    TEST_DATABASE_URL=postgresql+psycopg://cebollita:cebollita_dev@localhost:5433/cebollita_test
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import Settings
from src.database import Base, create_tables
from src.schemas.measurement import DeviceMeasurement
from src.services.model_data import TEST_X
from src.services.prediction_service import predict


@pytest.fixture
def engine(tmp_path) -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    test_engine = create_engine(url)
    Base.metadata.drop_all(test_engine)
    create_tables(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def session(session_factory) -> Iterator[Session]:
    with session_factory() as db_session:
        yield db_session


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        telegram_bot_token="test-token",
        telegram_chat_id="1000",
        gemini_api_key="test-key",
        report_interval_minutes=30,
        stale_margin_minutes=10,
        alert_repeat_minutes=180,
    )


def make_payload(sample_index: int, timestamp: datetime) -> DeviceMeasurement:
    """Payload valido del firmware usando un vector de verificacion del modelo."""

    humedad_tierra, luz, humedad_aire, temp_promedio = TEST_X[sample_index]
    prediction = predict(*TEST_X[sample_index])
    return DeviceMeasurement.model_validate(
        {
            "ok": True,
            "clase": prediction.class_index,
            "estado": prediction.state,
            "confianza": prediction.confidence,
            "timestamp_unix": int(timestamp.timestamp()),
            "duracion_ms": 9000,
            "muestras": 30,
            "datos": {
                "humedad_tierra": humedad_tierra,
                "luz": luz,
                "humedad_aire": humedad_aire,
                "temp_promedio": temp_promedio,
                "temp_dht11": temp_promedio - 0.01,
                "temp_lm35": temp_promedio + 0.01,
                "periodo": None,
            },
            "probabilidades": [
                {"clase": index, "estado": state, "probabilidad": probability}
                for index, (state, probability) in enumerate(prediction.probabilities.items())
            ],
            "calidad": {
                "llamadas_dht_validas": 30,
                "lecturas_lm35_validas": 30,
                "lm35_sospechoso": False,
                "solo_dht_para_temperatura": False,
            },
        }
    )


# Indices de TEST_X por estado esperado del modelo.
SAMPLE_AGUA = 0  # Preciso agua
SAMPLE_BIEN = 3  # Estoy bien
SAMPLE_MAL = 4  # Estoy mal

BASE_TIME = datetime(2026, 11, 8, 15, 0, tzinfo=UTC)


class FakeNotifier:
    def __init__(self, enabled: bool = True, fail_for: set[str] | None = None) -> None:
        self._enabled = enabled
        self.fail_for = fail_for or set()
        self.sent: list[tuple[str, str]] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def send(self, chat_id: str, text: str) -> None:
        if chat_id in self.fail_for:
            raise RuntimeError("fallo simulado")
        self.sent.append((chat_id, text))


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


class FakeLLM:
    """LLM falso: embeddings por bolsa de palabras y respuestas guionadas."""

    def __init__(self, reply: str = "Respuesta de Cebollita", in_domain_answer: str = "NO") -> None:
        self.reply = reply
        self.in_domain_answer = in_domain_answer
        self.generate_calls: list[tuple[str, list]] = []
        self.embed_calls: list[tuple[list[str], str]] = []
        self.fail_generate = False

    def generate(self, system_instruction, turns, temperature=None, max_output_tokens=None):
        from src.services.domain_guard import CLASSIFIER_PROMPT
        from src.services.gemini_service import GeminiError

        self.generate_calls.append((system_instruction, list(turns)))
        if system_instruction == CLASSIFIER_PROMPT:
            return self.in_domain_answer
        if self.fail_generate:
            raise GeminiError("fallo simulado")
        return self.reply

    def embed(self, texts, task, titles=None):
        import math
        import re
        import unicodedata

        from src.config import get_settings

        dims = get_settings().embedding_dimensions
        self.embed_calls.append((list(texts), task))
        vectors = []
        for text in texts:
            norm_text = unicodedata.normalize("NFKD", text.lower())
            norm_text = "".join(c for c in norm_text if not unicodedata.combining(c))
            vector = [0.0] * dims
            for word in re.findall(r"[a-z]{4,}", norm_text):
                vector[sum(map(ord, word[:6])) % dims] += 1.0
            length = math.sqrt(sum(v * v for v in vector)) or 1.0
            vectors.append([v / length for v in vector])
        return vectors


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()
