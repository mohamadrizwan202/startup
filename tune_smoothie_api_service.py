"""Application service for the Tune My Smoothie API.

This module translates API-shaped input into the already-proven
deterministic PureFyul calculation and tuning layers.

It contains no Flask, authentication, subscription, AI, EER, or UI logic.
"""

from __future__ import annotations

import math

import ingredient_tuning_rules_repository
from batch_nutrition import NUTRIENT_KEYS
from ingredient_tuning_policy import build_policy_tuning_bounds
from recipe_calculator import calculate_recipe
from smoothie_tuner import (
    calculate_feasible_nutrient_range,
    tune_recipe_to_exact_targets,
)


DEFAULT_RANGE_NUTRIENTS = tuple(NUTRIENT_KEYS)


class TuneSmoothieRequestError(ValueError):
    """Raised when an API-shaped tuning request is malformed."""


def _require_payload(payload) -> dict:
    if not isinstance(payload, dict):
        raise TuneSmoothieRequestError(
            "request body must be a JSON object"
        )
    return payload


def _require_ingredients(payload) -> list:
    ingredients = payload.get("ingredients")

    if not isinstance(ingredients, list) or not ingredients:
        raise TuneSmoothieRequestError(
            "ingredients must be a non-empty list"
        )

    return ingredients


def _normalize_adjustable_indices(
    value,
    *,
    ingredient_count: int,
) -> list[int]:
    if not isinstance(value, list):
        raise TuneSmoothieRequestError(
            "adjustable_indices must be a list"
        )

    if not value:
        raise TuneSmoothieRequestError(
            "adjustable_indices cannot be empty"
        )

    normalized = []

    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TuneSmoothieRequestError(
                "adjustable_indices must contain integer indices"
            )

        if item < 0 or item >= ingredient_count:
            raise TuneSmoothieRequestError(
                f"adjustable ingredient index out of range: {item}"
            )

        normalized.append(item)

    if len(set(normalized)) != len(normalized):
        raise TuneSmoothieRequestError(
            "adjustable_indices cannot contain duplicates"
        )

    return normalized


def _normalize_preserve_total_weight(payload) -> bool:
    value = payload.get("preserve_total_weight", True)

    if not isinstance(value, bool):
        raise TuneSmoothieRequestError(
            "preserve_total_weight must be a boolean"
        )

    return value


def _normalize_range_nutrients(value) -> list[str]:
    if value is None:
        return list(DEFAULT_RANGE_NUTRIENTS)

    if not isinstance(value, list) or not value:
        raise TuneSmoothieRequestError(
            "nutrients must be a non-empty list"
        )

    normalized = []

    for nutrient in value:
        if not isinstance(nutrient, str):
            raise TuneSmoothieRequestError(
                "nutrients must contain nutrient names"
            )

        if nutrient not in NUTRIENT_KEYS:
            raise TuneSmoothieRequestError(
                f"unsupported nutrient '{nutrient}'"
            )

        normalized.append(nutrient)

    if len(set(normalized)) != len(normalized):
        raise TuneSmoothieRequestError(
            "nutrients cannot contain duplicates"
        )

    return normalized


def _normalize_range_targets(value) -> dict[str, float]:
    if value is None:
        return {}

    if not isinstance(value, dict):
        raise TuneSmoothieRequestError(
            "targets must be a dictionary"
        )

    normalized = {}

    for nutrient, value in value.items():
        if nutrient not in NUTRIENT_KEYS:
            raise TuneSmoothieRequestError(
                f"unsupported nutrient '{nutrient}'"
            )

        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise TuneSmoothieRequestError(
                f"targets.{nutrient} must be a finite number"
            )

        numeric = float(value)

        if not math.isfinite(numeric):
            raise TuneSmoothieRequestError(
                f"targets.{nutrient} must be a finite number"
            )

        if numeric < 0:
            raise TuneSmoothieRequestError(
                f"targets.{nutrient} cannot be negative"
            )

        normalized[nutrient] = numeric

    return normalized


def _build_recipe_ingredient_response(
    recipe_result,
    *,
    adjustable_indices,
) -> list[dict]:
    adjustable = set(adjustable_indices)
    response = []

    for index, ingredient in enumerate(
        recipe_result["ingredients"]
    ):
        response.append(
            {
                "index": index,
                "ingredient": ingredient["ingredient"],
                "nutrition_lookup_name": ingredient[
                    "nutrition_lookup_name"
                ],
                "weight_g": ingredient["weight_g"],
                "mass_source": ingredient["mass_source"],
                "adjustable": index in adjustable,
            }
        )

    return response


def _build_reviewed_policy_bounds(
    *,
    recipe_result,
    adjustable_indices,
) -> list[dict]:
    """Load exact Tune rules and build fail-closed solver bounds."""

    tuning_rules = {}
    looked_up_names = set()

    for index in adjustable_indices:
        ingredient = recipe_result["ingredients"][index]
        lookup_name = ingredient.get("nutrition_lookup_name")

        if not isinstance(lookup_name, str) or not lookup_name:
            continue

        if lookup_name in looked_up_names:
            continue

        looked_up_names.add(lookup_name)

        rule = (
            ingredient_tuning_rules_repository
            .get_ingredient_tuning_rule_exact(lookup_name)
        )

        if rule is not None:
            tuning_rules[lookup_name] = rule

    return build_policy_tuning_bounds(
        recipe_result=recipe_result,
        adjustable_indices=adjustable_indices,
        tuning_rules=tuning_rules,
    )


def build_tune_ranges_response(payload) -> dict:
    """Calculate feasible tuning ranges for an existing recipe."""

    payload = _require_payload(payload)
    ingredients = _require_ingredients(payload)

    adjustable_indices = _normalize_adjustable_indices(
        payload.get("adjustable_indices"),
        ingredient_count=len(ingredients),
    )

    preserve_total_weight = _normalize_preserve_total_weight(
        payload
    )

    nutrients = _normalize_range_nutrients(
        payload.get("nutrients")
    )

    targets = _normalize_range_targets(
        payload.get("targets")
    )

    recipe_result = calculate_recipe(ingredients)

    bounds = _build_reviewed_policy_bounds(
        recipe_result=recipe_result,
        adjustable_indices=adjustable_indices,
    )

    ranges = {}

    for nutrient in nutrients:
        conditional_targets = {
            target_nutrient: target
            for target_nutrient, target in targets.items()
            if target_nutrient != nutrient
        }

        ranges[nutrient] = calculate_feasible_nutrient_range(
            recipe_result=recipe_result,
            ingredient_bounds=bounds,
            nutrient=nutrient,
            preserve_total_weight=preserve_total_weight,
            exact_targets=conditional_targets,
        )

    return {
        "ingredients": _build_recipe_ingredient_response(
            recipe_result,
            adjustable_indices=adjustable_indices,
        ),
        "batch": recipe_result["batch"],
        "ranges": ranges,
        "constraints": {
            "preserve_total_weight": preserve_total_weight,
        },
    }


def build_tune_response(payload) -> dict:
    """Tune a recipe to exact user-selected nutrient targets."""

    payload = _require_payload(payload)
    ingredients = _require_ingredients(payload)

    adjustable_indices = _normalize_adjustable_indices(
        payload.get("adjustable_indices"),
        ingredient_count=len(ingredients),
    )

    preserve_total_weight = _normalize_preserve_total_weight(
        payload
    )

    targets = payload.get("targets")

    if not isinstance(targets, dict) or not targets:
        raise TuneSmoothieRequestError(
            "targets must be a non-empty dictionary"
        )

    recipe_result = calculate_recipe(ingredients)

    bounds = _build_reviewed_policy_bounds(
        recipe_result=recipe_result,
        adjustable_indices=adjustable_indices,
    )

    tuned = tune_recipe_to_exact_targets(
        recipe_result=recipe_result,
        adjustable_indices=adjustable_indices,
        targets=targets,
        preserve_total_weight=preserve_total_weight,
        ingredient_bounds=bounds,
    )

    return {
        "ingredients": [
            {
                "index": index,
                "ingredient": ingredient["ingredient"],
                "nutrition_lookup_name": ingredient[
                    "nutrition_lookup_name"
                ],
                "before_weight_g": ingredient[
                    "before_weight_g"
                ],
                "after_weight_g": ingredient[
                    "after_weight_g"
                ],
                "delta_weight_g": ingredient[
                    "delta_weight_g"
                ],
            }
            for index, ingredient in enumerate(
                tuned["ingredients"]
            )
        ],
        "before": tuned["before"],
        "after": tuned["after"],
        "requested_targets": tuned["requested_targets"],
        "feasible_ranges": tuned["feasible_ranges"],
        "constraints": tuned["constraints"],
    }
