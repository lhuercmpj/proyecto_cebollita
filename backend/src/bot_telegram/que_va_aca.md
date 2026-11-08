# Bot de Telegram

## Qué va aquí

La integración específica de Telegram: registro de manejadores, polling y envío de mensajes.

## Archivos propuestos

- `main.py`: construir la aplicación del bot y ejecutar polling.
- `handlers.py`: manejar `/start`, `/help` y mensajes de texto.

## Flujo inicial

`/start` presenta a Cebollita, explica qué se le puede preguntar y permite registrar el chat destinatario de reportes. `/help` muestra ejemplos. Los mensajes libres se delegan al servicio de conversación.

Ejemplo: «¿Necesitás agua?» debe consultar el mismo servicio que utiliza la página web.

## Avisos automáticos

Enviar las mediciones y el estado cada 30 minutos al chat configurado. Enviar también alertas cuando se detecte necesidad de riego, con control de repetición. El programador de estos reportes pertenece a `jobs/`; esta carpeta implementa la comunicación con Telegram.

El usuario debe haber iniciado el chat con el bot antes de recibir mensajes privados. Guardar el `chat_id` de manera persistente y definir quién puede suscribirse en el prototipo.

## Ejecución

Mantener una sola instancia de polling por bot. Las credenciales se leen desde la configuración del backend. Este componente funciona aunque la página esté cerrada.
