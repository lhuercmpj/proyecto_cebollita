# Datos

## Qué va aquí

Archivos fuente que alimentarán el historial y el RAG del asistente.

- `sensors/`: dataset histórico de la Tarea 2, con sus campos y unidades documentados.
- `references/`: documentos científicos sobre fitonias y el cuidado de la especie.

Las nuevas mediciones de la ESP32 no se guardan como archivos en esta carpeta:
el backend las persiste en PostgreSQL. Si más adelante se exporta ese historial
para análisis, la exportación sí puede almacenarse en `sensors/` con su fecha y
procedencia.

## Criterios

Conservar los originales y distinguirlos de los datos procesados. Documentar
procedencia, fecha, campos, unidades y transformaciones. Los índices generados
por RAG son derivados reproducibles y no son fuentes: se definirá su ubicación
y exclusión de Git cuando se implemente la indexación.

Nunca guardar credenciales en esta carpeta. El sistema necesita recuperar los datos tras un reinicio; no depender del estado del navegador.
