import pytest

from batch_nutrition import (
    NUTRIENT_KEYS,
    BatchNutritionInputError,
    calculate_batch_nutrition,
    calculate_energy_density,
    calculate_ingredient_nutrition,
    scale_batch_nutrition_to_portion,
)


BASE_NUTRITION = {
    "calories": 120.0,
    "protein": 6.0,
    "carbs": 20.0,
    "fat": 2.0,
    "fiber": 4.0,
    "sugar": 8.0,
    "sodium": 30.0,
}


def _nutrition(**overrides):
    result = dict(BASE_NUTRITION)
    result.update(overrides)
    return result


def test_ingredient_nutrition_scales_per_100g_values_by_weight():
    result = calculate_ingredient_nutrition(
        weight_g=50.0,
        nutrition_per_100g=BASE_NUTRITION,
    )

    assert result == {
        "calories": pytest.approx(60.0),
        "protein": pytest.approx(3.0),
        "carbs": pytest.approx(10.0),
        "fat": pytest.approx(1.0),
        "fiber": pytest.approx(2.0),
        "sugar": pytest.approx(4.0),
        "sodium": pytest.approx(15.0),
    }


def test_zero_is_valid_when_explicitly_supplied_as_nutrient_value():
    result = calculate_ingredient_nutrition(
        weight_g=100.0,
        nutrition_per_100g=_nutrition(sugar=0.0),
    )

    assert result["sugar"] == 0.0


def test_output_contract_is_limited_to_current_seven_nutrients():
    nutrition = _nutrition()
    nutrition["potassium"] = 500.0

    result = calculate_ingredient_nutrition(
        weight_g=100.0,
        nutrition_per_100g=nutrition,
    )

    assert tuple(result.keys()) == NUTRIENT_KEYS
    assert "potassium" not in result


def test_batch_nutrition_sums_weight_and_all_supported_nutrients():
    result = calculate_batch_nutrition(
        [
            {
                "weight_g": 100.0,
                "nutrition_per_100g": BASE_NUTRITION,
            },
            {
                "weight_g": 50.0,
                "nutrition_per_100g": {
                    "calories": 200.0,
                    "protein": 10.0,
                    "carbs": 30.0,
                    "fat": 4.0,
                    "fiber": 2.0,
                    "sugar": 12.0,
                    "sodium": 50.0,
                },
            },
        ]
    )

    assert result["batch_weight_g"] == pytest.approx(150.0)
    assert result["nutrition"] == {
        "calories": pytest.approx(220.0),
        "protein": pytest.approx(11.0),
        "carbs": pytest.approx(35.0),
        "fat": pytest.approx(4.0),
        "fiber": pytest.approx(5.0),
        "sugar": pytest.approx(14.0),
        "sodium": pytest.approx(55.0),
    }


def test_energy_density_uses_actual_batch_calories_and_gram_mass():
    density = calculate_energy_density(
        batch_calories=220.0,
        batch_weight_g=150.0,
    )

    assert density == pytest.approx(220.0 / 150.0)


def test_portion_scaling_uses_same_ratio_for_all_nutrients():
    result = scale_batch_nutrition_to_portion(
        batch_nutrition={
            "calories": 220.0,
            "protein": 11.0,
            "carbs": 35.0,
            "fat": 4.0,
            "fiber": 5.0,
            "sugar": 14.0,
            "sodium": 55.0,
        },
        batch_weight_g=150.0,
        portion_g=60.0,
    )

    assert result == {
        "calories": pytest.approx(88.0),
        "protein": pytest.approx(4.4),
        "carbs": pytest.approx(14.0),
        "fat": pytest.approx(1.6),
        "fiber": pytest.approx(2.0),
        "sugar": pytest.approx(5.6),
        "sodium": pytest.approx(22.0),
    }


def test_full_batch_portion_preserves_full_batch_nutrition():
    result = scale_batch_nutrition_to_portion(
        batch_nutrition=BASE_NUTRITION,
        batch_weight_g=620.0,
        portion_g=620.0,
    )

    assert result == pytest.approx(BASE_NUTRITION)


def test_calculation_layer_does_not_apply_presentation_rounding():
    result = calculate_ingredient_nutrition(
        weight_g=33.3,
        nutrition_per_100g=_nutrition(calories=123.456),
    )

    assert result["calories"] == pytest.approx(41.110848)


@pytest.mark.parametrize(
    "weight_g",
    [
        None,
        0,
        -1,
        True,
        "100",
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_ingredient_weights_are_rejected(weight_g):
    with pytest.raises(BatchNutritionInputError):
        calculate_ingredient_nutrition(
            weight_g=weight_g,
            nutrition_per_100g=BASE_NUTRITION,
        )


@pytest.mark.parametrize("nutrient", NUTRIENT_KEYS)
def test_missing_required_nutrients_are_rejected(nutrient):
    nutrition = dict(BASE_NUTRITION)
    del nutrition[nutrient]

    with pytest.raises(BatchNutritionInputError):
        calculate_ingredient_nutrition(
            weight_g=100.0,
            nutrition_per_100g=nutrition,
        )


@pytest.mark.parametrize("nutrient", NUTRIENT_KEYS)
def test_none_required_nutrient_values_are_rejected(nutrient):
    nutrition = dict(BASE_NUTRITION)
    nutrition[nutrient] = None

    with pytest.raises(BatchNutritionInputError):
        calculate_ingredient_nutrition(
            weight_g=100.0,
            nutrition_per_100g=nutrition,
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        "12",
        -0.1,
        float("nan"),
        float("inf"),
    ],
)
def test_malformed_nutrient_values_are_rejected(value):
    with pytest.raises(BatchNutritionInputError):
        calculate_ingredient_nutrition(
            weight_g=100.0,
            nutrition_per_100g=_nutrition(calories=value),
        )


def test_empty_batch_is_rejected():
    with pytest.raises(BatchNutritionInputError):
        calculate_batch_nutrition([])


def test_batch_item_missing_weight_is_rejected():
    with pytest.raises(BatchNutritionInputError):
        calculate_batch_nutrition(
            [
                {
                    "nutrition_per_100g": BASE_NUTRITION,
                }
            ]
        )


def test_batch_item_missing_nutrition_is_rejected():
    with pytest.raises(BatchNutritionInputError):
        calculate_batch_nutrition(
            [
                {
                    "weight_g": 100.0,
                }
            ]
        )


@pytest.mark.parametrize(
    "batch_weight_g",
    [
        None,
        0,
        -1,
        True,
        "620",
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_energy_density_batch_weights_are_rejected(
    batch_weight_g,
):
    with pytest.raises(BatchNutritionInputError):
        calculate_energy_density(
            batch_calories=500.0,
            batch_weight_g=batch_weight_g,
        )


@pytest.mark.parametrize(
    "batch_calories",
    [
        None,
        -1,
        True,
        "500",
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_batch_calories_are_rejected(batch_calories):
    with pytest.raises(BatchNutritionInputError):
        calculate_energy_density(
            batch_calories=batch_calories,
            batch_weight_g=500.0,
        )


def test_zero_calorie_batch_has_zero_energy_density():
    density = calculate_energy_density(
        batch_calories=0.0,
        batch_weight_g=500.0,
    )

    assert density == 0.0


@pytest.mark.parametrize(
    "portion_g",
    [
        None,
        0,
        -1,
        True,
        "300",
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_portions_are_rejected(portion_g):
    with pytest.raises(BatchNutritionInputError):
        scale_batch_nutrition_to_portion(
            batch_nutrition=BASE_NUTRITION,
            batch_weight_g=620.0,
            portion_g=portion_g,
        )


def test_portion_larger_than_batch_is_rejected_not_clamped():
    with pytest.raises(
        BatchNutritionInputError,
        match="cannot exceed",
    ):
        scale_batch_nutrition_to_portion(
            batch_nutrition=BASE_NUTRITION,
            batch_weight_g=620.0,
            portion_g=621.0,
        )


def test_zero_batch_weight_is_rejected_for_portion_scaling():
    with pytest.raises(BatchNutritionInputError):
        scale_batch_nutrition_to_portion(
            batch_nutrition=BASE_NUTRITION,
            batch_weight_g=0.0,
            portion_g=100.0,
        )
