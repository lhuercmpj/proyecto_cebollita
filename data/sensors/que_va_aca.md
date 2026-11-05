# Datos de sensores

## Qué va aquí

El CSV histórico de la tarea 2, sus versiones procesadas y las nuevas lecturas recibidas por el backend. Si se elige SQLite, documentar dónde se guarda la base; esta carpeta puede conservar los CSV de origen y exportaciones.

## Campos del proyecto

El dataset histórico utiliza campos como `fecha_hora`, `registro`, `humedad_tierra`, `temp_dht11`, `humedad_aire`, `temp_lm35`, `temp_promedio`, `luz`, `estado` y `periodo`.

Las nuevas lecturas deben poder relacionarse con ese formato, conservando además un identificador único y las fechas de medición y recepción. `estado` puede ser una etiqueta histórica o una predicción: identificar su procedencia para no confundirlas.

## Lecturas nuevas

Se prevé recibir una lectura cada 30 minutos. Conservar el historial y permitir recuperar la última lectura para el reporte automático de Telegram. No sobrescribir todo el historial con cada recepción.

## Precauciones del dataset

- Confirmar la escala de humedad de tierra; no tratarla como porcentaje sin calibración.
- Documentar el cambio de sensor de luz y su orientación: el nuevo sensor aumenta su lectura cuando está más oscuro. Registrar la versión del sensor y verificar qué transformación se utilizó en entrenamiento.
- Calcular `temp_promedio` de la misma manera que en la tarea 2.
- Derivar `periodo` con la misma definición usada en entrenamiento; no asumir su significado.
- No enviar `fecha_hora`, `registro` ni la etiqueta objetivo como variables de entrada si fueron excluidos del modelo.
- Definir qué hacer ante faltantes según el preprocesamiento entrenado.

Ejemplo: para contestar «¿Cómo estuve esta semana?», el servicio de recuperación consulta un intervalo histórico, no solamente la última fila.
