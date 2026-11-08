from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from src.db_models import ChatMessage
from src.rag.ingest import ingest_directory
from src.services.chat_service import answer_message, unverified_numbers
from src.services.ingest_service import store_device_measurement
from src.services.personality import OUT_OF_DOMAIN_REPLIES, SYSTEM_PROMPT
from tests.conftest import BASE_TIME, SAMPLE_AGUA, FakeLLM, make_payload

REFERENCES = Path(__file__).resolve().parents[2] / "data" / "references"


def seed(session, settings, llm):
    store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME - timedelta(minutes=5)), settings)
    ingest_directory(session, REFERENCES, llm, settings)


def test_prompt_contains_sensor_data_documents_and_personality(session, settings, fake_llm):
    seed(session, settings, fake_llm)

    answer = answer_message(session, settings, fake_llm, "chat-1", "¿Necesitás riego hoy?", now=BASE_TIME)

    assert answer.in_domain and answer.used_llm
    assert answer.text == fake_llm.reply
    system, turns = fake_llm.generate_calls[-1]
    assert system == SYSTEM_PROMPT
    prompt = turns[-1].text
    assert "Preciso agua" in prompt
    assert "930" in prompt  # humedad de tierra cruda de la medicion
    assert "CONOCIMIENTO CIENTÍFICO" in prompt and "Fuente:" in prompt
    assert prompt.endswith("¿Necesitás riego hoy?")
    assert answer.sources


def test_out_of_domain_is_refused_without_calling_generation(session, settings):
    llm = FakeLLM(in_domain_answer="NO")

    answer = answer_message(session, settings, llm, "chat-2", "¿Quién ganó el clásico?", now=BASE_TIME)

    assert answer.in_domain is False
    assert answer.text in OUT_OF_DOMAIN_REPLIES
    # Solo se llamo al clasificador, nunca a la generacion de la respuesta.
    assert all(system != SYSTEM_PROMPT for system, _ in llm.generate_calls)


def test_history_is_sent_and_out_of_domain_turns_are_excluded(session, settings, fake_llm):
    seed(session, settings, fake_llm)
    answer_message(session, settings, fake_llm, "chat-3", "¿Cómo estás?", now=BASE_TIME)
    answer_message(session, settings, FakeLLM(in_domain_answer="NO"), "chat-3", "Contame de fútbol", now=BASE_TIME)
    answer_message(session, settings, fake_llm, "chat-3", "¿Y qué luz te gusta?", now=BASE_TIME)

    _, turns = fake_llm.generate_calls[-1]
    texts = [turn.text for turn in turns]
    assert texts[0] == "¿Cómo estás?"
    assert texts[1] == fake_llm.reply
    assert not any("fútbol" in text for text in texts)
    rows = list(session.scalars(select(ChatMessage).where(ChatMessage.conversation_id == "chat-3")))
    assert len(rows) == 6


def test_gemini_failure_falls_back_to_stored_data(session, settings, fake_llm):
    seed(session, settings, fake_llm)
    fake_llm.fail_generate = True

    answer = answer_message(session, settings, fake_llm, "chat-4", "¿Cómo estás?", now=BASE_TIME)

    assert answer.used_llm is False
    assert "Preciso agua" in answer.text
    assert "930" in answer.text


def test_without_api_key_answers_with_data(session, settings):
    store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME), settings)
    answer = answer_message(session, settings, None, "chat-5", "¿Cómo estás?", now=BASE_TIME)
    assert answer.in_domain and not answer.used_llm
    assert "Preciso agua" in answer.text


def test_unverified_numbers_detects_invented_values():
    prompt = "Temperatura promedio: 20,4 °C. Humedad de la tierra: 930"
    assert unverified_numbers("Estoy a 20,4 °C y la tierra marca 930", prompt) == []
    assert unverified_numbers("Estoy a 35 °C", prompt) == ["35"]
