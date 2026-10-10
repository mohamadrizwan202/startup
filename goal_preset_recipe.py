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
from statistics import median

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

    ("gut-health", "a"): {
        "display_name": "Gut Health A",
        "proportion_source": "reviewed_gut_health_a_recipe_composition",
        "ingredients": (
            {
                "id": "kefir",
                "display_name": "Kefir",
                "nutrition_lookup_name": "kefir",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="kefir",
                    volume_ml=150.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "kiwi",
                "display_name": "Kiwi",
                "nutrition_lookup_name": "kiwi",
                "proportion": 90.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 35.0,
            },
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 100.0,
            },
            {
                "id": "flax-seeds",
                "display_name": "Flax Seeds",
                "nutrition_lookup_name": "flax seeds",
                "proportion": 20.0,
            },
        ),
    },
    ("gut-health", "b"): {
        "display_name": "Gut Health B",
        "proportion_source": "reviewed_gut_health_b_recipe_composition",
        "ingredients": (
            {
                "id": "yogurt",
                "display_name": "Yogurt",
                "nutrition_lookup_name": "yogurt",
                "proportion": 120.0,
            },
            {
                "id": "prune",
                "display_name": "Prune",
                "nutrition_lookup_name": "prune",
                "proportion": 50.0,
            },
            {
                "id": "kiwi",
                "display_name": "Kiwi",
                "nutrition_lookup_name": "kiwi",
                "proportion": 90.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 35.0,
            },
            {
                "id": "raspberry",
                "display_name": "Raspberry",
                "nutrition_lookup_name": "raspberry",
                "proportion": 105.0,
            },
        ),
    },
    ("gut-health", "c"): {
        "display_name": "Gut Health C",
        "proportion_source": "reviewed_gut_health_c_recipe_composition",
        "ingredients": (
            {
                "id": "kefir",
                "display_name": "Kefir",
                "nutrition_lookup_name": "kefir",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="kefir",
                    volume_ml=190.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "prune",
                "display_name": "Prune",
                "nutrition_lookup_name": "prune",
                "proportion": 45.0,
            },
            {
                "id": "apple",
                "display_name": "Apple",
                "nutrition_lookup_name": "apple",
                "proportion": 110.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 35.0,
            },
            {
                "id": "chia-seeds",
                "display_name": "Chia Seeds",
                "nutrition_lookup_name": "chia seed",
                "proportion": 15.0,
            },
        ),
    },

    ("brain-focus", "a"): {
        "display_name": "Brain Focus A",
        "proportion_source": "reviewed_brain_focus_a_recipe_composition",
        "ingredients": (
            {
                "id": "blueberry",
                "display_name": "Blueberry",
                "nutrition_lookup_name": "blueberry",
                "proportion": 90.0,
            },
            {
                "id": "raspberry",
                "display_name": "Raspberry",
                "nutrition_lookup_name": "raspberry",
                "proportion": 70.0,
            },
            {
                "id": "blackberry",
                "display_name": "Blackberry",
                "nutrition_lookup_name": "blackberry",
                "proportion": 60.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "greek-yogurt",
                "display_name": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "proportion": 120.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 40.0,
            },
        ),
    },
    ("brain-focus", "b"): {
        "display_name": "Brain Focus B",
        "proportion_source": "reviewed_brain_focus_b_recipe_composition",
        "ingredients": (
            {
                "id": "blueberry",
                "display_name": "Blueberry",
                "nutrition_lookup_name": "blueberry",
                "proportion": 100.0,
            },
            {
                "id": "strawberry",
                "display_name": "Strawberry",
                "nutrition_lookup_name": "strawberry",
                "proportion": 80.0,
            },
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 80.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "oat-milk",
                "display_name": "Oat Milk",
                "nutrition_lookup_name": "oat milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="oat milk",
                    volume_ml=105.0,
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
    ("brain-focus", "c"): {
        "display_name": "Brain Focus C",
        "proportion_source": "reviewed_brain_focus_c_recipe_composition",
        "ingredients": (
            {
                "id": "blueberry",
                "display_name": "Blueberry",
                "nutrition_lookup_name": "blueberry",
                "proportion": 90.0,
            },
            {
                "id": "spinach",
                "display_name": "Spinach",
                "nutrition_lookup_name": "spinach",
                "proportion": 25.0,
            },
            {
                "id": "raspberry",
                "display_name": "Raspberry",
                "nutrition_lookup_name": "raspberry",
                "proportion": 70.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "almond-milk",
                "display_name": "Almond Milk",
                "nutrition_lookup_name": "almond milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="almond milk",
                    volume_ml=180.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "flax-seeds",
                "display_name": "Flax Seeds",
                "nutrition_lookup_name": "flax seeds",
                "proportion": 15.0,
            },
        ),
    },

    ("heart-support", "a"): {
        "display_name": "Heart Support A",
        "proportion_source": "reviewed_heart_support_a_recipe_composition",
        "ingredients": (
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 45.0,
            },
            {
                "id": "blueberry",
                "display_name": "Blueberry",
                "nutrition_lookup_name": "blueberry",
                "proportion": 90.0,
            },
            {
                "id": "apple",
                "display_name": "Apple",
                "nutrition_lookup_name": "apple",
                "proportion": 90.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "flax-seeds",
                "display_name": "Flax Seeds",
                "nutrition_lookup_name": "flax seeds",
                "proportion": 15.0,
            },
            {
                "id": "almond-milk",
                "display_name": "Almond Milk",
                "nutrition_lookup_name": "almond milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="almond milk",
                    volume_ml=140.0,
                ),
                "display_unit": "ml",
            },
        ),
    },
    ("heart-support", "b"): {
        "display_name": "Heart Support B",
        "proportion_source": "reviewed_heart_support_b_recipe_composition",
        "ingredients": (
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 40.0,
            },
            {
                "id": "strawberry",
                "display_name": "Strawberry",
                "nutrition_lookup_name": "strawberry",
                "proportion": 90.0,
            },
            {
                "id": "raspberry",
                "display_name": "Raspberry",
                "nutrition_lookup_name": "raspberry",
                "proportion": 75.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "chia-seeds",
                "display_name": "Chia Seeds",
                "nutrition_lookup_name": "chia seed",
                "proportion": 15.0,
            },
            {
                "id": "oat-milk",
                "display_name": "Oat Milk",
                "nutrition_lookup_name": "oat milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="oat milk",
                    volume_ml=156.0,
                ),
                "display_unit": "ml",
            },
        ),
    },
    ("heart-support", "c"): {
        "display_name": "Heart Support C",
        "proportion_source": "reviewed_heart_support_c_recipe_composition",
        "ingredients": (
            {
                "id": "blackberry",
                "display_name": "Blackberry",
                "nutrition_lookup_name": "blackberry",
                "proportion": 90.0,
            },
            {
                "id": "apple",
                "display_name": "Apple",
                "nutrition_lookup_name": "apple",
                "proportion": 110.0,
            },
            {
                "id": "spinach",
                "display_name": "Spinach",
                "nutrition_lookup_name": "spinach",
                "proportion": 25.0,
            },
            {
                "id": "walnuts",
                "display_name": "Walnuts",
                "nutrition_lookup_name": "walnuts",
                "proportion": 20.0,
            },
            {
                "id": "flax-seeds",
                "display_name": "Flax Seeds",
                "nutrition_lookup_name": "flax seeds",
                "proportion": 15.0,
            },
            {
                "id": "almond-milk",
                "display_name": "Almond Milk",
                "nutrition_lookup_name": "almond milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="almond milk",
                    volume_ml=140.0,
                ),
                "display_unit": "ml",
            },
        ),
    },

    ("energy-stamina", "a"): {
        "display_name": "Energy & Stamina A",
        "proportion_source": "reviewed_energy_stamina_a_recipe_composition",
        "ingredients": (
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 100.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 35.0,
            },
            {
                "id": "beets",
                "display_name": "Beets",
                "nutrition_lookup_name": "beets",
                "proportion": 60.0,
            },
            {
                "id": "mango",
                "display_name": "Mango",
                "nutrition_lookup_name": "mango",
                "proportion": 80.0,
            },
            {
                "id": "coconut-water",
                "display_name": "Coconut Water",
                "nutrition_lookup_name": "coconut water",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="coconut water",
                    volume_ml=125.0,
                ),
                "display_unit": "ml",
            },
        ),
    },
    ("energy-stamina", "b"): {
        "display_name": "Energy & Stamina B",
        "proportion_source": "reviewed_energy_stamina_b_recipe_composition",
        "ingredients": (
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 90.0,
            },
            {
                "id": "date",
                "display_name": "Date",
                "nutrition_lookup_name": "date",
                "proportion": 30.0,
            },
            {
                "id": "pineapple",
                "display_name": "Pineapple",
                "nutrition_lookup_name": "pineapple",
                "proportion": 80.0,
            },
            {
                "id": "greek-yogurt",
                "display_name": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "proportion": 90.0,
            },
            {
                "id": "oat-milk",
                "display_name": "Oat Milk",
                "nutrition_lookup_name": "oat milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="oat milk",
                    volume_ml=105.0,
                ),
                "display_unit": "ml",
            },
        ),
    },
    ("energy-stamina", "c"): {
        "display_name": "Energy & Stamina C",
        "proportion_source": "reviewed_energy_stamina_c_recipe_composition",
        "ingredients": (
            {
                "id": "beets",
                "display_name": "Beets",
                "nutrition_lookup_name": "beets",
                "proportion": 70.0,
            },
            {
                "id": "orange",
                "display_name": "Orange",
                "nutrition_lookup_name": "orange",
                "proportion": 70.0,
            },
            {
                "id": "mango",
                "display_name": "Mango",
                "nutrition_lookup_name": "mango",
                "proportion": 70.0,
            },
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 70.0,
            },
            {
                "id": "coconut-water",
                "display_name": "Coconut Water",
                "nutrition_lookup_name": "coconut water",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="coconut water",
                    volume_ml=90.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 28.0,
            },
        ),
    },
    ("muscle-health", "a"): {
        "display_name": "Muscle Health A",
        "proportion_source": "reviewed_muscle_health_a_recipe_composition",
        "ingredients": (
            {
                "id": "greek-yogurt",
                "display_name": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "proportion": 120.0,
            },
            {
                "id": "banana",
                "display_name": "Banana",
                "nutrition_lookup_name": "banana",
                "proportion": 80.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 40.0,
            },
            {
                "id": "soy-milk",
                "display_name": "Soy Milk",
                "nutrition_lookup_name": "soy milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="soy milk",
                    volume_ml=135.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "hemp-seeds",
                "display_name": "Hemp Seeds",
                "nutrition_lookup_name": "hemp seeds",
                "proportion": 20.0,
            },
        ),
    },
    ("muscle-health", "b"): {
        "display_name": "Muscle Health B",
        "proportion_source": "reviewed_muscle_health_b_recipe_composition",
        "ingredients": (
            {
                "id": "skyr",
                "display_name": "Skyr",
                "nutrition_lookup_name": "skyr",
                "proportion": 120.0,
            },
            {
                "id": "strawberry",
                "display_name": "Strawberry",
                "nutrition_lookup_name": "strawberry",
                "proportion": 90.0,
            },
            {
                "id": "oats",
                "display_name": "Oats",
                "nutrition_lookup_name": "oats",
                "proportion": 35.0,
            },
            {
                "id": "2-percent-milk",
                "display_name": "2% Milk",
                "nutrition_lookup_name": "2% milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="2% milk",
                    volume_ml=135.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "chia-seeds",
                "display_name": "Chia Seeds",
                "nutrition_lookup_name": "chia seed",
                "proportion": 15.0,
            },
        ),
    },
    ("muscle-health", "c"): {
        "display_name": "Muscle Health C",
        "proportion_source": "reviewed_muscle_health_c_recipe_composition",
        "ingredients": (
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
                "id": "blueberry",
                "display_name": "Blueberry",
                "nutrition_lookup_name": "blueberry",
                "proportion": 80.0,
            },
            {
                "id": "greek-yogurt",
                "display_name": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "proportion": 100.0,
            },
            {
                "id": "oat-milk",
                "display_name": "Oat Milk",
                "nutrition_lookup_name": "oat milk",
                "proportion": recipe_mass.convert_liquid_ml_to_grams(
                    nutrition_lookup_name="oat milk",
                    volume_ml=95.0,
                ),
                "display_unit": "ml",
            },
            {
                "id": "hemp-seeds",
                "display_name": "Hemp Seeds",
                "nutrition_lookup_name": "hemp seeds",
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


def get_supported_goal_slugs() -> tuple[str, ...]:
    """Return canonical goal slugs backed by reviewed preset recipes."""
    return tuple(
        sorted(
            {
                goal_slug
                for goal_slug, _variant in _PRESET_RECIPES
            }
        )
    )


def get_supported_timing_slugs() -> tuple[str, ...]:
    """Return canonical timing slugs backed by preset target weights."""
    return tuple(_TIMING_TARGET_WEIGHT_G)


def get_reviewed_goal_recipe_candidates(goal) -> tuple[dict, ...]:
    """Return complete reviewed recipe candidates for one health goal."""
    normalized_goal = _normalize_required_slug(
        goal,
        field="goal",
    )

    candidates = []

    for (candidate_goal, variant), preset in sorted(
        _PRESET_RECIPES.items()
    ):
        if candidate_goal != normalized_goal:
            continue

        candidates.append({
            "variant": variant,
            "display_name": preset["display_name"],
            "ingredient_ids": tuple(
                ingredient["id"]
                for ingredient in preset["ingredients"]
            ),
        })

    if not candidates:
        raise GoalPresetRecipeInputError(
            f"unsupported preset goal: '{normalized_goal}'"
        )

    return tuple(candidates)


def get_supported_ingredient_ids() -> tuple[str, ...]:
    """Return canonical ingredient IDs used by reviewed preset recipes."""
    return tuple(
        sorted(
            {
                ingredient["id"]
                for preset in _PRESET_RECIPES.values()
                for ingredient in preset["ingredients"]
            }
        )
    )


_PERSONALIZATION_INGREDIENT_DISPLAY_NAME_OVERRIDES = {
    "oat-milk": "Oat Milk",
}


def get_supported_ingredient_options() -> tuple[dict[str, str], ...]:
    """Return canonical ingredient IDs and display labels for personalization."""
    display_names_by_id: dict[str, set[str]] = {}

    for preset in _PRESET_RECIPES.values():
        for ingredient in preset["ingredients"]:
            ingredient_id = ingredient["id"]
            display_name = ingredient["display_name"]

            display_names_by_id.setdefault(
                ingredient_id,
                set(),
            ).add(display_name)

    options = []

    for ingredient_id in sorted(display_names_by_id):
        display_names = display_names_by_id[ingredient_id]

        if ingredient_id in _PERSONALIZATION_INGREDIENT_DISPLAY_NAME_OVERRIDES:
            display_name = (
                _PERSONALIZATION_INGREDIENT_DISPLAY_NAME_OVERRIDES[
                    ingredient_id
                ]
            )
        elif len(display_names) == 1:
            display_name = next(iter(display_names))
        else:
            raise RuntimeError(
                "Ingredient has conflicting display names without "
                f"an explicit personalization override: "
                f"{ingredient_id}={sorted(display_names)!r}"
            )

        options.append({
            "id": ingredient_id,
            "display_name": display_name,
        })

    return tuple(options)


def _get_personalization_catalog_definitions() -> dict[str, dict]:
    """Return canonical reviewed definitions for editable catalog items."""
    candidates_by_id: dict[str, list[dict]] = {}

    for preset in _PRESET_RECIPES.values():
        for ingredient in preset["ingredients"]:
            candidates_by_id.setdefault(
                ingredient["id"],
                [],
            ).append(ingredient)

    definitions_by_id: dict[str, dict] = {}

    for ingredient_id in sorted(candidates_by_id):
        candidates = candidates_by_id[ingredient_id]
        display_names = {
            candidate["display_name"]
            for candidate in candidates
        }
        nutrition_lookup_names = {
            candidate["nutrition_lookup_name"]
            for candidate in candidates
        }
        display_units = {
            candidate.get("display_unit", "g")
            for candidate in candidates
        }

        if (
            len(nutrition_lookup_names) != 1
            or len(display_units) != 1
        ):
            raise RuntimeError(
                "Ingredient has conflicting personalization metadata: "
                f"{ingredient_id}={candidates!r}"
            )

        if ingredient_id in _PERSONALIZATION_INGREDIENT_DISPLAY_NAME_OVERRIDES:
            display_name = (
                _PERSONALIZATION_INGREDIENT_DISPLAY_NAME_OVERRIDES[
                    ingredient_id
                ]
            )
        elif len(display_names) == 1:
            display_name = next(iter(display_names))
        else:
            raise RuntimeError(
                "Ingredient has conflicting display names without "
                f"an explicit personalization override: "
                f"{ingredient_id}={sorted(display_names)!r}"
            )

        definition = deepcopy(candidates[0])
        definition["display_name"] = display_name
        definition["nutrition_lookup_name"] = next(
            iter(nutrition_lookup_names)
        )
        definition["display_unit"] = next(iter(display_units))
        definition["proportion"] = float(
            median(
                float(candidate["proportion"])
                for candidate in candidates
            )
        )
        definitions_by_id[ingredient_id] = definition

    return definitions_by_id


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


def build_personalized_goal_preset_recipe(
    *,
    goal,
    timing,
    variant,
    ingredient_ids,
) -> dict:
    """Build one explicit Personalize editor selection."""

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

    if not isinstance(ingredient_ids, list):
        raise GoalPresetRecipeInputError(
            "ingredient_ids must be a list"
        )

    if not ingredient_ids:
        raise GoalPresetRecipeInputError(
            "at least 3 ingredients are required"
        )

    normalized_ingredient_ids = [
        _normalize_required_slug(
            ingredient_id,
            field="ingredient_id",
        )
        for ingredient_id in ingredient_ids
    ]

    if len(normalized_ingredient_ids) != len(
        set(normalized_ingredient_ids)
    ):
        raise GoalPresetRecipeInputError(
            "duplicate ingredient selections are not allowed"
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

    catalog_definitions = (
        _get_personalization_catalog_definitions()
    )
    unsupported_ingredient_ids = [
        ingredient_id
        for ingredient_id in normalized_ingredient_ids
        if ingredient_id not in catalog_definitions
    ]

    if unsupported_ingredient_ids:
        raise GoalPresetRecipeInputError(
            "ingredient is not supported for personalization: "
            f"'{unsupported_ingredient_ids[0]}'"
        )

    if len(normalized_ingredient_ids) < 3:
        raise GoalPresetRecipeInputError(
            "at least 3 ingredients are required"
        )

    preset_definitions_by_id = {
        ingredient["id"]: ingredient
        for ingredient in preset["ingredients"]
    }
    has_catalog_addition = any(
        ingredient_id not in preset_definitions_by_id
        for ingredient_id in normalized_ingredient_ids
    )

    if has_catalog_addition:
        definitions = [
            deepcopy(
                preset_definitions_by_id[ingredient_id]
            )
            if ingredient_id in preset_definitions_by_id
            else deepcopy(catalog_definitions[ingredient_id])
            for ingredient_id in normalized_ingredient_ids
        ]
        weight_source = (
            "normalized_selected_reference_amounts"
        )
        composition_source = (
            "user_selected_preset_and_catalog_composition"
        )
    else:
        selected_ingredient_ids = set(
            normalized_ingredient_ids
        )
        definitions = [
            deepcopy(ingredient)
            for ingredient in preset["ingredients"]
            if ingredient["id"] in selected_ingredient_ids
        ]
        weight_source = (
            "normalized_retained_preset_amounts"
        )
        composition_source = (
            "user_edited_reviewed_preset_composition"
        )

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
                nutrition_lookup_name=definition[
                    "nutrition_lookup_name"
                ],
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
    result_batch["weight_g"] = round(
        float(calculated["batch"]["weight_g"]),
        3,
    )

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
            "personalized": True,
            "uses_age": False,
            "uses_sex": False,
            "uses_eer": False,
            "weight_source": weight_source,
            "composition_source": composition_source,
        },
    }
