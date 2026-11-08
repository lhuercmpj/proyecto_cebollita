# Bot de Telegram

Implementado:

- `main.py`: aplicación de python-telegram-bot con polling
  (`python -m src.bot_telegram.main`).
- `actions.py`: lógica de los comandos, independiente de Telegram.

Comandos: `/start` (presenta a Cebollita y suscribe el chat), `/ayuda`,
`/estado` (última medición), `/historial` (24 h y 7 días), `/baja` (deja de
recibir reportes). Los mensajes libres van a `services/chat_service.py`.

Los reportes y alertas automáticos los envía el programador
(`jobs/sensor_report_job.py`) por la Bot API, así que siguen funcionando aunque
este proceso se reinicie. Los chats suscriptos se guardan en
`telegram_subscribers`. `TELEGRAM_ALLOWED_CHAT_IDS` limita quién puede
suscribirse.
