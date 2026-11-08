# Maceta Inteligente — Cebollita

Primer avance del backend para la Tarea 3. Incluye:

- API HTTP con FastAPI.
- PostgreSQL con la extension pgvector.
- Simulador HTTP que implementa el contrato previsto para la ESP32.
- Persistencia de mediciones y predicciones sin duplicados.
- Implementacion Python de referencia del modelo exportado a C.
- Validacion contra los 12 vectores incluidos en el modelo original.

## Inicio rapido

1. Copiar `.env.example` a `.env` si se desea cambiar la configuracion local.
2. Construir e iniciar los servicios:

   ```powershell
   docker compose up --build
   ```

3. Abrir Swagger en <http://localhost:8000/docs>.
4. Ejecutar `POST /api/measurements/request`.

El backend llamara a `POST /api/medir` del simulador, verificara la prediccion y
guardara la lectura en PostgreSQL.

## Ejemplo con PowerShell

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8000/api/measurements/request?sample_index=0"
```

Consultar la ultima medicion:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/measurements/latest"
```

Los valores de `sample_index` van de `0` a `11` y corresponden a los vectores
de verificacion del modelo.

## Sustituir el simulador por la ESP32

La placa debe exponer `POST /api/medir` y responder con el JSON implementado
por el firmware: `clase`, `estado`, `confianza`,
`timestamp_unix`, `datos`, `probabilidades` y `calidad`. El backend envia la
hora UTC en el cuerpo de cada solicitud y asume que tanto el DHT11 como el LM35
producen lecturas validas.

Configurar en `.env` una URL accesible desde Docker, por ejemplo:

```dotenv
SENSOR_DEVICE_URL=http://192.168.1.50
SENSOR_TIMEOUT_SECONDS=20
```

Luego reiniciar solamente la API:

```powershell
docker compose up -d --force-recreate api
```

## Servicios

| Servicio | Puerto | Uso |
| --- | ---: | --- |
| API | 8000 | Backend principal y Swagger |
| Simulador | 8081 | Contrato HTTP de la ESP32 |
| PostgreSQL/pgvector | 5433 | Persistencia local |

## Pruebas

Dentro de la imagen de la API:

```powershell
docker compose run --rm api pytest
```

Para desarrollo local, instalar `backend/requirements-dev.txt` y ejecutar:

```powershell
pytest
```

## Alcance pendiente

- Programacion automatica cada 30 minutos.
- Telegram y alertas de riego.
- Gemini y personalidad de Cebollita.
- Ingestion e indexacion de documentos para RAG.
- Frontend React.

