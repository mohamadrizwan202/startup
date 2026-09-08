import pytest

import starter_recipe
from starter_recipe import (
    StarterRecipeInputError,
    StarterRecipeUnavailableError,
    build_starter_recipe,
    get_mobile_starter_definition,
)


def _fake_calculated_recipe(inputs):
    ingredients = []

    for item in inputs:
        ingredients.append(
            {
                "ingredient": item["ingredient"],
                "nutrition_lookup_name": item["nutrition_lookup_name"],
                "nutrition_record_name": item["nutrition_lookup_name"],
                "weight_g": float(item["amount"]),
                "mass_source": "gram_input",
                "nutrition": {
                    "calories": 1.0,
                    "protein": 1.0,
                    "carbs": 1.0,
                    "fat": 1.0,
                    "fiber": 1.0,
                    "sugar": 1.0,
                    "sodium": 1.0,
                },
            }
        )

    return {
        "ingredients": ingredients,
        "batch": {
            "weight_g": sum(float(item["amount"]) for item in inputs),
            "nutrition": {
                "calories": 4.0,
                "protein": 4.0,
                "carbs": 4.0,
                "fat": 4.0,
                "fiber": 4.0,
                "sugar": 4.0,
                "sodium": 4.0,
            },
            "energy_density_kcal_per_g": 0.01,
        },
        "portion": None,
    }


def test_mobile_catalog_bridge_uses_explicit_product_starters(monkeypatch):
    captured = {}

    def fake_calculate_recipe(inputs):
        captured["inputs"] = inputs
        return _fake_calculated_recipe(inputs)

    monkeypatch.setattr(
        starter_recipe.recipe_calculator,
        "calculate_recipe",
        fake_calculate_recipe,
    )

    result = build_starter_recipe(
        [
            "blueberries",
            "mango",
            "chia-seeds",
            "greek-yogurt",
        ]
    )

    assert captured["inputs"] == [
        {
            "ingredient": "Blueberries",
            "nutrition_lookup_name": "blueberries",
            "amount": 100.0,
            "unit": "g",
        },
        {
            "ingredient": "Mango",
            "nutrition_lookup_name": "mango",
            "amount": 100.0,
            "unit": "g",
        },
        {
            "ingredient": "Chia Seeds",
            "nutrition_lookup_name": "chia seed",
            "amount": 12.0,
            "unit": "g",
        },
        {
            "ingredient": "Greek Yogurt",
            "nutrition_lookup_name": "greek yogurt",
            "amount": 170.0,
            "unit": "g",
        },
    ]

    assert [item["id"] for item in result["ingredients"]] == [
        "blueberries",
        "mango",
        "chia-seeds",
        "greek-yogurt",
    ]
    assert result["starter_amount_contract"] == {
        "personalized": False,
        "dietary_recommendation": False,
    }
    assert result["portion"] is None


def test_blueberries_use_explicit_smoothie_nutrition_lookup():
    definition = get_mobile_starter_definition("blueberries")

    assert definition["nutrition_lookup_name"] == "blueberries"
    assert definition["amount"] == 100.0
    assert definition["unit"] == "g"


def test_spinach_uses_usda_household_measure_starter(monkeypatch):
    captured = {}

    def fake_calculate_recipe(inputs):
        captured["inputs"] = inputs
        return _fake_calculated_recipe(inputs)

    monkeypatch.setattr(
        starter_recipe.recipe_calculator,
        "calculate_recipe",
        fake_calculate_recipe,
    )

    result = build_starter_recipe(["spinach"])

    assert captured["inputs"] == [
        {
            "ingredient": "Spinach",
            "nutrition_lookup_name": "spinach",
            "amount": 30.0,
            "unit": "g",
        }
    ]
    assert result["ingredients"][0]["id"] == "spinach"

    definition = get_mobile_starter_definition("spinach")
    assert definition["amount"] == 30.0
    assert definition["unit"] == "g"
    assert definition["starter_source"] == (
        "usda_household_measure_1_cup_raw"
    )
    assert definition["available"] is True


def test_oat_milk_fails_before_any_one_ml_equals_one_g_assumption(
    monkeypatch,
):
    calculator_called = False

    def fake_calculate_recipe(_inputs):
        nonlocal calculator_called
        calculator_called = True
        raise AssertionError("calculator must not be called")

    monkeypatch.setattr(
        starter_recipe.recipe_calculator,
        "calculate_recipe",
        fake_calculate_recipe,
    )

    with pytest.raises(StarterRecipeUnavailableError) as exc_info:
        build_starter_recipe(["oat-milk"])

    assert exc_info.value.reason == "mass_unresolved"
    assert exc_info.value.ingredient_id == "oat-milk"
    assert calculator_called is False


@pytest.mark.parametrize(
    "value",
    [
        None,
        "mango",
        {},
    ],
)
def test_selected_ids_must_be_a_collection(value):
    with pytest.raises(
        StarterRecipeInputError,
        match="must be a list or tuple",
    ):
        build_starter_recipe(value)


def test_selected_ids_cannot_be_empty():
    with pytest.raises(
        StarterRecipeInputError,
        match="cannot be empty",
    ):
        build_starter_recipe([])


def test_duplicate_ids_are_rejected():
    with pytest.raises(
        StarterRecipeInputError,
        match="duplicate ingredient id",
    ):
        build_starter_recipe(["mango", "mango"])


def test_unknown_mobile_id_is_rejected():
    with pytest.raises(
        StarterRecipeInputError,
        match="unsupported mobile ingredient id",
    ):
        build_starter_recipe(["banana"])
