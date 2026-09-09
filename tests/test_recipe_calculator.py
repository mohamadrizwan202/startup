import pytest

import recipe_calculator
from batch_nutrition import BatchNutritionInputError
from recipe_calculator import (
    RecipeCalculationError,
    calculate_recipe,
)
from recipe_mass import RecipeMassResolutionError


BANANA_NUTRITION = {
    "ingredient": "banana",
    "nutrition_per_100g": {
        "calories": 89.0,
        "protein": 1.1,
        "carbs": 23.0,
        "fat": 0.3,
        "fiber": 2.6,
        "sugar": 12.0,
        "sodium": 1.0,
    },
}

SPINACH_NUTRITION = {
    "ingredient": "spinach",
    "nutrition_per_100g": {
        "calories": 23.0,
        "protein": 2.9,
        "carbs": 3.6,
        "fat": 0.4,
        "fiber": 2.2,
        "sugar": 0.4,
        "sodium": 79.0,
    },
}


def _fake_lookup(name):
    records = {
        "banana": BANANA_NUTRITION,
        "spinach": SPINACH_NUTRITION,
    }
    return records.get(name.strip().lower())


def test_calculate_recipe_connects_mass_lookup_and_batch_math(monkeypatch):
    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        _fake_lookup,
    )

    result = calculate_recipe(
        [
            {
                "ingredient": "Banana",
                "nutrition_lookup_name": "banana",
                "amount": 100,
                "unit": "g",
            },
            {
                "ingredient": "Spinach",
                "nutrition_lookup_name": "spinach",
                "amount": 50,
                "unit": "g",
            },
        ]
    )

    assert result["batch"]["weight_g"] == pytest.approx(150.0)

    assert result["batch"]["nutrition"]["calories"] == pytest.approx(
        100.5
    )
    assert result["batch"]["nutrition"]["protein"] == pytest.approx(
        2.55
    )
    assert result["batch"]["nutrition"]["fiber"] == pytest.approx(
        3.7
    )
    assert result["batch"]["nutrition"]["sugar"] == pytest.approx(
        12.2
    )

    assert result["batch"]["energy_density_kcal_per_g"] == pytest.approx(
        100.5 / 150.0
    )

    assert result["ingredients"][0]["weight_g"] == pytest.approx(100.0)
    assert result["ingredients"][0]["mass_source"] == "gram_input"
    assert result["ingredients"][0]["nutrition"]["protein"] == pytest.approx(
        1.1
    )

    assert result["ingredients"][1]["weight_g"] == pytest.approx(50.0)
    assert result["ingredients"][1]["nutrition"]["protein"] == pytest.approx(
        1.45
    )

    assert result["portion"] is None


def test_calculate_recipe_can_scale_to_supplied_portion(monkeypatch):
    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        _fake_lookup,
    )

    result = calculate_recipe(
        [
            {
                "ingredient": "Banana",
                "nutrition_lookup_name": "banana",
                "amount": 100,
                "unit": "g",
            },
            {
                "ingredient": "Spinach",
                "nutrition_lookup_name": "spinach",
                "amount": 100,
                "unit": "g",
            },
        ],
        portion_g=100,
    )

    assert result["batch"]["weight_g"] == pytest.approx(200.0)
    assert result["portion"]["weight_g"] == 100
    assert result["portion"]["nutrition"]["calories"] == pytest.approx(
        result["batch"]["nutrition"]["calories"] / 2
    )
    assert result["portion"]["nutrition"]["protein"] == pytest.approx(
        result["batch"]["nutrition"]["protein"] / 2
    )


def test_missing_exact_nutrition_fails_entire_recipe(monkeypatch):
    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        lambda _name: None,
    )

    with pytest.raises(
        RecipeCalculationError,
        match="exact nutrition facts not found",
    ):
        calculate_recipe(
            [
                {
                    "ingredient": "Unknown",
                    "nutrition_lookup_name": "unknown",
                    "amount": 100,
                    "unit": "g",
                }
            ]
        )


def test_unresolved_ml_mass_fails_before_nutrition_lookup(monkeypatch):
    lookup_called = False

    def fake_lookup(_name):
        nonlocal lookup_called
        lookup_called = True
        return BANANA_NUTRITION

    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        fake_lookup,
    )

    with pytest.raises(
        RecipeMassResolutionError,
        match="mass conversion is unresolved",
    ):
        calculate_recipe(
            [
                {
                    "ingredient": "Coconut Milk",
                    "nutrition_lookup_name": "coconut milk",
                    "amount": 150,
                    "unit": "ml",
                }
            ]
        )

    assert lookup_called is False


def test_portion_larger_than_batch_is_rejected(monkeypatch):
    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        _fake_lookup,
    )

    with pytest.raises(BatchNutritionInputError):
        calculate_recipe(
            [
                {
                    "ingredient": "Banana",
                    "nutrition_lookup_name": "banana",
                    "amount": 100,
                    "unit": "g",
                }
            ],
            portion_g=101,
        )
