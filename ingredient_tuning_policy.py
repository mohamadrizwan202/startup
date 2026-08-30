"""Pure ingredient-bound policy for Tune My Smoothie.

This module does not query a database and does not define serving science.

It receives:
- an already-calculated recipe,
- ingredient indices the caller wants to make adjustable,
- reviewed tuning rules keyed by exact ``nutrition_lookup_name``.

It fails closed: an ingredient is adjustable only when an enabled,
approved rule exists and the current ingredient amount is already inside
that rule's allowed range. Otherwise the ingredient is locked at its
current weight.
"""

from __future__ import annotations

import math


class IngredientTuningPolicyError(ValueError):
    """Raised when the policy builder itself receives malformed input."""


def build_policy_tuning_bounds(
    *,
    recipe_result,
    adjustable_indices,
    tuning_rules,
) -> list[dict]:
    """Build solver bounds from reviewed ingredient tuning rules."""

    if not isinstance(recipe_result, dict):
        raise IngredientTuningPolicyError(
            "recipe_result must be a dictionary"
        )

    ingredients = recipe_result.get("ingredients")

    if not isinstance(ingredients, list) or not ingredients:
        raise IngredientTuningPolicyError(
            "recipe_result.ingredients must be a non-empty list"
        )

    if not isinstance(adjustable_indices, (list, tuple, set)):
        raise IngredientTuningPolicyError(
            "adjustable_indices must be a list, tuple, or set"
        )

    normalized_indices = []

    for value in adjustable_indices:
        if isinstance(value, bool) or not isinstance(value, int):
            raise IngredientTuningPolicyError(
                "adjustable_indices must contain integer indices"
            )

        if value < 0 or value >= len(ingredients):
            raise IngredientTuningPolicyError(
                f"adjustable ingredient index out of range: {value}"
            )

        normalized_indices.append(value)

    if not normalized_indices:
        raise IngredientTuningPolicyError(
            "at least one adjustable ingredient is required"
        )

    if len(set(normalized_indices)) != len(normalized_indices):
        raise IngredientTuningPolicyError(
            "adjustable_indices cannot contain duplicates"
        )

    if not isinstance(tuning_rules, dict):
        raise IngredientTuningPolicyError(
            "tuning_rules must be a dictionary"
        )

    adjustable = set(normalized_indices)
    bounds = []

    for index, ingredient in enumerate(ingredients):
        if not isinstance(ingredient, dict):
            raise IngredientTuningPolicyError(
                f"recipe_result.ingredients[{index}] "
                "must be a dictionary"
            )

        original_weight = _require_nonnegative_number(
            ingredient.get("weight_g"),
            f"recipe_result.ingredients[{index}].weight_g",
        )

        locked = {
            "min_weight_g": original_weight,
            "max_weight_g": original_weight,
        }

        if index not in adjustable:
            bounds.append(locked)
            continue

        lookup_name = ingredient.get("nutrition_lookup_name")

        if not isinstance(lookup_name, str) or not lookup_name:
            bounds.append(locked)
            continue

        rule = tuning_rules.get(lookup_name)

        if not isinstance(rule, dict):
            bounds.append(locked)
            continue

        if rule.get("enabled") is not True:
            bounds.append(locked)
            continue

        if rule.get("review_status") != "approved":
            bounds.append(locked)
            continue

        minimum = _optional_nonnegative_number(
            rule.get("min_weight_g")
        )
        maximum = _optional_nonnegative_number(
            rule.get("max_weight_g")
        )

        if minimum is None or maximum is None:
            bounds.append(locked)
            continue

        if minimum > maximum:
            bounds.append(locked)
            continue

        if original_weight < minimum or original_weight > maximum:
            bounds.append(locked)
            continue

        bounds.append(
            {
                "min_weight_g": minimum,
                "max_weight_g": maximum,
            }
        )

    return bounds


def _require_nonnegative_number(value, field_name: str) -> float:
    numeric = _optional_nonnegative_number(value)

    if numeric is None:
        raise IngredientTuningPolicyError(
            f"{field_name} must be a finite non-negative number"
        )

    return numeric


def _optional_nonnegative_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    numeric = float(value)

    if not math.isfinite(numeric) or numeric < 0:
        return None

    return numeric
