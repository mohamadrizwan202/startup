import pytest

from smoothie_tuner import (
    SmoothieTuningInfeasibleError,
    SmoothieTuningInputError,
    tune_calculated_recipe,
)


def _recipe():
    return {
        "ingredients": [
            {
                "ingredient": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "weight_g": 100.0,
                "nutrition_per_100g": {
                    "calories": 100.0,
                    "protein": 10.0,
                    "carbs": 5.0,
                    "fat": 2.0,
                    "fiber": 0.0,
                    "sugar": 4.0,
                    "sodium": 50.0,
                },
            },
            {
                "ingredient": "Apple",
                "nutrition_lookup_name": "apple",
                "weight_g": 100.0,
                "nutrition_per_100g": {
                    "calories": 50.0,
                    "protein": 0.0,
                    "carbs": 14.0,
                    "fat": 0.0,
                    "fiber": 2.0,
                    "sugar": 10.0,
                    "sodium": 1.0,
                },
            },
        ]
    }


BOUNDS = [
    {
        "min_weight_g": 50.0,
        "max_weight_g": 250.0,
    },
    {
        "min_weight_g": 20.0,
        "max_weight_g": 150.0,
    },
]


def test_tuner_finds_feasible_exact_target_recipe():
    result = tune_calculated_recipe(
        recipe_result=_recipe(),
        ingredient_bounds=BOUNDS,
        minimums={
            "protein": 20.0,
        },
        maximums={
            "sugar": 12.0,
        },
    )

    assert result["after"]["nutrition"]["protein"] >= (
        20.0 - 1e-7
    )
    assert result["after"]["nutrition"]["sugar"] <= (
        12.0 + 1e-7
    )

    yogurt = result["ingredients"][0]
    apple = result["ingredients"][1]

    assert yogurt["after_weight_g"] == pytest.approx(200.0)
    assert apple["after_weight_g"] == pytest.approx(40.0)

    assert yogurt["before_weight_g"] == 100.0
    assert apple["before_weight_g"] == 100.0


def test_tuner_leaves_recipe_unchanged_when_targets_already_met():
    result = tune_calculated_recipe(
        recipe_result=_recipe(),
        ingredient_bounds=BOUNDS,
        minimums={
            "protein": 5.0,
        },
        maximums={
            "sugar": 20.0,
        },
    )

    assert result["ingredients"][0]["after_weight_g"] == pytest.approx(
        100.0
    )
    assert result["ingredients"][1]["after_weight_g"] == pytest.approx(
        100.0
    )


def test_tuner_fails_when_targets_are_impossible():
    with pytest.raises(
        SmoothieTuningInfeasibleError,
        match="no recipe",
    ):
        tune_calculated_recipe(
            recipe_result=_recipe(),
            ingredient_bounds=BOUNDS,
            minimums={
                "protein": 30.0,
            },
        )


def test_tuner_requires_explicit_bounds_for_every_ingredient():
    with pytest.raises(
        SmoothieTuningInputError,
        match="one entry per ingredient",
    ):
        tune_calculated_recipe(
            recipe_result=_recipe(),
            ingredient_bounds=[BOUNDS[0]],
            minimums={
                "protein": 20.0,
            },
        )


def test_tuner_rejects_bounds_that_exclude_original_recipe():
    with pytest.raises(
        SmoothieTuningInputError,
        match="must include the original ingredient weight",
    ):
        tune_calculated_recipe(
            recipe_result=_recipe(),
            ingredient_bounds=[
                {
                    "min_weight_g": 110.0,
                    "max_weight_g": 250.0,
                },
                BOUNDS[1],
            ],
            minimums={
                "protein": 20.0,
            },
        )


def test_tuner_rejects_conflicting_targets():
    with pytest.raises(
        SmoothieTuningInputError,
        match="cannot exceed",
    ):
        tune_calculated_recipe(
            recipe_result=_recipe(),
            ingredient_bounds=BOUNDS,
            minimums={
                "sugar": 15.0,
            },
            maximums={
                "sugar": 10.0,
            },
        )


def test_tuner_supports_existing_seven_nutrient_contract():
    result = tune_calculated_recipe(
        recipe_result=_recipe(),
        ingredient_bounds=BOUNDS,
        maximums={
            "sodium": 60.0,
            "carbs": 20.0,
            "fat": 5.0,
            "calories": 200.0,
        },
    )

    nutrition = result["after"]["nutrition"]

    assert nutrition["sodium"] <= 60.0 + 1e-7
    assert nutrition["carbs"] <= 20.0 + 1e-7
    assert nutrition["fat"] <= 5.0 + 1e-7
    assert nutrition["calories"] <= 200.0 + 1e-7
