"""Constrained Haiku selection for reviewed health-goal recipes."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from types import SimpleNamespace

from goal_preset_recipe import (
    GoalPresetRecipeInputError,
    get_reviewed_goal_recipe_candidates,
    get_supported_timing_slugs,
)


class AIGoalRecipeSelectionError(RuntimeError):
    """Raised when Haiku does not return one exact reviewed candidate."""


_ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"
_AI_REQUEST_TIMEOUT_SECONDS = 2.5


def _request_anthropic_message_text(*, payload: dict) -> str:
    """Make one bounded Anthropic Messages API request without the SDK."""
    api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()

    if not api_key:
        raise AIGoalRecipeSelectionError(
            "AI ingredient selection is unavailable"
        )

    request = urllib.request.Request(
        _ANTHROPIC_MESSAGES_URL,
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
            "Anthropic-Version": _ANTHROPIC_VERSION,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=_AI_REQUEST_TIMEOUT_SECONDS,
        ) as response:
            raw_response = response.read()
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise AIGoalRecipeSelectionError(
            "AI ingredient selection request failed"
        ) from exc

    try:
        response_payload = json.loads(
            raw_response.decode("utf-8")
        )
    except (TypeError, UnicodeDecodeError, ValueError) as exc:
        raise AIGoalRecipeSelectionError(
            "AI selection response was invalid"
        ) from exc

    content = (
        response_payload.get("content")
        if isinstance(response_payload, dict)
        else None
    )

    if (
        not isinstance(content, list)
        or not content
        or not isinstance(content[0], dict)
        or not isinstance(content[0].get("text"), str)
    ):
        raise AIGoalRecipeSelectionError(
            "AI selection response was invalid"
        )

    return content[0]["text"]


class _BoundedMessages:
    """Minimal SDK-free Messages adapter for the Build flow."""

    def create(self, **payload):
        raw_text = _request_anthropic_message_text(
            payload=payload
        )
        return SimpleNamespace(
            content=[SimpleNamespace(text=raw_text)]
        )


class _BoundedMessagesClient:
    """Client shape used when Build has no injected SDK client."""

    def __init__(self):
        self.messages = _BoundedMessages()


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
    client=None,
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
        client = _BoundedMessagesClient()

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
        "a JSON object with exactly this key: variant.\n\n"
        f"Health goal: {goal}\n"
        f"Timing: {normalized_timing}\n"
        "Allowed candidates:\n"
        + json.dumps(prompt_candidates, ensure_ascii=True)
    )

    try:
        ai_client = client

        if hasattr(client, "with_options"):
            ai_client = client.with_options(
                timeout=_AI_REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )

        response = ai_client.messages.create(
            model=os.getenv(
                "ANTHROPIC_GOAL_RECIPE_MODEL",
                "claude-haiku-4-5-20251001",
            ),
            max_tokens=32,
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

    if set(parsed) != {"variant"}:
        raise AIGoalRecipeSelectionError(
            "AI selection returned unsupported fields"
        )

    variant = parsed.get("variant")

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

    return {
        "variant": variant,
        "ingredient_ids": list(selected["ingredient_ids"]),
        "selection_source": "haiku_reviewed_candidate",
    }
