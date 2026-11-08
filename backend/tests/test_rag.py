from datetime import timedelta
from pathlib import Path

from src.rag.documents import chunk_document, load_references, parse_reference
from src.rag.import_history import import_rows
from src.rag.ingest import ingest_directory
from src.services.ingest_service import store_device_measurement
from src.services.rag_service import build_context, retrieve_documents, sensor_context
from tests.conftest import BASE_TIME, SAMPLE_AGUA, SAMPLE_BIEN, make_payload

REFERENCES = Path(__file__).resolve().parents[2] / "data" / "references"


def test_reference_documents_have_provenance():
    documents = load_references(REFERENCES)
    assert len(documents) >= 6
    for document in documents:
        assert document.title and document.institution
        assert document.metadata.get("accessed")
        assert document.body
    assert all(doc.source_id != "fuentes" for doc in documents)


def test_chunks_keep_section_title_and_size():
    document = parse_reference(REFERENCES / "rhs-how-to-grow-fittonia.md")
    chunks = chunk_document(document.body, max_chars=400)
    assert len(chunks) >= 6
    assert all(len(chunk.content) <= 700 for chunk in chunks)
    assert any(chunk.content.startswith("Riego: ") for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


def test_ingest_is_idempotent_and_retrieves_relevant_chunk(session, settings, fake_llm):
    first = ingest_directory(session, REFERENCES, fake_llm, settings)
    assert sum(first.values()) > 10
    second = ingest_directory(session, REFERENCES, fake_llm, settings)
    assert sum(second.values()) == 0  # sin cambios, no se vuelve a embeber

    results = retrieve_documents(session, fake_llm, "¿Cada cuánto riego y cómo evito la pudrición de raíces?", settings)
    assert len(results) == settings.rag_top_k
    assert any("Riego" in (chunk.topic or "") for chunk in results)
    assert results[0].score >= results[-1].score


def test_ingest_removes_deleted_sources(session, settings, fake_llm, tmp_path):
    (tmp_path / "a.md").write_text("---\nsource_id: a\ntitle: A\ninstitution: X\n---\n# Luz\nTexto sobre luz", "utf-8")
    (tmp_path / "b.md").write_text("---\nsource_id: b\ntitle: B\ninstitution: X\n---\n# Agua\nTexto sobre agua", "utf-8")
    ingest_directory(session, tmp_path, fake_llm, settings)
    (tmp_path / "b.md").unlink()
    ingest_directory(session, tmp_path, fake_llm, settings)
    results = retrieve_documents(session, fake_llm, "agua", settings)
    assert {chunk.source_id for chunk in results} == {"a"}


def test_sensor_context_summarizes_history(session, settings):
    for hours, sample in ((30, SAMPLE_BIEN), (5, SAMPLE_AGUA), (1, SAMPLE_BIEN)):
        store_device_measurement(session, make_payload(sample, BASE_TIME - timedelta(hours=hours)), settings)

    context = sensor_context(session, settings, now=BASE_TIME)

    assert context.latest is not None
    assert "Últimas 24 horas (2 mediciones" in context.text
    assert "Últimos 7 días (3 mediciones" in context.text
    assert "Última vez «Preciso agua»" in context.text
    assert "ATRASADA" in context.text  # la ultima es de hace 1 h


def test_sensor_context_without_data(session, settings):
    context = sensor_context(session, settings, now=BASE_TIME)
    assert context.latest is None
    assert "Todavía no hay" in context.text


def test_build_context_without_llm_skips_documents(session, settings, fake_llm):
    ingest_directory(session, REFERENCES, fake_llm, settings)
    context = build_context(session, None, "riego", settings, now=BASE_TIME)
    assert context.documents == []


def test_import_history_recomputes_prediction_and_skips_bad_rows(session, settings):
    rows = [
        {"fecha_hora": "2026-10-01 10:00:00", "humedad_tierra": "930,1", "luz": "409", "humedad_aire": "66.05",
         "temp_dht11": "20.40", "temp_lm35": "20.42", "estado": "Preciso agua"},
        {"fecha_hora": "2026-10-01 10:30:00", "humedad_tierra": "", "luz": "409", "humedad_aire": "66",
         "temp_dht11": "20", "temp_lm35": "20"},
        {"fecha_hora": "2026-10-01 10:00:00", "humedad_tierra": "930", "luz": "409", "humedad_aire": "66",
         "temp_dht11": "20", "temp_lm35": "20"},
    ]
    result = import_rows(session, rows, settings)
    assert result.imported == 1
    assert result.duplicated == 1
    assert len(result.skipped) == 1

    again = import_rows(session, rows[:1], settings)
    assert again.imported == 0 and again.duplicated == 1

    context = sensor_context(session, settings, now=BASE_TIME)
    assert "Preciso agua" in context.text
    assert "01/10/2026 10:00" in context.text  # se interpreta en hora de Montevideo
