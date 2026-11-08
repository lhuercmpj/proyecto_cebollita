import pytest

from app.services.model_data import CLASS_NAMES, TEST_P, TEST_X, TEST_Y
from app.services.prediction_service import predict


@pytest.mark.parametrize(
    ("inputs", "expected_class", "expected_probabilities"),
    tuple(zip(TEST_X, TEST_Y, TEST_P, strict=True)),
)
def test_matches_exported_sklearn_vectors(
    inputs: tuple[float, float, float, float],
    expected_class: int,
    expected_probabilities: tuple[float, float, float, float],
) -> None:
    result = predict(*inputs)

    assert result.class_index == expected_class
    assert result.state == CLASS_NAMES[expected_class]
    actual_probabilities = tuple(result.probabilities[name] for name in CLASS_NAMES)
    assert actual_probabilities == pytest.approx(expected_probabilities, abs=2e-6)


def test_probabilities_sum_to_one() -> None:
    result = predict(*TEST_X[0])

    assert sum(result.probabilities.values()) == pytest.approx(1.0)
    assert result.confidence == max(result.probabilities.values())

