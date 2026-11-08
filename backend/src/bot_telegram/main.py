"""Bot de Telegram de Cebollita (polling).

    python -m src.bot_telegram.main

Ejecutar UNA sola instancia por token. Los reportes de cada 30 minutos los
envia el programador (``src.jobs.sensor_report_job``), no este proceso.
"""

import asyncio
import logging

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from src.bot_telegram import actions
from src.config import Settings, get_settings
from src.services.chat_service import answer_message
from src.services.gemini_service import GeminiNotConfiguredError, LLMClient, build_client
from src.services.personality import HELP

logger = logging.getLogger("cebollita.bot")


class CebollitaBot:
    def __init__(self, settings: Settings, session_factory, llm: LLMClient | None) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.llm = llm

    def _run(self, func, *args):
        with self.session_factory() as session:
            return func(session, *args)

    async def start(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        chat = update.effective_chat
        user = update.effective_user
        text = await asyncio.to_thread(
            self._run, actions.subscribe, self.settings, str(chat.id), user.username if user else None
        )
        await update.effective_message.reply_text(text)

    async def help(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(HELP)

    async def stop(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        text = await asyncio.to_thread(self._run, actions.unsubscribe, str(update.effective_chat.id))
        await update.effective_message.reply_text(text)

    async def status(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        text = await asyncio.to_thread(self._run, actions.status_text, self.settings)
        await update.effective_message.reply_text(text)

    async def history(self, update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
        text = await asyncio.to_thread(self._run, actions.history_text, self.settings)
        await update.effective_message.reply_text(text)

    async def message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        if not message or not message.text:
            return
        chat_id = str(update.effective_chat.id)
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        answer = await asyncio.to_thread(
            self._run,
            answer_message,
            self.settings,
            self.llm,
            f"telegram-{chat_id}",
            message.text,
            "telegram",
        )
        logger.info(
            "chat=%s dominio=%s metodo=%s fuentes=%s",
            chat_id,
            answer.in_domain,
            answer.method,
            ",".join(answer.sources),
        )
        await message.reply_text(answer.text)

    async def error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Error atendiendo un mensaje", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Uy, me mareé 🥴 Algo falló de mi lado. ¿Me lo repetís en un ratito?"
            )

    def register(self, application: Application) -> None:
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler(["ayuda", "help"], self.help))
        application.add_handler(CommandHandler(["estado", "status"], self.status))
        application.add_handler(CommandHandler("historial", self.history))
        application.add_handler(CommandHandler(["baja", "stop"], self.stop))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message))
        application.add_error_handler(self.error)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # sus logs incluyen la URL con el token

    from src.database import SessionLocal, create_tables

    settings = get_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("Falta TELEGRAM_BOT_TOKEN en el .env (crear el bot con @BotFather).")
    try:
        llm = build_client(settings)
    except GeminiNotConfiguredError:
        logger.warning("GEMINI_API_KEY vacia: el bot respondera solo con los datos de los sensores")
        llm = None

    create_tables()
    application = Application.builder().token(settings.telegram_bot_token).build()
    CebollitaBot(settings, SessionLocal, llm).register(application)
    logger.info("Bot de Cebollita iniciado (polling)")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
