import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

_requests_stub = ModuleType("requests")
_requests_stub.__getattr__ = lambda _name: MagicMock()
sys.modules.setdefault("requests", _requests_stub)

import ai_goal_recipe_selector
import goal_preset_recipe
import startup_recovered as app_module

from goal_preset_recipe import GoalPresetRecipeInputError
from recipe_calculator import RecipeCalculationError
from recipe_mass import RecipeMassResolutionError


def _client(*, ai_enabled=False):
    app_module.app.config["TESTING"] = True
    app_module.app.config["AI_GOAL_RECIPE_ENABLED"] = ai_enabled
    return app_module.app.test_client()


def test_build_goal_preset_is_public_and_returns_recipe(monkeypatch):
    captured = {}

    expected_recipe = {
        "goal": "skin-glow",
        "timing": "breakfast",
        "variant": "a",
        "target_weight_g": 400.0,
        "ingredients": [],
        "batch": {
            "weight_g": 400.0,
            "nutrition": {},
        },
    }

    def fake_build(*, goal, timing, variant):
        captured["goal"] = goal
        captured["timing"] = timing
        captured["variant"] = variant
        return expected_recipe

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "goal": "skin-glow",
        "timing": "breakfast",
        "variant": "a",
    }
    assert response.get_json() == {
        "success": True,
        "recipe": expected_recipe,
    }


def test_build_goal_preset_requires_json_object():
    response = _client().post(
        "/api/build-goal-preset",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_build_goal_preset_rejects_fields_outside_contract():
    response = _client().post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "age": 31,
            "sex": "male",
        },
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["error"] == "invalid_request"
    assert body["fields"] == [
        "age",
        "sex",
    ]


def test_build_goal_preset_maps_input_error_to_400(monkeypatch):
    def fake_build(**_kwargs):
        raise GoalPresetRecipeInputError(
            "unsupported preset timing: 'dinner'"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "dinner",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_build_goal_preset_maps_mass_failure_to_422(monkeypatch):
    def fake_build(**_kwargs):
        raise RecipeMassResolutionError(
            "mass conversion is unresolved"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
        },
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "build_unavailable",
        "reason": "mass_unresolved",
    }


def test_build_goal_preset_maps_missing_nutrition_to_422(monkeypatch):
    def fake_build(**_kwargs):
        raise RecipeCalculationError(
            "exact nutrition facts not found"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
        },
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "build_unavailable",
        "reason": "nutrition_unavailable",
    }


def test_build_goal_preset_uses_ai_and_avoids_recent_variant(
    monkeypatch,
):
    selections = []
    built_variants = []

    def fake_select(
        *,
        client,
        goal,
        timing,
        excluded_variants,
    ):
        selections.append({
            "goal": goal,
            "timing": timing,
            "excluded_variants": tuple(excluded_variants),
        })
        variant = "b" if len(selections) == 1 else "c"
        return {
            "variant": variant,
            "ingredient_ids": ["reviewed"],
            "selection_source": "haiku_reviewed_candidate",
        }

    def fake_build(*, goal, timing, variant):
        built_variants.append(variant)
        return {
            "goal": goal,
            "timing": timing,
            "variant": variant,
            "ingredients": [],
            "batch": {
                "weight_g": 400.0,
                "nutrition": {},
            },
            "preset_contract": {},
        }

    monkeypatch.setattr(
        ai_goal_recipe_selector,
        "select_reviewed_goal_recipe",
        fake_select,
    )
    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    client = _client(ai_enabled=True)

    first = client.post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "variant": "a",
        },
    )
    second = client.post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "variant": "a",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert built_variants == ["b", "c"]
    assert selections == [
        {
            "goal": "skin-glow",
            "timing": "breakfast",
            "excluded_variants": (),
        },
        {
            "goal": "skin-glow",
            "timing": "breakfast",
            "excluded_variants": ("b",),
        },
    ]
    assert (
        first.get_json()["recipe"]["preset_contract"][
            "selection_source"
        ]
        == "haiku_reviewed_candidate"
    )


def test_build_goal_preset_uses_reviewed_fallback_when_ai_fails(
    monkeypatch,
):
    captured = {}

    def fake_select(**_kwargs):
        raise ai_goal_recipe_selector.AIGoalRecipeSelectionError(
            "invalid AI output"
        )

    def fake_build(*, goal, timing, variant):
        captured["variant"] = variant
        return {
            "goal": goal,
            "timing": timing,
            "variant": variant,
            "ingredients": [],
            "batch": {
                "weight_g": 400.0,
                "nutrition": {},
            },
            "preset_contract": {},
        }

    monkeypatch.setattr(
        ai_goal_recipe_selector,
        "select_reviewed_goal_recipe",
        fake_select,
    )
    monkeypatch.setattr(
        goal_preset_recipe,
        "build_goal_preset_recipe",
        fake_build,
    )

    response = _client(ai_enabled=True).post(
        "/api/build-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "variant": "c",
        },
    )

    assert response.status_code == 200
    assert captured["variant"] == "c"
    assert (
        response.get_json()["recipe"]["preset_contract"][
            "selection_source"
        ]
        == "reviewed_preset_fallback"
    )


def test_build_goal_preset_template_has_client_deadline():
    template = (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "index.html"
    ).read_text(encoding="utf-8")

    start = template.index("async function buildPresetVariant(")
    end = template.index("if (buildButton)", start)
    flow = template[start:end]

    assert "new AbortController()" in flow
    assert "buildRequestController.abort()" in flow
    assert "4000" in flow
    assert "signal: buildRequestController.signal" in flow
    assert "window.clearTimeout(buildRequestTimeout)" in flow
    assert "This is taking longer than expected." in flow
