"""Deterministic smoothie nutrition tuning.

This module does not decide what a user should eat.

It accepts:
- an already-calculated PureFyul recipe,
- explicit allowed gram bounds for every ingredient,
- explicit minimum and/or maximum nutrient targets.

It then finds the feasible recipe closest to the original recipe.

"Closest" means minimum total proportional ingredient change:
    sum(abs(new_weight - original_weight) / original_weight)

No AI, EER, BMI, fuzzy lookup, density inference, serving recommendation,
or presentation rounding occurs here.
"""

from __future__ import annotations

import math

from scipy.optimize import linprog

from batch_nutrition import (
    NUTRIENT_KEYS,
    calculate_batch_nutrition,
    calculate_energy_density,
)


class SmoothieTuningInputError(ValueError):
    """Raised when tuning inputs violate the deterministic contract."""


class SmoothieTuningInfeasibleError(ValueError):
    """Raised when no recipe can satisfy all supplied constraints."""


class SmoothieTuningSolverError(RuntimeError):
    """Raised when the numerical solver fails unexpectedly."""


TECHNICAL_MIN_EDIT_WEIGHT_G = 1.0


def build_tuning_bounds(
    *,
    recipe_result,
    adjustable_indices,
) -> list[dict]:
    """Build technical editing bounds for a calculated recipe.

    This helper does NOT define healthy, recommended, or age-based serving
    ranges.

    Ingredients explicitly listed in ``adjustable_indices`` may be
    redistributed between the existing PureFyul technical editing floor
    and the total recipe weight.

    All other ingredients are locked exactly at their original weight.

    The total-weight preservation constraint, when enabled in
    ``tune_calculated_recipe``, prevents the recipe from becoming larger
    or smaller overall.
    """

    if not isinstance(recipe_result, dict):
        raise SmoothieTuningInputError(
            "recipe_result must be a dictionary"
        )

    ingredients = recipe_result.get("ingredients")

    if not isinstance(ingredients, list) or not ingredients:
        raise SmoothieTuningInputError(
            "recipe_result.ingredients must be a non-empty list"
        )

    if not isinstance(adjustable_indices, (list, tuple, set)):
        raise SmoothieTuningInputError(
            "adjustable_indices must be a list, tuple, or set"
        )

    normalized_indices = []

    for value in adjustable_indices:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SmoothieTuningInputError(
                "adjustable_indices must contain integer indices"
            )

        if value < 0 or value >= len(ingredients):
            raise SmoothieTuningInputError(
                f"adjustable ingredient index out of range: {value}"
            )

        normalized_indices.append(value)

    if not normalized_indices:
        raise SmoothieTuningInputError(
            "at least one adjustable ingredient is required"
        )

    if len(set(normalized_indices)) != len(normalized_indices):
        raise SmoothieTuningInputError(
            "adjustable_indices cannot contain duplicates"
        )

    adjustable = set(normalized_indices)

    original_weights = []

    for index, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            raise SmoothieTuningInputError(
                f"recipe_result.ingredients[{index}] "
                "must be a dictionary"
            )

        original_weights.append(
            _require_number(
                ingredient.get("weight_g"),
                f"recipe_result.ingredients[{index}].weight_g",
                positive=True,
            )
        )

    total_weight = sum(original_weights)
    bounds = []

    for index, original_weight in enumerate(original_weights):
        if index not in adjustable:
            bounds.append(
                {
                    "min_weight_g": original_weight,
                    "max_weight_g": original_weight,
                }
            )
            continue

        # Preserve an existing sub-1g amount if one ever reaches this
        # boundary rather than forcing the ingredient upward.
        technical_floor = min(
            TECHNICAL_MIN_EDIT_WEIGHT_G,
            original_weight,
        )

        bounds.append(
            {
                "min_weight_g": technical_floor,
                "max_weight_g": total_weight,
            }
        )

    return bounds


def _require_number(value, field_name: str, *, positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SmoothieTuningInputError(
            f"{field_name} must be a finite number"
        )

    numeric = float(value)

    if not math.isfinite(numeric):
        raise SmoothieTuningInputError(
            f"{field_name} must be a finite number"
        )

    if positive:
        if numeric <= 0:
            raise SmoothieTuningInputError(
                f"{field_name} must be greater than zero"
            )
    elif numeric < 0:
        raise SmoothieTuningInputError(
            f"{field_name} cannot be negative"
        )

    return numeric


def _normalize_targets(targets, field_name: str) -> dict[str, float]:
    if targets is None:
        return {}

    if not isinstance(targets, dict):
        raise SmoothieTuningInputError(
            f"{field_name} must be a dictionary"
        )

    normalized = {}

    for nutrient, value in targets.items():
        if nutrient not in NUTRIENT_KEYS:
            raise SmoothieTuningInputError(
                f"{field_name} contains unsupported nutrient "
                f"'{nutrient}'"
            )

        normalized[nutrient] = _require_number(
            value,
            f"{field_name}.{nutrient}",
        )

    return normalized


def tune_calculated_recipe(
    *,
    recipe_result,
    ingredient_bounds,
    minimums=None,
    maximums=None,
    preserve_total_weight=False,
) -> dict:
    """Return the feasible recipe closest to the original recipe.

    ``ingredient_bounds`` must align one-to-one with recipe ingredients:

        [
            {
                "min_weight_g": ...,
                "max_weight_g": ...,
            },
            ...
        ]

    Bounds are mandatory. This module never invents safe serving ranges.

    Nutrient targets use the existing PureFyul nutrient keys:

        minimums={"protein": 30, "fiber": 7}
        maximums={"calories": 400, "sugar": 20}

    Sodium follows the existing PureFyul sodium contract.
    """

    if not isinstance(recipe_result, dict):
        raise SmoothieTuningInputError(
            "recipe_result must be a dictionary"
        )

    ingredients = recipe_result.get("ingredients")

    if not isinstance(ingredients, list) or not ingredients:
        raise SmoothieTuningInputError(
            "recipe_result.ingredients must be a non-empty list"
        )

    if not isinstance(ingredient_bounds, (list, tuple)):
        raise SmoothieTuningInputError(
            "ingredient_bounds must be a list or tuple"
        )

    if len(ingredient_bounds) != len(ingredients):
        raise SmoothieTuningInputError(
            "ingredient_bounds must contain one entry per ingredient"
        )

    if not isinstance(preserve_total_weight, bool):
        raise SmoothieTuningInputError(
            "preserve_total_weight must be a boolean"
        )

    normalized_minimums = _normalize_targets(
        minimums,
        "minimums",
    )
    normalized_maximums = _normalize_targets(
        maximums,
        "maximums",
    )

    if not normalized_minimums and not normalized_maximums:
        raise SmoothieTuningInputError(
            "at least one nutrient target is required"
        )

    for nutrient in (
        normalized_minimums.keys()
        & normalized_maximums.keys()
    ):
        if (
            normalized_minimums[nutrient]
            > normalized_maximums[nutrient]
        ):
            raise SmoothieTuningInputError(
                f"minimums.{nutrient} cannot exceed "
                f"maximums.{nutrient}"
            )

    original_weights = []
    nutrition_rows = []
    solver_weight_bounds = []

    for index, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            raise SmoothieTuningInputError(
                f"recipe_result.ingredients[{index}] "
                "must be a dictionary"
            )

        original_weight = _require_number(
            ingredient.get("weight_g"),
            f"recipe_result.ingredients[{index}].weight_g",
            positive=True,
        )

        nutrition = ingredient.get("nutrition_per_100g")

        if not isinstance(nutrition, dict):
            raise SmoothieTuningInputError(
                f"recipe_result.ingredients[{index}]"
                ".nutrition_per_100g must be a dictionary"
            )

        normalized_nutrition = {}

        for nutrient in NUTRIENT_KEYS:
            if nutrient not in nutrition:
                raise SmoothieTuningInputError(
                    f"recipe_result.ingredients[{index}]"
                    f".nutrition_per_100g missing '{nutrient}'"
                )

            normalized_nutrition[nutrient] = _require_number(
                nutrition[nutrient],
                f"recipe_result.ingredients[{index}]"
                f".nutrition_per_100g.{nutrient}",
            )

        bound = ingredient_bounds[index]

        if not isinstance(bound, dict):
            raise SmoothieTuningInputError(
                f"ingredient_bounds[{index}] must be a dictionary"
            )

        min_weight = _require_number(
            bound.get("min_weight_g"),
            f"ingredient_bounds[{index}].min_weight_g",
            positive=True,
        )
        max_weight = _require_number(
            bound.get("max_weight_g"),
            f"ingredient_bounds[{index}].max_weight_g",
            positive=True,
        )

        if min_weight > max_weight:
            raise SmoothieTuningInputError(
                f"ingredient_bounds[{index}].min_weight_g "
                "cannot exceed max_weight_g"
            )

        if not (
            min_weight <= original_weight <= max_weight
        ):
            raise SmoothieTuningInputError(
                f"ingredient_bounds[{index}] must include "
                "the original ingredient weight"
            )

        original_weights.append(original_weight)
        nutrition_rows.append(normalized_nutrition)
        solver_weight_bounds.append((min_weight, max_weight))

    ingredient_count = len(ingredients)
    variable_count = ingredient_count * 2

    # Variables:
    # x[0:n]   = tuned ingredient weights
    # x[n:2n]  = absolute deviations from original weights
    #
    # Objective minimizes proportional deviation so an ingredient's
    # original scale is respected.
    objective = [0.0] * variable_count

    for index, original_weight in enumerate(original_weights):
        objective[ingredient_count + index] = (
            1.0 / original_weight
        )

    a_ub = []
    b_ub = []

    # d_i >= |x_i - original_i|
    for index, original_weight in enumerate(original_weights):
        row = [0.0] * variable_count
        row[index] = 1.0
        row[ingredient_count + index] = -1.0
        a_ub.append(row)
        b_ub.append(original_weight)

        row = [0.0] * variable_count
        row[index] = -1.0
        row[ingredient_count + index] = -1.0
        a_ub.append(row)
        b_ub.append(-original_weight)

    # Nutrient minimums.
    for nutrient, target in normalized_minimums.items():
        row = [0.0] * variable_count

        for index, nutrition in enumerate(nutrition_rows):
            row[index] = -(nutrition[nutrient] / 100.0)

        a_ub.append(row)
        b_ub.append(-target)

    # Nutrient maximums.
    for nutrient, target in normalized_maximums.items():
        row = [0.0] * variable_count

        for index, nutrition in enumerate(nutrition_rows):
            row[index] = nutrition[nutrient] / 100.0

        a_ub.append(row)
        b_ub.append(target)

    variable_bounds = (
        solver_weight_bounds
        + [(0.0, None)] * ingredient_count
    )

    a_eq = None
    b_eq = None

    if preserve_total_weight:
        original_total_weight = sum(original_weights)

        total_weight_row = [0.0] * variable_count
        for index in range(ingredient_count):
            total_weight_row[index] = 1.0

        a_eq = [total_weight_row]
        b_eq = [original_total_weight]

    solution = linprog(
        c=objective,
        A_ub=a_ub,
        b_ub=b_ub,
        A_eq=a_eq,
        b_eq=b_eq,
        bounds=variable_bounds,
        method="highs",
    )

    if solution.status == 2:
        raise SmoothieTuningInfeasibleError(
            "no recipe within the supplied ingredient bounds "
            "can satisfy all nutrient targets"
        )

    if not solution.success:
        raise SmoothieTuningSolverError(
            f"tuning solver failed: {solution.message}"
        )

    tuned_weights = [
        float(value)
        for value in solution.x[:ingredient_count]
    ]

    before_batch_inputs = []
    after_batch_inputs = []
    tuned_ingredients = []

    for index, ingredient in enumerate(ingredients):
        before_weight = original_weights[index]
        after_weight = tuned_weights[index]
        nutrition = nutrition_rows[index]

        before_batch_inputs.append(
            {
                "weight_g": before_weight,
                "nutrition_per_100g": nutrition,
            }
        )
        after_batch_inputs.append(
            {
                "weight_g": after_weight,
                "nutrition_per_100g": nutrition,
            }
        )

        tuned_ingredients.append(
            {
                "ingredient": ingredient.get("ingredient"),
                "nutrition_lookup_name": ingredient.get(
                    "nutrition_lookup_name"
                ),
                "before_weight_g": before_weight,
                "after_weight_g": after_weight,
                "delta_weight_g": after_weight - before_weight,
                "nutrition_per_100g": nutrition,
            }
        )

    before_batch = calculate_batch_nutrition(
        before_batch_inputs
    )
    after_batch = calculate_batch_nutrition(
        after_batch_inputs
    )

    after_nutrition = after_batch["nutrition"]

    # Verify the deterministic result after solving rather than trusting
    # only the solver's internal arithmetic.
    for nutrient, target in normalized_minimums.items():
        tolerance = 1e-7 * max(1.0, abs(target))

        if after_nutrition[nutrient] + tolerance < target:
            raise SmoothieTuningSolverError(
                f"solver result failed minimum target '{nutrient}'"
            )

    for nutrient, target in normalized_maximums.items():
        tolerance = 1e-7 * max(1.0, abs(target))

        if after_nutrition[nutrient] - tolerance > target:
            raise SmoothieTuningSolverError(
                f"solver result failed maximum target '{nutrient}'"
            )

    return {
        "ingredients": tuned_ingredients,
        "targets": {
            "minimums": normalized_minimums,
            "maximums": normalized_maximums,
        },
        "constraints": {
            "preserve_total_weight": preserve_total_weight,
        },
        "before": {
            "weight_g": before_batch["batch_weight_g"],
            "nutrition": before_batch["nutrition"],
            "energy_density_kcal_per_g": calculate_energy_density(
                batch_calories=before_batch["nutrition"]["calories"],
                batch_weight_g=before_batch["batch_weight_g"],
            ),
        },
        "after": {
            "weight_g": after_batch["batch_weight_g"],
            "nutrition": after_batch["nutrition"],
            "energy_density_kcal_per_g": calculate_energy_density(
                batch_calories=after_batch["nutrition"]["calories"],
                batch_weight_g=after_batch["batch_weight_g"],
            ),
        },
    }
