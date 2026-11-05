# Datos

## Qué va aquí

Datos de sensores y documentos científicos que alimentarán las respuestas del asistente.

- `sensors/`: dataset histórico de la tarea 2 y nuevas mediciones.
- `references/`: fuentes científicas sobre la especie.

## Criterios

Conservar los originales y distinguirlos de los datos procesados. Documentar procedencia, fecha, campos, unidades y transformaciones. Los índices generados de RAG son derivados reproducibles: decidir su ubicación y exclusión de Git al implementarlos.

Nunca guardar credenciales en esta carpeta. El sistema necesita recuperar los datos tras un reinicio; no depender del estado del navegador.
