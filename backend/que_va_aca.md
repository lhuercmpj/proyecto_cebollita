# Backend

## Qué va aquí

API de FastAPI, recepción de sensores, servicios de conversación y componentes de Telegram.

- `app/main.py`: crear FastAPI y registrar rutas.
- `app/api/`: endpoints.
- `app/services/`: lógica compartida.
- `app/telegram_bot/`: manejadores de Telegram y ejecución de polling.
- `app/jobs/`: tareas periódicas.
- `requirements.txt`: dependencias de Python; fijar versiones probadas al implementarlas.
- `.env.example`: nombres de configuración sin secretos.
- `.env`: valores locales reales, excluidos de Git.

## Variables propuestas

```dotenv
TELEGRAM_BOT_TOKEN=
GEMINI_API_KEY=
TELEGRAM_CHAT_ID=
SENSOR_API_KEY=
REPORT_INTERVAL_MINUTES=30
```

El identificador del chat se obtiene cuando el usuario inicia una conversación con el bot. Para el prototipo se puede configurar un único destinatario; si hay varios, guardar las suscripciones de forma persistente.

## Procesos

La API debe permanecer disponible para recibir mediciones. El polling debe tener una sola instancia por bot. El programador de reportes también debe tener una única instancia activa: no iniciarlo en cada proceso de FastAPI, porque eso duplicaría los avisos.

Una organización sencilla es ejecutar API, bot y programador como procesos separados que reutilizan servicios y almacenamiento persistente. Definir sus comandos reales cuando estén implementados.

## Persistencia

La última lectura, el historial, los destinatarios y el estado de alertas no deben depender exclusivamente de variables en memoria. Para el prototipo se pueden usar archivos con escrituras controladas o SQLite; si varios procesos escriben, preferir SQLite y documentar su ubicación.
