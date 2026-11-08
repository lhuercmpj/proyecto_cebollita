"""Envio de mensajes a Telegram por la Bot API (sin depender del proceso del bot)."""

import logging
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LENGTH = 4096


class Notifier(Protocol):
    @property
    def enabled(self) -> bool: ...

    async def send(self, chat_id: str, text: str) -> None: ...


class TelegramSendError(RuntimeError):
    pass


class TelegramNotifier:
    def __init__(self, token: str, timeout: float = 15.0) -> None:
        self._token = token
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def send(self, chat_id: str, text: str) -> None:
        if not self.enabled:
            raise TelegramSendError("TELEGRAM_BOT_TOKEN no configurado")
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        body = {"chat_id": chat_id, "text": text[:TELEGRAM_MAX_LENGTH]}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            # No incluir la URL: contiene el token.
            raise TelegramSendError(f"Error de red con Telegram: {type(exc).__name__}") from None
        if response.status_code != 200:
            try:
                description = response.json().get("description", "")
            except ValueError:
                description = response.text[:200]
            raise TelegramSendError(f"Telegram respondio {response.status_code}: {description}")
