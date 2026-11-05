# Modelo predictivo

## Qué va aquí

El modelo seleccionado en la tarea 2 y todos los elementos necesarios para reproducir su predicción.

## Elementos a incorporar

- Archivo del modelo entrenado, por ejemplo `.joblib` o el formato realmente usado.
- Pipeline o transformadores de preprocesamiento.
- Lista y orden exacto de variables de entrada.
- Correspondencia entre clases numéricas y nombres de estados.
- Versiones de las bibliotecas utilizadas.
- Métricas de evaluación y fecha o versión del entrenamiento.

## Uso

`prediction_service.py` carga el modelo y aplica las mismas transformaciones del entrenamiento a cada lectura válida. Si se usa Random Forest, respetar su preparación; si se usa Softmax con escalado, reutilizar el escalador ajustado, sin volver a ajustarlo en cada petición.

## Ejemplo

Una lectura nueva produce un estado estimado. Ese resultado se guarda asociado a la medición y se reutiliza en el chat, el reporte de los 30 minutos y la evaluación de alertas de riego.

No asumir que `Bien` y `Estoy bien` son clases equivalentes sin revisar las etiquetas reales. Si no se puede predecir, reportar la falta de estimación.

Cargar únicamente artefactos confiables, especialmente si se usa pickle o joblib.
