# API HTTP

## Qué va aquí

Rutas de FastAPI y validación de peticiones/respuestas. Los siguientes endpoints son propuestas para implementar.

| Ruta | Uso |
| --- | --- |
| `GET /health` | Comprobar que la API responde. |
| `POST /api/measurements` | Recibir lecturas del dispositivo. |
| `GET /api/measurements/latest` | Obtener la última lectura y su antigüedad. |
| `GET /api/measurements` | Consultar historial limitado por fecha y cantidad. |
| `POST /api/chat` | Recibir una consulta de la página y devolver la respuesta. |

## Recepción cada 30 minutos

El dispositivo envía un JSON a `POST /api/measurements` cada 30 minutos. La API recibe cuando llega la petición: no usa un cron para esperar lecturas.

Ejemplo de estructura; los números son ilustrativos y las escalas deben validarse contra los sensores reales:

```json
{
  "measurement_id": "cebollita-20261105T150000Z",
  "plant_id": "cebollita",
  "measured_at": "2026-11-05T15:00:00Z",
  "humedad_tierra": 1142.4,
  "temp_dht11": 22.0,
  "humedad_aire": 65.2,
  "temp_lm35": 21.57,
  "luz": 2108.0
}
```

El backend añade `received_at` y calcula `temp_promedio` si corresponde al preprocesamiento del modelo. Conservar la fecha de medición y la fecha de recepción por separado.

## Validaciones

- Autenticar el dispositivo con una credencial del backend, por ejemplo en `X-Sensor-Key`.
- Verificar tipos, campos requeridos, identificador de planta y fechas con zona horaria.
- No asumir que humedad de tierra o luz son porcentajes.
- Evitar duplicados por `measurement_id`: un reintento no debe guardar dos lecturas ni disparar dos alertas.
- Guardar antes de confirmar recepción. Rechazar datos inválidos con un error claro.
- Si falta una variable necesaria para el modelo, indicar que no se pudo predecir; no inventarla.

Configurar los orígenes CORS permitidos para React al implementar la interfaz.
