# Backend

La API coordina la comunicacion con la ESP32, valida su respuesta y persiste
las mediciones. El simulador usa el mismo servicio de prediccion que sirve como
referencia para verificar el firmware.

## Endpoints principales

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/health` | Estado de API, base y modelo de referencia. |
| POST | `/api/measurements/request` | Solicita una lectura a la ESP32 o simulador. |
| POST | `/api/measurements` | Permite recibir una lectura en modo push. |
| GET | `/api/measurements/latest` | Devuelve la lectura mas reciente. |
| GET | `/api/measurements?limit=50` | Lista el historial reciente. |

Los endpoints POST requieren `X-API-Key`.

## Contrato del dispositivo

El dispositivo expone `POST /api/medir` y valida `X-API-Key`. El backend envia
`timestamp_unix` en el cuerpo y espera el mismo JSON producido por el firmware:
lecturas dentro de `datos`, prediccion en `clase`, `estado` y `confianza`, el
arreglo `probabilidades` y los indicadores de `calidad`. El esquema exacto se
puede inspeccionar en <http://localhost:8081/docs> con el simulador.

El contrato supone que el LM35 siempre responde: `temp_lm35` debe ser numerico,
debe haber al menos una lectura valida y `solo_dht_para_temperatura` debe ser
`false`. La version del modelo y el identificador de la medicion los agrega el
backend al persistir, porque son datos propios del sistema y no del sensor.

