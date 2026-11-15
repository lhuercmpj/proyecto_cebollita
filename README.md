# Maceta Inteligente — Cebollita

Chatbot de Telegram con Gemini y RAG, y una página web, para Cebollita, una
fitonia (_Fittonia albivenis_) con sensores conectados a una ESP32. El backend
(`backend/`) corresponde a la Tarea 3; la página (`frontend/`) es React + Vite.

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
- **Página web** (`frontend/`): chat con Cebollita dentro de un celular, planta
  que cambia según el estado del modelo, panel con las últimas mediciones,
  fondo según la hora (mañana, tarde, noche) y reproductor de música. Ver
  [Página web](#página-web-frontend).

## Inicio rápido

1. Copiar `.env.example` a `.env` y completar `GEMINI_API_KEY` y
   `TELEGRAM_BOT_TOKEN` (ver abajo). Sin claves todo funciona igual, pero no se
   envían mensajes y el chat responde solo con los datos de los sensores.
2. Levantar base, simulador, API, programador y página web:

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

Swagger: <http://localhost:8000/docs>. Página web: <http://localhost:5173>
(ver [Página web](#página-web-frontend)).

> Si ya tenían la base creada con la versión anterior, recrearla para que se
> agreguen las columnas y tablas nuevas: `docker compose down -v` (borra los
> datos de desarrollo).

## Claves necesarias

| Variable                    | Cómo obtenerla                                                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `TELEGRAM_BOT_TOKEN`        | Hablar con [@BotFather](https://t.me/BotFather), `/newbot`, copiar el token.                                                         |
| `GEMINI_API_KEY`            | Crear una key en <https://aistudio.google.com/apikey>.                                                                               |
| `TELEGRAM_CHAT_ID`          | Opcional: chat fijo que siempre recibe los reportes.                                                                                 |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Opcional: lista de chats que pueden suscribirse.                                                                                     |
| `CORS_ORIGINS`              | Orígenes de la página web que pueden llamar a la API, separados por coma. Por defecto los puertos 5173 (Docker) y 5174 (`npm run dev`), en `localhost` y `127.0.0.1`. |

`GEMINI_MODEL` usa por defecto el alias `gemini-flash-latest` (el Flash estable
vigente). Se puede fijar una versión concreta si hace falta: si el alias
responde `503` (alta demanda) o `429` (cuota), probar con un modelo concreto,
por ejemplo `GEMINI_MODEL=gemini-3.5-flash`, y recrear la API con
`docker compose up -d api`.

## Servicios

| Servicio    | Puerto | Uso                                                                 |
| ----------- | -----: | ------------------------------------------------------------------- |
| `api`       |   8000 | Backend, Swagger, `POST /api/chat` y `GET /api/measurements/latest` |
| `simulator` |   8081 | Contrato HTTP de la ESP32                                           |
| `db`        |   5433 | PostgreSQL + pgvector                                               |
| `scheduler` |      — | Medición, reporte y alertas cada 30 min (una sola instancia)        |
| `bot`       |      — | Bot de Telegram por polling (perfil `telegram`)                     |
| `frontend`  |   5173 | Página web (build de producción servido por nginx)                  |

## Página web (frontend)

React + Vite en `frontend/`. Los detalles (organización, scripts y cómo
regenerar imágenes y música) están en [`frontend/instrucciones.md`](frontend/instrucciones.md).

Sale junto con el resto con `docker compose up --build` y queda en
<http://localhost:5173>. Para levantar solo la página: `docker compose up -d --build frontend`.
La URL de la API que usa el navegador se fija al compilar (`VITE_API_URL` en el
`.env`, por defecto `http://localhost:8000`): si la cambian, reconstruir con
`docker compose up -d --build frontend`.

Para desarrollar con recarga en vivo se corre Vite localmente (requiere Node
20.19+), en el puerto 5174, sin apagar nada: puede convivir con el contenedor.

```powershell
cd frontend
npm install
copy .env.example .env   # VITE_API_URL=http://localhost:8000
npm run dev              # http://localhost:5174
```

Si la página corre en otro origen, agregarlo a `CORS_ORIGINS`.

- **Chat** en un celular, con botones de sugerencia, hora por mensaje y una
  tarjeta con las lecturas. Usa `POST /api/chat`, el mismo servicio que el bot.
- **Planta con estados**: cuatro versiones (`Estoy bien`, `Preciso luz`,
  `Preciso agua`, `Estoy mal`) según la última predicción, con una burbuja que
  dice qué le pasa.
- **Panel de mediciones**, consultado cada minuto a `/api/measurements/latest`.
  Marca la lectura como atrasada pasados 40 minutos. Si todavía no hay
  mediciones muestra «Esperando mis datos…».
- **Fondo según la hora**: mañana (6–12), tarde (12–19) y noche (19–6), con
  saludo, partículas y sombra de la planta en el suelo. `?tema=manana`,
  `?tema=tarde` o `?tema=noche` fuerza uno.
- **Música**: jazz, bossa, clásica y pop, con listas fijas de temas de YouTube
  (no hay archivos .mp3 en el proyecto).

La humedad de la tierra y la luz se muestran como lecturas crudas (0–4095, sin
calibrar), nunca como porcentaje. La página no guarda claves: solo usa
`VITE_API_URL`.

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
retoma el ritmo normal. El programador toma un _advisory lock_ de PostgreSQL,
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

Inspirada en Edna Moda: una diseñadora de alta costura legendaria, pequeña y
genial. Cebollita se considera una obra maestra ("alta costura de la selva"),
es directa, impaciente y teatral, da órdenes cortas, llama "querido" o
"darling" a quien la cuida y no tolera la mediocridad. En el fondo le importa
mucho que la cuiden bien. Como fitonia, cuando le falta agua se "desmaya" y lo
vive como una tragedia de pasarela. Nunca inventa datos y separa lo que estima
el modelo de sus consejos. No cita frases textuales de la película: el estilo
está descrito con rasgos propios. Detalle en
`backend/src/services/personality.py`; los textos fijos de reportes y alertas
están en `backend/src/services/report_service.py`.

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

| Tabla                  | Contenido                                                |
| ---------------------- | -------------------------------------------------------- |
| `measurements`         | Lecturas (ESP32 o histórico), predicción y JSON original |
| `telegram_subscribers` | Chats que hicieron `/start`                              |
| `alert_states`         | Última alerta enviada y fallos seguidos del dispositivo  |
| `job_runs`             | Cada ejecución del programador                           |
| `notification_logs`    | Cada mensaje automático enviado o fallido                |
| `document_chunks`      | Fragmentos científicos con embedding (pgvector)          |
| `chat_messages`        | Conversaciones (memoria del chat y logs para el informe) |
