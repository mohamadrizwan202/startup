"""Deterministic mobile starter-recipe bridge for PureFyul.

Starter amounts are product editing defaults only.

They are NOT:
- personalized serving recommendations;
- age-, sex-, activity-, timing-, or health-goal recommendations;
- EER-derived portions;
- dietary prescriptions.

This module maps the small, explicit Flutter ingredient catalog onto
deterministic recipe inputs and delegates all nutrition calculation to
``recipe_calculator.calculate_recipe``.

Unsupported or scientifically unresolved inputs fail closed.
"""

from __future__ import annotations

from copy import deepcopy

import recipe_calculator


class StarterRecipeInputError(ValueError):
    """Raised when a starter-recipe request violates the mobile contract."""


class StarterRecipeUnavailableError(ValueError):
    """Raised when PureFyul cannot yet build a defensible starter recipe."""

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        ingredient_id: str,
    ):
        super().__init__(message)
        self.reason = reason
        self.ingredient_id = ingredient_id


# These are product starter values, not dietary recommendations.
#
# Only the six ingredient IDs currently exposed by the Flutter catalog belong
# here. Adding another ingredient requires an explicit product starter amount,
# an exact nutrition lookup name, and defensible mass handling.
_STARTER_INGREDIENTS = {
    "blueberries": {
        "display_name": "Blueberries",
        "nutrition_lookup_name": "blueberries",
        "amount": 100.0,
        "unit": "g",
        "starter_source": "existing_no_age_fresh_fruit_default",
        "available": True,
    },
    "mango": {
        "display_name": "Mango",
        "nutrition_lookup_name": "mango",
        "amount": 100.0,
        "unit": "g",
        "starter_source": "existing_no_age_fresh_fruit_default",
        "available": True,
    },
    "spinach": {
        "display_name": "Spinach",
        "nutrition_lookup_name": "spinach",
        "amount": 30.0,
        "unit": "g",
        "starter_source": "usda_household_measure_1_cup_raw",
        "available": True,
    },
    "oat-milk": {
        "display_name": "Oat Milk",
        "nutrition_lookup_name": "oat milk",
        "amount": 240.0,
        "unit": "ml",
        "starter_source": "existing_no_age_plant_milk_default",
        "available": True,
    },
    "chia-seeds": {
        "display_name": "Chia Seeds",
        "nutrition_lookup_name": "chia seed",
        "amount": 12.0,
        "unit": "g",
        "starter_source": "existing_no_age_seed_default",
        "available": True,
    },
    "greek-yogurt": {
        "display_name": "Greek Yogurt",
        "nutrition_lookup_name": "greek yogurt",
        "amount": 170.0,
        "unit": "g",
        "starter_source": "existing_staple_reference_default",
        "available": True,
    },
}


def get_mobile_starter_definition(ingredient_id: str) -> dict:
    """Return one defensive copy of the explicit mobile starter definition."""

    if not isinstance(ingredient_id, str):
        raise StarterRecipeInputError("ingredient id must be a string")

    normalized_id = ingredient_id.strip()

    if not normalized_id:
        raise StarterRecipeInputError(
            "ingredient id must be a non-empty string"
        )

    definition = _STARTER_INGREDIENTS.get(normalized_id)

    if definition is None:
        raise StarterRecipeInputError(
            f"unsupported mobile ingredient id: '{normalized_id}'"
        )

    return {
        "id": normalized_id,
        **deepcopy(definition),
    }


def build_starter_recipe(selected_ingredient_ids) -> dict:
    """Build deterministic nutrition for selected Flutter ingredient IDs."""

    if not isinstance(selected_ingredient_ids, (list, tuple)):
        raise StarterRecipeInputError(
            "selected_ingredient_ids must be a list or tuple"
        )

    if not selected_ingredient_ids:
        raise StarterRecipeInputError(
            "selected_ingredient_ids cannot be empty"
        )

    definitions = []
    seen_ids = set()

    for index, raw_id in enumerate(selected_ingredient_ids):
        try:
            definition = get_mobile_starter_definition(raw_id)
        except StarterRecipeInputError as exc:
            raise StarterRecipeInputError(
                f"ingredient at index {index}: {exc}"
            ) from exc

        ingredient_id = definition["id"]

        if ingredient_id in seen_ids:
            raise StarterRecipeInputError(
                f"duplicate ingredient id: '{ingredient_id}'"
            )

        seen_ids.add(ingredient_id)
        definitions.append(definition)

    for definition in definitions:
        if not definition["available"]:
            reason = definition["unavailable_reason"]
            ingredient_id = definition["id"]

            raise StarterRecipeUnavailableError(
                "starter recipe is unavailable for "
                f"'{ingredient_id}': {reason}",
                reason=reason,
                ingredient_id=ingredient_id,
            )

    recipe_inputs = [
        {
            "ingredient": definition["display_name"],
            "nutrition_lookup_name": definition[
                "nutrition_lookup_name"
            ],
            "amount": definition["amount"],
            "unit": definition["unit"],
        }
        for definition in definitions
    ]

    calculated = recipe_calculator.calculate_recipe(recipe_inputs)

    bridged_ingredients = []

    for definition, calculated_ingredient in zip(
        definitions,
        calculated["ingredients"],
        strict=True,
    ):
        bridged_ingredients.append(
            {
                "id": definition["id"],
                "display_name": definition["display_name"],
                "amount": definition["amount"],
                "unit": definition["unit"],
                "starter_source": definition["starter_source"],
                "nutrition_lookup_name": calculated_ingredient[
                    "nutrition_lookup_name"
                ],
                "nutrition_record_name": calculated_ingredient[
                    "nutrition_record_name"
                ],
                "weight_g": calculated_ingredient["weight_g"],
                "mass_source": calculated_ingredient["mass_source"],
                "nutrition": calculated_ingredient["nutrition"],
            }
        )

    return {
        "ingredients": bridged_ingredients,
        "batch": calculated["batch"],
        "portion": None,
        "starter_amount_contract": {
            "personalized": False,
            "dietary_recommendation": False,
        },
    }
