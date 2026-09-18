"""
Deterministic health-goal preset recipe sizing for PureFyul.

Preset contract:

- health goal + variant chooses the reviewed ingredient combination
  and its relative recipe proportions;
- timing chooses the target total smoothie weight;
- age, sex, activity level, and EER are intentionally not used;
- final ingredient weights are calculated server-side;
- nutrition calculation is delegated to recipe_calculator.

The proportion values below are recipe-composition weights, not
personalized serving recommendations.
"""

from __future__ import annotations

from copy import deepcopy

import recipe_calculator
import recipe_mass


class GoalPresetRecipeInputError(ValueError):
    """Raised when a preset request violates the supported contract."""


_TIMING_TARGET_WEIGHT_G = {
    "breakfast": 400.0,
    "morning-snack": 220.0,
    "lunch": 450.0,
    "afternoon-snack": 220.0,
    "dinner": 300.0,
    "bedtime": 180.0,
}


_PRESET_RECIPES = {
    ("skin-glow", "a"): {
        "display_name": "Skin Glow A",
        "proportion_source": "reviewed_skin_glow_a_recipe_composition",
        "ingredients": (
            {
                "id": "guava",
                "display_name": "Guava",
                "nutrition_lookup_name": "guava",
                "proportion": 134.0,
            },
            {
                "id": "pea-milk",
                "display_name": "Unsweetened Pea Milk",
                "nutrition_lookup_name": "pea milk",
                "proportion": 134.0,
            },
            {
                "id": "cucumber",
                "display_name": "Cucumber",
                "nutrition_lookup_name": "cucumber",
                "proportion": 54.0,
            },
            {
                "id": "cauliflower",
                "display_name": "Cauliflower",
                "nutrition_lookup_name": "cauliflower",
                "proportion": 54.0,
            },
            {
                "id": "hemp-seeds",
                "display_name": "Hemp Seeds",
                "nutrition_lookup_name": "hemp seeds",
                "proportion": 13.0,
            },
            {
                "id": "flax-seeds",
                "display_name": "Flax Seeds",
                "nutrition_lookup_name": "flax seeds",
                "proportion": 6.0,
            },
            {
                "id": "lime-juice",
                "display_name": "Lime Juice",
                "nutrition_lookup_name": "lime juice",
                "proportion": 4.5,
            },
        ),
    },
    ("skin-glow", "b"): {
        "display_name": "Skin Glow B",
        "proportion_source": "reviewed_skin_glow_b_recipe_composition",
        "ingredients": (
            {
                "id": "kiwi",
                "display_name": "Kiwi",
                "nutrition_lookup_name": "kiwi",
                "proportion": 70.0,
            },
            {
                "id": "strawberry",
                "display_name": "Strawberry",
                "nutrition_lookup_name": "strawberry",
                "proportion": 70.0,
            },
            {
                "id": "spinach",
                "display_name": "Spinach",
                "nutrition_lookup_name": "spinach",
                "proportion": 25.0,
            },
            {
                "id": "greek-yogurt",
                "display_name": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "proportion": 100.0,
            },
            {
                "id": "oat-milk",
                "display_name": "Unsweetened Oat Milk",
                "nutrition_lookup_name": "oat milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="oat milk",
                    volume_ml=120.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "chia-seeds",
                "display_name": "Chia Seeds",
                "nutrition_lookup_name": "chia seed",
                "proportion": 12.0,
            },
        ),
    },
    ("skin-glow", "c"): {
        "display_name": "Skin Glow C",
        "proportion_source": "reviewed_skin_glow_c_recipe_composition",
        "ingredients": (
            {
                "id": "papaya",
                "display_name": "Papaya",
                "nutrition_lookup_name": "papaya",
                "proportion": 90.0,
            },
            {
                "id": "mango",
                "display_name": "Mango",
                "nutrition_lookup_name": "mango",
                "proportion": 40.0,
            },
            {
                "id": "carrot",
                "display_name": "Carrot",
                "nutrition_lookup_name": "carrots",
                "proportion": 45.0,
            },
            {
                "id": "kefir",
                "display_name": "Kefir",
                "nutrition_lookup_name": "kefir",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="kefir",
                    volume_ml=100.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "coconut-water",
                "display_name": "Coconut Water",
                "nutrition_lookup_name": "coconut water",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="coconut water",
                    volume_ml=100.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "pumpkin-seeds",
                "display_name": "Pumpkin Seeds",
                "nutrition_lookup_name": "pumpkin seeds",
                "proportion": 20.0,
            },
        ),
    },
}


def _normalize_required_slug(value, *, field: str) -> str:
    if not isinstance(value, str):
        raise GoalPresetRecipeInputError(
            f"{field} must be a string"
        )

    normalized = value.strip().lower()

    if not normalized:
        raise GoalPresetRecipeInputError(
            f"{field} must be a non-empty string"
        )

    return normalized


def _build_scaled_weights(
    ingredients,
    *,
    target_weight_g: float,
) -> list[float]:
    proportions = [
        float(ingredient["proportion"])
        for ingredient in ingredients
    ]

    if any(value <= 0 for value in proportions):
        raise GoalPresetRecipeInputError(
            "preset ingredient proportions must be positive"
        )

    proportion_total = sum(proportions)

    if proportion_total <= 0:
        raise GoalPresetRecipeInputError(
            "preset proportion total must be positive"
        )

    scaled = [
        round(
            target_weight_g * proportion / proportion_total,
            3,
        )
        for proportion in proportions
    ]

    # Keep the server-side recipe mass exactly on the timing target
    # after deterministic rounding.
    scaled[-1] = round(
        scaled[-1] + (target_weight_g - sum(scaled)),
        3,
    )

    return scaled


def build_goal_preset_recipe(
    *,
    goal,
    timing,
    variant="a",
) -> dict:
    """Build one deterministic reviewed preset at its timing target weight."""

    normalized_goal = _normalize_required_slug(
        goal,
        field="goal",
    )
    normalized_timing = _normalize_required_slug(
        timing,
        field="timing",
    )
    normalized_variant = _normalize_required_slug(
        variant,
        field="variant",
    )

    target_weight_g = _TIMING_TARGET_WEIGHT_G.get(
        normalized_timing
    )

    if target_weight_g is None:
        raise GoalPresetRecipeInputError(
            f"unsupported preset timing: '{normalized_timing}'"
        )

    preset = _PRESET_RECIPES.get(
        (normalized_goal, normalized_variant)
    )

    if preset is None:
        raise GoalPresetRecipeInputError(
            "unsupported preset recipe: "
            f"goal='{normalized_goal}', "
            f"variant='{normalized_variant}'"
        )

    definitions = deepcopy(preset["ingredients"])

    scaled_weights = _build_scaled_weights(
        definitions,
        target_weight_g=target_weight_g,
    )

    recipe_inputs = [
        {
            "ingredient": definition["display_name"],
            "nutrition_lookup_name": definition[
                "nutrition_lookup_name"
            ],
            "amount": weight_g,
            "unit": "g",
        }
        for definition, weight_g in zip(
            definitions,
            scaled_weights,
            strict=True,
        )
    ]

    calculated = recipe_calculator.calculate_recipe(
        recipe_inputs
    )

    result_ingredients = []

    for definition, weight_g, calculated_ingredient in zip(
        definitions,
        scaled_weights,
        calculated["ingredients"],
        strict=True,
    ):
        display_unit = definition.get("display_unit", "g")

        if display_unit == "ml":
            display_amount = recipe_mass.convert_liquid_grams_to_ml(
                nutrition_lookup_name=definition["nutrition_lookup_name"],
                weight_g=weight_g,
            )
        else:
            display_amount = weight_g

        result_ingredients.append(
            {
                "id": definition["id"],
                "display_name": definition["display_name"],
                "nutrition_lookup_name": calculated_ingredient[
                    "nutrition_lookup_name"
                ],
                "nutrition_record_name": calculated_ingredient[
                    "nutrition_record_name"
                ],
                "amount": round(display_amount, 3),
                "unit": display_unit,
                "weight_g": calculated_ingredient["weight_g"],
                "mass_source": calculated_ingredient["mass_source"],
                "nutrition": calculated_ingredient["nutrition"],
            }
        )

    result_batch = deepcopy(calculated["batch"])
    result_batch["weight_g"] = round(float(target_weight_g), 3)

    return {
        "goal": normalized_goal,
        "timing": normalized_timing,
        "variant": normalized_variant,
        "display_name": preset["display_name"],
        "target_weight_g": target_weight_g,
        "ingredients": result_ingredients,
        "batch": result_batch,
        "portion": None,
        "preset_contract": {
            "personalized": False,
            "uses_age": False,
            "uses_sex": False,
            "uses_eer": False,
            "weight_source": "timing",
            "composition_source": preset["proportion_source"],
        },
    }
