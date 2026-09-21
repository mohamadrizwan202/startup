import goal_preset_recipe
import startup_recovered as app_module

from goal_preset_recipe import GoalPresetRecipeInputError
from recipe_calculator import RecipeCalculationError
from recipe_mass import RecipeMassResolutionError


def _client():
    app_module.app.config["TESTING"] = True
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
