from copy import deepcopy
from decimal import Decimal

import pytest

from batch_nutrition import (
    NUTRIENT_KEYS,
    calculate_ingredient_nutrition,
)
from nutrition_facts_adapter import (
    NutritionFactsAdapterError,
    adapt_nutrition_facts_row,
)


POSTGRES_BANANA = {
    "ingredient": "banana",
    "calories": Decimal("89"),
    "protein_g": Decimal("1.1"),
    "carbs_g": Decimal("23"),
    "fat_g": Decimal("0.3"),
    "fiber_g": Decimal("2.6"),
    "sugar_g": Decimal("12"),
    "sodium_g": Decimal("1"),
    "serving_size_g": Decimal("118"),
    "vitamins": "C, B6",
    "minerals": "Potassium, Manganese",
}


SQLITE_BANANA = {
    "ingredient": "banana",
    "calories_per_100g": 89,
    "protein": 1.1,
    "carbs": 23,
    "fat": 0.3,
    "fiber": 2.6,
    "sugar": 12,
    "sodium": 1,
    "serving_size": 118,
}


def test_postgres_row_maps_to_strict_per_100g_contract():
    result = adapt_nutrition_facts_row(
        POSTGRES_BANANA,
        backend="postgres",
    )

    assert result == {
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


def test_sqlite_row_maps_to_same_per_100g_contract():
    postgres = adapt_nutrition_facts_row(
        POSTGRES_BANANA,
        backend="postgres",
    )

    sqlite = adapt_nutrition_facts_row(
        SQLITE_BANANA,
        backend="sqlite",
    )

    assert sqlite == postgres


def test_output_nutrients_match_batch_math_contract_exactly():
    result = adapt_nutrition_facts_row(
        POSTGRES_BANANA,
        backend="postgres",
    )

    assert tuple(result["nutrition_per_100g"].keys()) == NUTRIENT_KEYS


def test_postgres_decimal_values_are_normalized_to_floats():
    result = adapt_nutrition_facts_row(
        POSTGRES_BANANA,
        backend="postgres",
    )

    assert all(
        isinstance(value, float)
        for value in result["nutrition_per_100g"].values()
    )


def test_serving_size_is_metadata_and_does_not_scale_per_100g_values():
    row = dict(POSTGRES_BANANA)
    row["serving_size_g"] = Decimal("999")

    result = adapt_nutrition_facts_row(
        row,
        backend="postgres",
    )

    assert result["nutrition_per_100g"]["calories"] == 89.0
    assert "serving_size_g" not in result
    assert "serving_size" not in result


def test_sodium_value_is_preserved_in_existing_mg_contract():
    row = dict(POSTGRES_BANANA)
    row["ingredient"] = "spinach"
    row["sodium_g"] = Decimal("79")

    result = adapt_nutrition_facts_row(
        row,
        backend="postgres",
    )

    assert result["nutrition_per_100g"]["sodium"] == 79.0


def test_adapter_output_can_feed_pure_ingredient_math():
    adapted = adapt_nutrition_facts_row(
        POSTGRES_BANANA,
        backend="postgres",
    )

    nutrition = calculate_ingredient_nutrition(
        weight_g=118.0,
        nutrition_per_100g=adapted["nutrition_per_100g"],
    )

    assert nutrition["calories"] == pytest.approx(105.02)
    assert nutrition["protein"] == pytest.approx(1.298)


def test_adapter_does_not_mutate_database_row():
    row = deepcopy(POSTGRES_BANANA)
    before = deepcopy(row)

    adapt_nutrition_facts_row(
        row,
        backend="postgres",
    )

    assert row == before


@pytest.mark.parametrize(
    "backend",
    [
        None,
        "",
        "mysql",
        "POSTGRES",
    ],
)
def test_unknown_backend_is_rejected(backend):
    with pytest.raises(NutritionFactsAdapterError):
        adapt_nutrition_facts_row(
            POSTGRES_BANANA,
            backend=backend,
        )


def test_blank_ingredient_is_rejected():
    row = dict(POSTGRES_BANANA)
    row["ingredient"] = "   "

    with pytest.raises(NutritionFactsAdapterError):
        adapt_nutrition_facts_row(
            row,
            backend="postgres",
        )


@pytest.mark.parametrize(
    "column",
    [
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "sugar_g",
        "sodium_g",
    ],
)
def test_missing_postgres_nutrient_columns_are_rejected(column):
    row = dict(POSTGRES_BANANA)
    del row[column]

    with pytest.raises(NutritionFactsAdapterError):
        adapt_nutrition_facts_row(
            row,
            backend="postgres",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        "89",
        -1,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_nutrient_values_are_rejected(value):
    row = dict(POSTGRES_BANANA)
    row["calories"] = value

    with pytest.raises(NutritionFactsAdapterError):
        adapt_nutrition_facts_row(
            row,
            backend="postgres",
        )


def test_extra_database_fields_do_not_expand_result_contract():
    row = dict(POSTGRES_BANANA)
    row["potassium"] = Decimal("358")
    row["random_future_column"] = "ignored"

    result = adapt_nutrition_facts_row(
        row,
        backend="postgres",
    )

    assert set(result) == {
        "ingredient",
        "nutrition_per_100g",
    }

    assert "potassium" not in result["nutrition_per_100g"]
