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


def test_choose_flash_model_prefers_newest_stable_text_flash():
    from src.services.gemini_service import choose_flash_model

    models = [
        ("gemini-2.5-flash", ["generateContent"]),
        ("gemini-3-flash", ["generateContent", "countTokens"]),
        ("gemini-3-flash-lite", ["generateContent"]),
        ("gemini-3-flash-image", ["generateContent"]),
        ("gemini-3-pro", ["generateContent"]),
        ("gemini-embedding-001", ["embedContent"]),
        ("gemini-3.1-flash-preview", ["generateContent"]),
    ]
    assert choose_flash_model(models) == "gemini-3-flash"
    # Si solo quedan Lite, se usa Lite como ultimo recurso.
    assert choose_flash_model([("gemini-3-flash-lite", ["generateContent"])]) == "gemini-3-flash-lite"
    assert choose_flash_model([("gemini-embedding-001", ["embedContent"])]) is None


def test_generate_falls_back_when_model_is_not_found(settings):
    client, fake = make_client(settings)

    class NotFound(Exception):
        code = 404

    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == settings.gemini_model:
            raise NotFound("models/x is not found")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    fake.list = lambda: [
        SimpleNamespace(name="models/gemini-3-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-embedding-001", supported_actions=["embedContent"]),
    ]

    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    assert calls == [settings.gemini_model, "gemini-3-flash"]
    # La siguiente llamada ya usa el modelo encontrado.
    client.generate("s", [ChatTurn("user", "y")])
    assert calls[-1] == "gemini-3-flash"


def test_generate_retries_then_switches_model_when_overloaded(settings):
    client, fake = make_client(settings)
    client._sleep = lambda seconds: None
    settings_model = settings.gemini_model

    class Overloaded(Exception):
        code = 503

    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] in (settings_model, "gemini-3.8-flash"):
            raise Overloaded("high demand")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    fake.list = lambda: [
        SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.5-flash", supported_actions=["generateContent"]),
    ]

    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    # Sin reintentos: configurado, luego el 3.8 (no hay Lite) saturado, luego el 3.5.
    assert calls == [settings_model, "gemini-3.8-flash", "gemini-3.5-flash"]


def test_non_transient_errors_are_not_retried(settings):
    client, fake = make_client(settings)
    client._sleep = lambda seconds: None

    class BadKey(Exception):
        code = 403

    calls = []

    def generate_content(**kwargs):
        calls.append(1)
        raise BadKey("invalid key")

    fake.generate_content = generate_content
    with pytest.raises(GeminiError):
        client.generate("s", [ChatTurn("user", "x")])
    assert calls == [1]


def test_timeout_switches_model_without_retrying(settings):
    client, fake = make_client(settings)
    client._sleep = lambda seconds: None
    settings_model = settings.gemini_model

    class ReadTimeout(Exception):
        pass

    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == settings_model:
            raise ReadTimeout("timed out")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    fake.list = lambda: [SimpleNamespace(name="models/gemini-3.5-flash", supported_actions=["generateContent"])]

    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    assert calls == [settings_model, "gemini-3.5-flash"]


def test_gateway_timeout_switches_model_and_thinking_is_low(settings):
    client, fake = make_client(settings)
    client._sleep = lambda seconds: None
    settings_model = settings.gemini_model

    class Deadline(Exception):
        code = 504

    calls = []

    def generate_content(**kwargs):
        calls.append((kwargs["model"], kwargs["config"].thinking_config))
        if kwargs["model"] == settings_model:
            raise Deadline("DEADLINE_EXCEEDED")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    fake.list = lambda: [SimpleNamespace(name="models/gemini-3.5-flash", supported_actions=["generateContent"])]

    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    assert [model for model, _ in calls] == [settings_model, "gemini-3.5-flash"]
    assert str(calls[0][1].thinking_level).endswith("LOW")


def test_model_without_thinking_support_is_called_without_it(settings):
    client, fake = make_client(settings)

    class BadRequest(Exception):
        code = 400

    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["config"].thinking_config)
        if kwargs["config"].thinking_config is not None:
            raise BadRequest("thinking_level is not supported for this model")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    assert calls[0] is not None and calls[-1] is None


def test_lite_is_used_when_all_flash_are_overloaded(settings):
    client, fake = make_client(settings)
    client._sleep = lambda seconds: None

    class Overloaded(Exception):
        code = 503

    calls = []

    def generate_content(**kwargs):
        calls.append(kwargs["model"])
        if "lite" not in kwargs["model"]:
            raise Overloaded("high demand")
        return SimpleNamespace(text="ok")

    fake.generate_content = generate_content
    fake.list = lambda: [
        SimpleNamespace(name="models/gemini-3.8-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.7-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-3.8-flash-lite", supported_actions=["generateContent"]),
    ]

    assert client.generate("s", [ChatTurn("user", "x")]) == "ok"
    # Tras fallar el configurado se va directo al Lite, sin pasar por los otros Flash.
    assert calls == [settings.gemini_model, "gemini-3.8-flash-lite"]
