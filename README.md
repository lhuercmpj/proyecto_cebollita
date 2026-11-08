# Maceta Inteligente — Cebollita

Backend de la Tarea 3: chatbot de Telegram con Gemini y RAG para Cebollita, una
fitonia (*Fittonia albivenis*) con sensores conectados a una ESP32.

## Qué hace

- **API HTTP** (FastAPI) con PostgreSQL + pgvector.
- **Simulador** de la ESP32 con el mismo contrato que el firmware.
- **Medición automática** cada 30 minutos: pide la lectura, la guarda, envía el
  reporte a Telegram y evalúa alertas (`src/jobs/sensor_report_job.py`).
- **Alertas** cuando el modelo estima `Preciso agua`, `Preciso luz` o
  `Estoy mal`, sin repetirlas en cada medición (recordatorio a las 3 h y aviso
  de recuperación al volver a `Estoy bien`).
- **Bot de Telegram** (`src/bot_telegram/`) con `/start`, `/estado`,
  `/historial`, `/ayuda`, `/baja` y conversación libre.
- **Gemini + personalidad**: respuestas en primera persona con la personalidad
  de Cebollita (`src/services/personality.py`).
- **Filtro de dominio**: solo responde sobre la planta (reglas + clasificación
  con Gemini + reglas del prompt).
- **RAG**: historial de sensores por consultas SQL y documentos científicos
  indexados en pgvector con embeddings de Gemini.
- Modelo de la Tarea 2 replicado en Python y validado contra sus 12 vectores.

## Inicio rápido

1. Copiar `.env.example` a `.env` y completar `GEMINI_API_KEY` y
   `TELEGRAM_BOT_TOKEN` (ver abajo). Sin claves todo funciona igual, pero no se
   envían mensajes y el chat responde solo con los datos de los sensores.
2. Levantar base, simulador, API y programador:

   ```powershell
   docker compose up --build
   ```

3. Indexar los documentos científicos (una vez, o cuando cambien):

   ```powershell
   docker compose run --rm api python -m src.rag.ingest
   ```

4. Levantar el bot de Telegram:

   ```powershell
   docker compose --profile telegram up -d bot
   ```

5. En Telegram, abrir el bot y enviar `/start`: ese chat queda suscripto a los
   reportes y alertas.

Swagger: <http://localhost:8000/docs>.

> Si ya tenían la base creada con la versión anterior, recrearla para que se
> agreguen las columnas y tablas nuevas: `docker compose down -v` (borra los
> datos de desarrollo).

## Claves necesarias

| Variable | Cómo obtenerla |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Hablar con [@BotFather](https://t.me/BotFather), `/newbot`, copiar el token. |
| `GEMINI_API_KEY` | Crear una key en <https://aistudio.google.com/apikey>. |
| `TELEGRAM_CHAT_ID` | Opcional: chat fijo que siempre recibe los reportes. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Opcional: lista de chats que pueden suscribirse. |

`GEMINI_MODEL` usa por defecto el alias `gemini-flash-latest` (el Flash estable
vigente). Se puede fijar una versión concreta si hace falta.

## Servicios

| Servicio | Puerto | Uso |
| --- | ---: | --- |
| `api` | 8000 | Backend, Swagger y `POST /api/chat` |
| `simulator` | 8081 | Contrato HTTP de la ESP32 |
| `db` | 5433 | PostgreSQL + pgvector |
| `scheduler` | — | Medición, reporte y alertas cada 30 min (una sola instancia) |
| `bot` | — | Bot de Telegram por polling (perfil `telegram`) |

## Flujo cada 30 minutos

1. El programador llama a `POST /api/medir` de la ESP32 (o del simulador).
2. Valida la respuesta, recalcula la predicción como control y guarda la
   medición. Si la misma medición llega dos veces, no se duplica.
3. Envía el reporte a todos los chats suscriptos. Las cifras del reporte salen
   de la base, no de Gemini.
4. Evalúa la alerta: avisa al cambiar a `Preciso agua`/`Preciso luz`/`Estoy mal`,
   recuerda a las 3 h si sigue igual y avisa cuando vuelve a `Estoy bien`.
5. Si la placa no responde, registra el error en `job_runs` sin crear una
   medición y avisa una sola vez por racha de fallos.

Al reiniciarse no se envían de golpe los reportes omitidos: se mide una vez y se
retoma el ritmo normal. El programador toma un *advisory lock* de PostgreSQL,
así que una segunda instancia termina sola.

Las mediciones que llegan por la API (`/api/measurements` y
`/api/measurements/request`) también evalúan alertas al momento.

## RAG

- **Sensores**: `src/services/rag_service.py` arma un bloque con la última
  medición (marcando si está atrasada), un resumen de las últimas 24 h y de los
  últimos 7 días (promedios, mínimos, máximos, estados y la última vez que
  necesitó agua).
- **Documentos**: `data/references/` tiene resúmenes propios de fuentes
  científicas sobre la fitonia (NC State Extension, UF/IFAS, RHS, Kew,
  NParks) y una guía interna de sensores. `python -m src.rag.ingest` los divide
  por secciones, genera embeddings con `gemini-embedding-001` (768 dimensiones)
  y los guarda en `document_chunks`. La pregunta (más el estado actual) se
  embebe y se recuperan los 4 fragmentos más cercanos por distancia coseno.
- **Prompt**: personalidad + reglas (sistema) y, en el mensaje, los bloques
  `DATOS DE SENSORES`, `CONOCIMIENTO CIENTÍFICO` y la pregunta. Se envían
  también los últimos turnos de la conversación.
- Si Gemini falla o no hay key, Cebollita responde solo con los datos
  guardados.

### Dataset histórico

Cuando esté el CSV limpio de la Tarea 2:

```powershell
docker compose run --rm api python -m src.rag.import_history data/sensors/ARCHIVO.csv --dry-run
docker compose run --rm api python -m src.rag.import_history data/sensors/ARCHIVO.csv
```

Columnas: `fecha_hora`, `humedad_tierra`, `luz`, `humedad_aire`, `temp_dht11`,
`temp_lm35` (y opcional `estado`). La predicción se recalcula con el modelo
actual; la etiqueta histórica queda aparte en `raw_payload`. Ojo con el cambio
de sensor de luz: si el CSV usa el sensor anterior, revisar la escala antes de
importar.

## Personalidad de Cebollita

Dramática pero adorable: como buena fitonia se "desmaya" cuando le falta agua y
"revive" al regarla, y lo exagera con humor. Cariñosa, habla de vos, curiosa y
un poco sabionda con su especie, y siempre honesta con los datos: no inventa
cifras y separa lo que estima el modelo de sus consejos. Detalle completo en
`backend/src/services/personality.py`.

## Ejemplos con PowerShell

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/measurements/request?sample_index=0"
Invoke-RestMethod -Uri "http://localhost:8000/api/measurements/latest"
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/chat" `
  -ContentType "application/json" -Body '{"message":"¿Necesitás riego hoy?"}'
```

Los valores de `sample_index` van de `0` a `11` (vectores de verificación del
modelo).

## Sustituir el simulador por la ESP32

La placa expone `POST /api/medir` con el JSON del firmware. Configurar en
`.env` una URL accesible desde Docker y reiniciar `api` y `scheduler`:

```dotenv
SENSOR_DEVICE_URL=http://192.168.1.50
SENSOR_TIMEOUT_SECONDS=20
```

```powershell
docker compose up -d --force-recreate api scheduler
```

## Pruebas

```powershell
docker compose run --rm api pytest
```

Localmente (`pip install -r backend/requirements-dev.txt`) los tests usan
SQLite. Para probar contra PostgreSQL + pgvector:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://cebollita:cebollita_dev@localhost:5433/cebollita_test"
pytest
```

Gemini y Telegram se reemplazan por clientes falsos en los tests: no hace falta
ninguna clave para correrlos.

## Tablas

| Tabla | Contenido |
| --- | --- |
| `measurements` | Lecturas (ESP32 o histórico), predicción y JSON original |
| `telegram_subscribers` | Chats que hicieron `/start` |
| `alert_states` | Última alerta enviada y fallos seguidos del dispositivo |
| `job_runs` | Cada ejecución del programador |
| `notification_logs` | Cada mensaje automático enviado o fallido |
| `document_chunks` | Fragmentos científicos con embedding (pgvector) |
| `chat_messages` | Conversaciones (memoria del chat y logs para el informe) |

## Pendiente

- Probar con el token de Telegram y la key de Gemini reales y ajustar el prompt.
- Indexar los documentos con la key (`python -m src.rag.ingest`).
- Importar el dataset histórico limpio.
- Probar con la ESP32 real.
- Frontend React (opcional según la letra).
