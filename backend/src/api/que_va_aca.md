# API HTTP

## Qué va aquí

Rutas de FastAPI y validación de peticiones y respuestas.

| Ruta | Uso |
| --- | --- |
| `GET /health` | Comprobar la API, la base y el modelo. |
| `POST /api/measurements/request` | Pedir una medición a la ESP32 y guardarla. |
| `POST /api/measurements` | Recibir manualmente el mismo JSON de la ESP32. |
| `GET /api/measurements/latest` | Obtener la última lectura. |
| `GET /api/measurements` | Consultar el historial reciente. |
| `POST /api/chat` | Futuro endpoint del chatbot web. |

## Medición cada 30 minutos

El backend programará la tarea periódica. En cada ejecución llamará a
`POST /api/medir` en la ESP32 y enviará la hora UTC:

```json
{
  "timestamp_unix": 1794142800
}
```

La placa mide los sensores, ejecuta el modelo y devuelve el contrato definido
en `schemas/measurement.py`: `datos`, `clase`, `estado`, `confianza`,
`probabilidades` y `calidad`. El simulador implementa ese mismo contrato.

El backend agrega al persistir los datos que le pertenecen: `measurement_id`,
`plant_id`, `received_at` y la versión conocida del modelo. También vuelve a
calcular la predicción como control de equivalencia con el firmware.

## Validaciones

- No asumir que humedad de tierra o luz son porcentajes: conservan la escala ADC.
- Exigir fecha válida, cuatro clases y probabilidades coherentes.
- Exigir lecturas válidas tanto del DHT11 como del LM35.
- Verificar que `temp_promedio` sea el promedio de ambos sensores.
- No reintentar automáticamente `POST /api/medir`: cada llamada genera una nueva medición.
- Guardar el JSON original de la placa en `raw_payload` para trazabilidad.

Configurar los orígenes CORS permitidos para React al implementar la interfaz.
