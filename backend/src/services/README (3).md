# Servicios compartidos

## Qué va aquí

La lógica reutilizada por la página, Telegram y los trabajos periódicos.

| Archivo propuesto | Responsabilidad |
| --- | --- |
| `sensor_service.py` | Validar, deduplicar, guardar y recuperar mediciones. |
| `prediction_service.py` | Aplicar el preprocesamiento y ejecutar el modelo de la tarea 2. |
| `rag_service.py` | Recuperar historial relevante y fragmentos científicos. |
| `gemini_service.py` | Construir la llamada a Gemini y manejar su respuesta. |
| `chat_service.py` | Coordinar una consulta con contexto y personalidad. |
| `notification_service.py` | Construir y enviar reportes y alertas. |

## Flujo al recibir sensores

Guardar una lectura válida, evaluar si es suficientemente reciente y ejecutar la predicción con las mismas variables y transformaciones del entrenamiento. Evaluar el aviso de riego según el resultado y la política de repetición.

No definir umbrales de riego arbitrarios: usar el modelo y/o criterios documentados para los sensores y la especie.

## Flujo de conversación

Web y Telegram llaman a `chat_service.py`. El servicio recupera información relevante, incorpora el estado predictivo y las fuentes, y solicita una respuesta de Gemini con la personalidad de Cebollita. Mantener el dominio de conversación asociado a la planta.

## Reporte periódico

Construir el resumen desde la última medición persistida, incluyendo fecha y estado. Si no hay lecturas nuevas, indicarlo. Los valores numéricos del reporte se toman de los datos guardados; Gemini puede redactar el mensaje, pero no modificar ni inventar esas cifras.
