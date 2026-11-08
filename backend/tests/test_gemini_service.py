from types import SimpleNamespace

import pytest

from src.services.gemini_service import (
    ChatTurn,
    GeminiClient,
    GeminiError,
    GeminiNotConfiguredError,
)


class FakeModels:
    def __init__(self):
        self.generate_kwargs = None
        self.embed_calls = []

    def generate_content(self, **kwargs):
        self.generate_kwargs = kwargs
        return SimpleNamespace(text="  ¡Hola, soy Cebollita!  ")

    def embed_content(self, **kwargs):
        self.embed_calls.append(kwargs)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in kwargs["contents"]])


def make_client(settings):
    client = GeminiClient(settings)  # usa el SDK real; no hace llamadas al construirse
    fake = FakeModels()
    client._client = SimpleNamespace(models=fake)
    return client, fake


def test_requires_api_key(settings):
    settings.gemini_api_key = ""
    with pytest.raises(GeminiNotConfiguredError):
        GeminiClient(settings)


def test_generate_sends_system_prompt_and_turns(settings):
    client, fake = make_client(settings)

    text = client.generate("sistema", [ChatTurn("user", "hola"), ChatTurn("model", "hola!"), ChatTurn("user", "¿y?")])

    assert text == "¡Hola, soy Cebollita!"
    kwargs = fake.generate_kwargs
    assert kwargs["model"] == settings.gemini_model
    assert kwargs["config"].system_instruction == "sistema"
    assert [content.role for content in kwargs["contents"]] == ["user", "model", "user"]


def test_embed_batches_and_normalizes(settings):
    client, fake = make_client(settings)

    vectors = client.embed([f"texto {i}" for i in range(120)], "RETRIEVAL_DOCUMENT")

    assert len(vectors) == 120
    assert [len(call["contents"]) for call in fake.embed_calls] == [50, 50, 20]
    assert fake.embed_calls[0]["config"].output_dimensionality == settings.embedding_dimensions
    assert vectors[0] == pytest.approx([0.6, 0.8])


def test_errors_are_wrapped(settings):
    client, fake = make_client(settings)

    def boom(**_):
        raise RuntimeError("quota")

    fake.generate_content = boom
    with pytest.raises(GeminiError):
        client.generate("s", [ChatTurn("user", "x")])
