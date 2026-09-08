"""Deterministic recipe nutrition calculation service.

This module connects the already-proven PureFyul boundaries:

recipe input
    -> recipe_mass
    -> exact nutrition lookup
    -> per-100g adapter contract
    -> batch nutrition

It does not recommend portions, optimize recipes, use EER, perform fuzzy
ingredient matching, infer liquid density, or use AI.
"""

from __future__ import annotations

import nutrition_facts_repository
from batch_nutrition import (
    calculate_batch_nutrition,
    calculate_energy_density,
    calculate_ingredient_nutrition,
    scale_batch_nutrition_to_portion,
)
from recipe_mass import normalize_recipe_mass


class RecipeCalculationError(ValueError):
    """Raised when a complete deterministic recipe cannot be calculated."""


def calculate_recipe(
    ingredients,
    *,
    portion_g=None,
) -> dict:
    """Calculate deterministic nutrition for one complete recipe.

    Every ingredient must first resolve to real gram mass.

    Every resolved ingredient must then have one exact nutrition_facts match.
    Missing nutrition fails the entire recipe rather than returning partial
    nutrition.

    ``portion_g`` is optional. When supplied, nutrition is proportionally
    scaled from the full homogeneous blended batch.
    """

    resolved_ingredients = normalize_recipe_mass(ingredients)

    calculated_ingredients = []
    batch_inputs = []

    for index, resolved in enumerate(resolved_ingredients):
        lookup_name = resolved["nutrition_lookup_name"]

        nutrition_record = (
            nutrition_facts_repository.get_nutrition_facts_exact(
                lookup_name
            )
        )

        if nutrition_record is None:
            raise RecipeCalculationError(
                "exact nutrition facts not found for "
                f"ingredient at index {index}: '{lookup_name}'"
            )

        nutrition_per_100g = nutrition_record["nutrition_per_100g"]
        weight_g = resolved["weight_g"]

        ingredient_nutrition = calculate_ingredient_nutrition(
            weight_g=weight_g,
            nutrition_per_100g=nutrition_per_100g,
        )

        batch_inputs.append(
            {
                "weight_g": weight_g,
                "nutrition_per_100g": nutrition_per_100g,
            }
        )

        calculated_ingredients.append(
            {
                "ingredient": resolved["ingredient"],
                "nutrition_lookup_name": lookup_name,
                "nutrition_record_name": nutrition_record["ingredient"],
                "weight_g": weight_g,
                "mass_source": resolved["mass_source"],
                "nutrition_per_100g": nutrition_per_100g,
                "nutrition": ingredient_nutrition,
            }
        )

    batch_result = calculate_batch_nutrition(batch_inputs)

    batch_weight_g = batch_result["batch_weight_g"]
    batch_nutrition = batch_result["nutrition"]

    result = {
        "ingredients": calculated_ingredients,
        "batch": {
            "weight_g": batch_weight_g,
            "nutrition": batch_nutrition,
            "energy_density_kcal_per_g": calculate_energy_density(
                batch_calories=batch_nutrition["calories"],
                batch_weight_g=batch_weight_g,
            ),
        },
        "portion": None,
    }

    if portion_g is not None:
        result["portion"] = {
            "weight_g": portion_g,
            "nutrition": scale_batch_nutrition_to_portion(
                batch_nutrition=batch_nutrition,
                batch_weight_g=batch_weight_g,
                portion_g=portion_g,
            ),
        }

    return result
