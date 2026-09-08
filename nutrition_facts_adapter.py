"""Normalize nutrition_facts database rows for deterministic smoothie math.

This module performs database-row adaptation only.

It does NOT:
- open database connections;
- search for ingredients;
- perform aliases or fuzzy matching;
- apply serving-size scaling;
- calculate recipe quantities;
- convert liquid volume to mass;
- calculate batch nutrition;
- make nutrition recommendations.

The returned nutrition values represent the existing PureFyul per-100g
nutrition contract.

Current nutrient units:
- calories: kcal per 100g
- protein: g per 100g
- carbs: g per 100g
- fat: g per 100g
- fiber: g per 100g
- sugar: g per 100g
- sodium: mg per 100g

Production PostgreSQL currently names its sodium column ``sodium_g``, but
PureFyul's existing application contract treats the stored value as milligrams.
"""

from __future__ import annotations

from decimal import Decimal
import math

from batch_nutrition import NUTRIENT_KEYS


class NutritionFactsAdapterError(ValueError):
    """Raised when a nutrition_facts row cannot satisfy the strict contract."""


_COLUMN_MAPS = {
    "postgres": {
        "calories": "calories",
        "protein": "protein_g",
        "carbs": "carbs_g",
        "fat": "fat_g",
        "fiber": "fiber_g",
        "sugar": "sugar_g",
        "sodium": "sodium_g",
    },
    "sqlite": {
        "calories": "calories_per_100g",
        "protein": "protein",
        "carbs": "carbs",
        "fat": "fat",
        "fiber": "fiber",
        "sugar": "sugar",
        "sodium": "sodium",
    },
}


def _get_required_row_value(row, column: str):
    try:
        keys = row.keys()
    except Exception as exc:
        raise NutritionFactsAdapterError(
            "nutrition row must provide keyed values"
        ) from exc

    if column not in keys:
        raise NutritionFactsAdapterError(
            f"nutrition row is missing required column '{column}'"
        )

    return row[column]


def _normalize_nutrient_value(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, Decimal),
    ):
        raise NutritionFactsAdapterError(
            f"{field_name} must be numeric"
        )

    number = float(value)

    if not math.isfinite(number):
        raise NutritionFactsAdapterError(
            f"{field_name} must be finite"
        )

    if number < 0:
        raise NutritionFactsAdapterError(
            f"{field_name} cannot be negative"
        )

    return number


def adapt_nutrition_facts_row(
    row,
    *,
    backend: str,
) -> dict:
    """Return one nutrition_facts row in the pure per-100g contract.

    ``backend`` must be ``postgres`` or ``sqlite``.

    ``serving_size_g`` / ``serving_size`` is deliberately ignored because
    the stored nutrient values are per-100g values. Serving metadata must not
    change the deterministic per-100g contract.

    Ingredient identity is preserved from the database row. This function
    does not perform canonicalization, aliases, or fuzzy matching.
    """

    if backend not in _COLUMN_MAPS:
        raise NutritionFactsAdapterError(
            "backend must be 'postgres' or 'sqlite'"
        )

    ingredient = _get_required_row_value(row, "ingredient")

    if not isinstance(ingredient, str) or not ingredient.strip():
        raise NutritionFactsAdapterError(
            "ingredient must be a non-empty string"
        )

    column_map = _COLUMN_MAPS[backend]

    nutrition_per_100g = {}

    for nutrient in NUTRIENT_KEYS:
        source_column = column_map[nutrient]

        value = _get_required_row_value(
            row,
            source_column,
        )

        nutrition_per_100g[nutrient] = _normalize_nutrient_value(
            value,
            source_column,
        )

    return {
        "ingredient": ingredient.strip(),
        "nutrition_per_100g": nutrition_per_100g,
    }
