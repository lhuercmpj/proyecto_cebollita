# Aplicación Python

## Qué va aquí

El paquete principal del backend. Mantener `__init__.py` para identificar el paquete y `main.py` como entrada de FastAPI.

`main.py` crea la aplicación y registra rutas, configuración y recursos. La lógica de conversación, sensores, predicción y avisos va en servicios.

## Subcarpetas

- `api/`: entrada HTTP desde React y el dispositivo.
- `services/`: operaciones compartidas.
- `telegram_bot/`: entrada y salida por Telegram.
- `jobs/`: ejecución periódica de reportes.

## Ejemplo de responsabilidad

Al llegar una medición, la ruta valida la petición y llama al servicio de sensores. Ese servicio guarda los datos y coordina predicción y alertas. El archivo principal no debe contener todo ese flujo.
