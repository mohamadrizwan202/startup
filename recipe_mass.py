"""Resolve recipe ingredient inputs to real gram mass.

This module defines the mass boundary for deterministic smoothie nutrition.

Accepted input units:
- ``g``: already-resolved gram mass;
- ``ml``: accepted only when PureFyul has an explicit mass conversion for
  that exact nutrition ingredient.

This module deliberately does NOT:
- treat 1 mL as 1 g;
- trust legacy browser ``nutritionWeightG`` fields;
- infer density for plant milks or other liquids;
- calculate nutrition;
- look up nutrition database rows;
- calculate or recommend portion sizes;
- perform fuzzy ingredient matching.

Current explicit liquid conversions come from PureFyul's existing citrus
contract:
- lemon juice: USDA household weight 244 g per 240 mL, FDC 167747;
- lime juice: USDA household weight 242 g per 240 mL, FDC 168156.
"""

from __future__ import annotations

import math


class RecipeMassResolutionError(ValueError):
    """Raised when an ingredient cannot be resolved to defensible gram mass."""


_CITRUS_GRAMS_PER_ML = {
    "lemon juice": 244.0 / 240.0,
    "lime juice": 242.0 / 240.0,
}


def _require_nonempty_string(value, field_name: str) -> str:
    if not isinstance(value, str):
        raise RecipeMassResolutionError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise RecipeMassResolutionError(
            f"{field_name} must be a non-empty string"
        )

    return normalized


def _require_positive_number(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise RecipeMassResolutionError(
            f"{field_name} must be numeric"
        )

    number = float(value)

    if not math.isfinite(number):
        raise RecipeMassResolutionError(
            f"{field_name} must be finite"
        )

    if number <= 0:
        raise RecipeMassResolutionError(
            f"{field_name} must be greater than zero"
        )

    return number


def normalize_recipe_ingredient_mass(
    *,
    ingredient,
    nutrition_lookup_name,
    amount,
    unit,
) -> dict:
    """Resolve one normalized recipe input to gram mass.

    ``amount`` means exactly what ``unit`` says. A caller must not pass a
    milliliter quantity labeled as grams.

    Gram inputs are preserved directly.

    Milliliter inputs require an explicit conversion registered in this
    module. Unknown liquid densities fail closed rather than assuming
    1 mL == 1 g.
    """

    ingredient_name = _require_nonempty_string(
        ingredient,
        "ingredient",
    )

    lookup_name = _require_nonempty_string(
        nutrition_lookup_name,
        "nutrition_lookup_name",
    )

    normalized_unit = _require_nonempty_string(
        unit,
        "unit",
    ).lower()

    numeric_amount = _require_positive_number(
        amount,
        "amount",
    )

    if normalized_unit == "g":
        return {
            "ingredient": ingredient_name,
            "nutrition_lookup_name": lookup_name,
            "weight_g": numeric_amount,
            "mass_source": "gram_input",
        }

    if normalized_unit != "ml":
        raise RecipeMassResolutionError(
            "unit must be 'g' or 'ml'"
        )

    grams_per_ml = _CITRUS_GRAMS_PER_ML.get(
        lookup_name.lower()
    )

    if grams_per_ml is None:
        raise RecipeMassResolutionError(
            f"mass conversion is unresolved for '{lookup_name}'"
        )

    return {
        "ingredient": ingredient_name,
        "nutrition_lookup_name": lookup_name,
        "weight_g": numeric_amount * grams_per_ml,
        "mass_source": "explicit_household_weight_conversion",
    }


def normalize_recipe_mass(ingredients) -> list[dict]:
    """Resolve every ingredient in a recipe to real gram mass."""

    if not isinstance(ingredients, (list, tuple)):
        raise RecipeMassResolutionError(
            "ingredients must be a list or tuple"
        )

    if not ingredients:
        raise RecipeMassResolutionError(
            "ingredients cannot be empty"
        )

    normalized = []

    for index, item in enumerate(ingredients):
        if not isinstance(item, dict):
            raise RecipeMassResolutionError(
                f"ingredient at index {index} must be a dictionary"
            )

        try:
            normalized.append(
                normalize_recipe_ingredient_mass(
                    ingredient=item.get("ingredient"),
                    nutrition_lookup_name=item.get(
                        "nutrition_lookup_name"
                    ),
                    amount=item.get("amount"),
                    unit=item.get("unit"),
                )
            )
        except RecipeMassResolutionError as exc:
            raise RecipeMassResolutionError(
                f"ingredient at index {index}: {exc}"
            ) from exc

    return normalized
