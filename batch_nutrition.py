"""Pure deterministic gram-based batch nutrition calculations for PureFyul.

No database, Flask, network, AI, EER, recommendation, or unit-conversion
dependencies.

This module accepts normalized gram masses and provided per-100g nutrition.
It performs deterministic arithmetic only.

It does NOT establish that:
- recipe gram amounts are canonical or scientifically recommended;
- upstream nutrition records are verified or authoritative;
- liquid volumes have been correctly converted to gram mass.

Those are adapter/integration responsibilities outside this pure math layer.
"""

from __future__ import annotations

import math


NUTRIENT_KEYS = (
    "calories",
    "protein",
    "carbs",
    "fat",
    "fiber",
    "sugar",
    "sodium",
)


class BatchNutritionInputError(ValueError):
    """Raised when batch-nutrition inputs are outside the supported contract."""


def _require_finite_number(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BatchNutritionInputError(f"{field_name} must be numeric")

    number = float(value)

    if not math.isfinite(number):
        raise BatchNutritionInputError(f"{field_name} must be finite")

    return number


def _require_positive_number(value, field_name: str) -> float:
    number = _require_finite_number(value, field_name)

    if number <= 0:
        raise BatchNutritionInputError(
            f"{field_name} must be greater than zero"
        )

    return number


def _require_nonnegative_number(value, field_name: str) -> float:
    number = _require_finite_number(value, field_name)

    if number < 0:
        raise BatchNutritionInputError(
            f"{field_name} cannot be negative"
        )

    return number


def _normalize_nutrition(
    nutrition,
    field_name: str,
) -> dict[str, float]:
    if not isinstance(nutrition, dict):
        raise BatchNutritionInputError(
            f"{field_name} must be a dictionary"
        )

    normalized = {}

    for nutrient in NUTRIENT_KEYS:
        if nutrient not in nutrition:
            raise BatchNutritionInputError(
                f"{field_name}.{nutrient} is required"
            )

        normalized[nutrient] = _require_nonnegative_number(
            nutrition[nutrient],
            f"{field_name}.{nutrient}",
        )

    return normalized


def calculate_ingredient_nutrition(
    *,
    weight_g,
    nutrition_per_100g,
) -> dict[str, float]:
    """Scale provided per-100g nutrition to an actual gram mass.

    The caller is responsible for supplying a normalized gram mass and the
    appropriate per-100g nutrition record.
    """

    weight = _require_positive_number(weight_g, "weight_g")
    nutrition = _normalize_nutrition(
        nutrition_per_100g,
        "nutrition_per_100g",
    )

    factor = weight / 100.0

    return {
        nutrient: nutrition[nutrient] * factor
        for nutrient in NUTRIENT_KEYS
    }


def calculate_batch_nutrition(ingredients) -> dict:
    """Return deterministic nutrition totals and total gram mass for a batch.

    Each ingredient must contain:

        {
            "weight_g": <positive normalized gram mass>,
            "nutrition_per_100g": {
                "calories": ...,
                "protein": ...,
                "carbs": ...,
                "fat": ...,
                "fiber": ...,
                "sugar": ...,
                "sodium": ...,
            },
        }

    No presentation rounding is performed.
    """

    if not isinstance(ingredients, (list, tuple)):
        raise BatchNutritionInputError(
            "ingredients must be a list or tuple"
        )

    if not ingredients:
        raise BatchNutritionInputError(
            "ingredients must contain at least one ingredient"
        )

    batch_weight_g = 0.0
    totals = {
        nutrient: 0.0
        for nutrient in NUTRIENT_KEYS
    }

    for index, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            raise BatchNutritionInputError(
                f"ingredients[{index}] must be a dictionary"
            )

        weight_g = _require_positive_number(
            ingredient.get("weight_g"),
            f"ingredients[{index}].weight_g",
        )

        ingredient_nutrition = calculate_ingredient_nutrition(
            weight_g=weight_g,
            nutrition_per_100g=ingredient.get(
                "nutrition_per_100g"
            ),
        )

        batch_weight_g += weight_g

        for nutrient in NUTRIENT_KEYS:
            totals[nutrient] += ingredient_nutrition[nutrient]

    return {
        "batch_weight_g": batch_weight_g,
        "nutrition": totals,
    }


def calculate_energy_density(
    *,
    batch_calories,
    batch_weight_g,
) -> float:
    """Return batch energy density in kcal per gram."""

    calories = _require_nonnegative_number(
        batch_calories,
        "batch_calories",
    )
    weight = _require_positive_number(
        batch_weight_g,
        "batch_weight_g",
    )

    return calories / weight


def scale_batch_nutrition_to_portion(
    *,
    batch_nutrition,
    batch_weight_g,
    portion_g,
) -> dict[str, float]:
    """Scale batch nutrition to a selected gram portion.

    This proportional scaling assumes a sufficiently homogeneous blended
    batch: each selected gram portion is assumed to contain the same nutrient
    proportions as the full batch.

    A portion larger than the available batch is rejected rather than
    silently clamped.
    """

    nutrition = _normalize_nutrition(
        batch_nutrition,
        "batch_nutrition",
    )
    batch_weight = _require_positive_number(
        batch_weight_g,
        "batch_weight_g",
    )
    portion = _require_positive_number(
        portion_g,
        "portion_g",
    )

    if portion > batch_weight:
        raise BatchNutritionInputError(
            "portion_g cannot exceed batch_weight_g"
        )

    ratio = portion / batch_weight

    return {
        nutrient: nutrition[nutrient] * ratio
        for nutrient in NUTRIENT_KEYS
    }
