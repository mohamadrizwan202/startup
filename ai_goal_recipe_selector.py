"""Constrained Haiku selection for reviewed health-goal recipes."""

from __future__ import annotations

import json
import os
import re

from goal_preset_recipe import (
    GoalPresetRecipeInputError,
    get_reviewed_goal_recipe_candidates,
    get_supported_timing_slugs,
)


class AIGoalRecipeSelectionError(RuntimeError):
    """Raised when Haiku does not return one exact reviewed candidate."""


def _normalize_timing(value) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GoalPresetRecipeInputError(
            "timing must be a non-empty string"
        )

    normalized = value.strip().lower()

    if normalized not in get_supported_timing_slugs():
        raise GoalPresetRecipeInputError(
            f"unsupported preset timing: '{normalized}'"
        )

    return normalized


def _parse_json_object(raw_text) -> dict:
    if not isinstance(raw_text, str):
        raise AIGoalRecipeSelectionError(
            "AI selection did not return text"
        )

    cleaned = raw_text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

    try:
        parsed = json.loads(cleaned)
    except (TypeError, ValueError) as exc:
        raise AIGoalRecipeSelectionError(
            "AI selection did not return valid JSON"
        ) from exc

    if not isinstance(parsed, dict):
        raise AIGoalRecipeSelectionError(
            "AI selection must be a JSON object"
        )

    return parsed


def select_reviewed_goal_recipe(
    *,
    client,
    goal,
    timing,
    excluded_variants=(),
) -> dict:
    """Ask Haiku to select one complete backend-reviewed recipe."""
    normalized_timing = _normalize_timing(timing)
    candidates = get_reviewed_goal_recipe_candidates(goal)
    candidate_by_variant = {
        candidate["variant"]: candidate
        for candidate in candidates
    }

    excluded = {
        value.strip().lower()
        for value in excluded_variants
        if isinstance(value, str) and value.strip()
    }
    eligible = [
        candidate
        for candidate in candidates
        if candidate["variant"] not in excluded
    ]

    if not eligible:
        eligible = list(candidates)

    if client is None:
        raise AIGoalRecipeSelectionError(
            "AI ingredient selection is unavailable"
        )

    prompt_candidates = [
        {
            "variant": candidate["variant"],
            "ingredient_ids": list(candidate["ingredient_ids"]),
        }
        for candidate in eligible
    ]

    prompt = (
        "Select exactly one complete smoothie candidate for the "
        "requested health goal and timing. The backend has already "
        "reviewed every listed candidate for this goal. Do not add, "
        "remove, reorder, rename, or combine ingredients. Return only "
        "a JSON object with exactly these keys: variant and "
        "ingredient_ids.\n\n"
        f"Health goal: {goal}\n"
        f"Timing: {normalized_timing}\n"
        "Allowed candidates:\n"
        + json.dumps(prompt_candidates, ensure_ascii=True)
    )

    try:
        ai_client = client

        if hasattr(client, "with_options"):
            ai_client = client.with_options(
                timeout=8.0,
                max_retries=0,
            )

        response = ai_client.messages.create(
            model=os.getenv(
                "ANTHROPIC_GOAL_RECIPE_MODEL",
                "claude-haiku-4-5-20251001",
            ),
            max_tokens=180,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )
        raw_text = response.content[0].text
    except Exception as exc:
        raise AIGoalRecipeSelectionError(
            "AI ingredient selection request failed"
        ) from exc

    parsed = _parse_json_object(raw_text)

    if set(parsed) != {"variant", "ingredient_ids"}:
        raise AIGoalRecipeSelectionError(
            "AI selection returned unsupported fields"
        )

    variant = parsed.get("variant")
    ingredient_ids = parsed.get("ingredient_ids")

    if not isinstance(variant, str):
        raise AIGoalRecipeSelectionError(
            "AI selection returned an invalid variant"
        )

    variant = variant.strip().lower()
    selected = candidate_by_variant.get(variant)

    if selected is None or selected not in eligible:
        raise AIGoalRecipeSelectionError(
            "AI selected a candidate outside the allowed goal set"
        )

    if (
        not isinstance(ingredient_ids, list)
        or ingredient_ids != list(selected["ingredient_ids"])
    ):
        raise AIGoalRecipeSelectionError(
            "AI ingredient IDs do not match the reviewed candidate"
        )

    return {
        "variant": variant,
        "ingredient_ids": list(selected["ingredient_ids"]),
        "selection_source": "haiku_reviewed_candidate",
    }
