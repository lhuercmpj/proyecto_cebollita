from math import exp

from app.schemas.measurement import Prediction
from app.services.model_data import (
    BIAS1,
    BIAS2,
    CLASS_NAMES,
    ESC_MIN,
    ESC_SCALE,
    MODEL_VERSION,
    W1,
    W2,
)


def predict(
    humedad_tierra: float,
    luz: float,
    humedad_aire: float,
    temp_promedio: float,
) -> Prediction:
    """Replica la red 4-16-4 exportada en el encabezado de la ESP32."""

    raw_inputs = (humedad_tierra, luz, humedad_aire, temp_promedio)
    scaled = tuple(
        value * scale + minimum
        for value, scale, minimum in zip(raw_inputs, ESC_SCALE, ESC_MIN, strict=True)
    )

    hidden = tuple(
        max(
            0.0,
            BIAS1[hidden_index]
            + sum(
                scaled[input_index] * W1[input_index][hidden_index]
                for input_index in range(len(scaled))
            ),
        )
        for hidden_index in range(len(BIAS1))
    )

    logits = tuple(
        BIAS2[class_index]
        + sum(
            hidden[hidden_index] * W2[hidden_index][class_index]
            for hidden_index in range(len(hidden))
        )
        for class_index in range(len(BIAS2))
    )
    max_logit = max(logits)
    exponentials = tuple(exp(logit - max_logit) for logit in logits)
    total = sum(exponentials)
    probability_values = tuple(value / total for value in exponentials)

    class_index = max(range(len(probability_values)), key=probability_values.__getitem__)
    state = CLASS_NAMES[class_index]
    probabilities = dict(zip(CLASS_NAMES, probability_values, strict=True))

    return Prediction(
        class_index=class_index,
        state=state,
        confidence=probability_values[class_index],
        probabilities=probabilities,
        model_version=MODEL_VERSION,
    )

