import asyncio
from types import SimpleNamespace

from sqlalchemy import select

from src.bot_telegram import actions
from src.bot_telegram.main import CebollitaBot
from src.db_models import TelegramSubscriber
from src.services.ingest_service import store_device_measurement
from src.services.notification_service import recipients
from src.services.personality import GREETING, OUT_OF_DOMAIN_REPLIES
from tests.conftest import BASE_TIME, SAMPLE_AGUA, FakeLLM, make_payload


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text):
        self.replies.append(text)


class FakeBot:
    def __init__(self):
        self.actions = []

    async def send_chat_action(self, chat_id, action):
        self.actions.append((chat_id, action))


def make_update(text="", chat_id=42, username="diego"):
    message = FakeMessage(text)
    update = SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(username=username),
        effective_message=message,
    )
    return update, message


def run(coro):
    return asyncio.run(coro)


def test_start_subscribes_and_stop_unsubscribes(session_factory, settings):
    bot = CebollitaBot(settings, session_factory, None)
    update, message = make_update()

    run(bot.start(update, None))
    assert message.replies == [GREETING]
    with session_factory() as session:
        assert "42" in recipients(session, settings)

    run(bot.stop(update, None))
    with session_factory() as session:
        assert "42" not in recipients(session, settings)
        assert session.scalar(select(TelegramSubscriber)).active is False

    run(bot.start(update, None))  # volver a suscribirse
    with session_factory() as session:
        assert "42" in recipients(session, settings)


def test_allowlist_blocks_unknown_chats(session, settings):
    settings.telegram_allowed_chat_ids = "1, 2"
    text = actions.subscribe(session, settings, "42", "x")
    assert "TELEGRAM_ALLOWED_CHAT_IDS" in text
    assert session.get(TelegramSubscriber, "42") is None


def test_status_and_history_commands(session_factory, settings):
    bot = CebollitaBot(settings, session_factory, None)
    update, message = make_update()
    run(bot.status(update, None))
    assert "Todavía no tengo mediciones" in message.replies[-1]

    with session_factory() as session:
        store_device_measurement(session, make_payload(SAMPLE_AGUA, BASE_TIME), settings)
    run(bot.status(update, None))
    assert "Preciso agua" in message.replies[-1]
    with session_factory() as session:
        assert "Últimas 24 horas" in actions.history_text(session, settings, now=BASE_TIME)


def test_free_text_goes_through_chat_service(session_factory, settings):
    llm = FakeLLM(reply="¡Tengo sed! 💧", in_domain_answer="NO")
    bot = CebollitaBot(settings, session_factory, llm)
    context = SimpleNamespace(bot=FakeBot())

    update, message = make_update("¿Necesitás agua?")
    run(bot.message(update, context))
    assert message.replies == ["¡Tengo sed! 💧"]
    assert context.bot.actions == [("42", "typing")]

    update, message = make_update("¿Me ayudás con la tarea de matemática?")
    run(bot.message(update, context))
    assert message.replies[0] in OUT_OF_DOMAIN_REPLIES
