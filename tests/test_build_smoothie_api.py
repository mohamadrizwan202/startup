import starter_recipe
import startup_recovered as app_module

from recipe_calculator import RecipeCalculationError
from starter_recipe import (
    StarterRecipeInputError,
    StarterRecipeUnavailableError,
)


def _client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_build_smoothie_is_public_and_returns_bridge_result(monkeypatch):
    captured = {}

    expected_recipe = {
        "ingredients": [
            {
                "id": "mango",
                "display_name": "Mango",
                "amount": 100.0,
                "unit": "g",
            }
        ],
        "batch": {
            "weight_g": 100.0,
            "nutrition": {
                "calories": 60.0,
                "protein": 1.0,
                "carbs": 15.0,
                "fat": 0.4,
                "fiber": 1.6,
                "sugar": 14.0,
                "sodium": 1.0,
            },
        },
        "portion": None,
    }

    def fake_build(ids):
        captured["ids"] = ids
        return expected_recipe

    monkeypatch.setattr(
        starter_recipe,
        "build_starter_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": [
                "mango",
            ]
        },
    )

    assert response.status_code == 200
    assert captured["ids"] == ["mango"]
    assert response.get_json() == {
        "success": True,
        "recipe": expected_recipe,
    }


def test_build_smoothie_requires_json_object():
    response = _client().post(
        "/api/build-smoothie",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_build_smoothie_rejects_fields_outside_contract():
    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": ["mango"],
            "age": 31,
            "health_goal": "energy",
        },
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["error"] == "invalid_request"
    assert body["fields"] == [
        "age",
        "health_goal",
    ]


def test_build_smoothie_maps_bridge_input_error_to_400(monkeypatch):
    def fake_build(_ids):
        raise StarterRecipeInputError(
            "unsupported mobile ingredient id: 'banana'"
        )

    monkeypatch.setattr(
        starter_recipe,
        "build_starter_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": ["banana"],
        },
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["error"] == "invalid_request"
    assert "banana" in body["message"]


def test_build_smoothie_reports_oat_milk_as_unavailable(monkeypatch):
    def fake_build(_ids):
        raise StarterRecipeUnavailableError(
            "starter recipe is unavailable for "
            "'oat-milk': mass_unresolved",
            reason="mass_unresolved",
            ingredient_id="oat-milk",
        )

    monkeypatch.setattr(
        starter_recipe,
        "build_starter_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": ["oat-milk"],
        },
    )

    assert response.status_code == 422

    body = response.get_json()

    assert body["error"] == "build_unavailable"
    assert body["reason"] == "mass_unresolved"
    assert body["ingredient_id"] == "oat-milk"


def test_build_smoothie_maps_missing_nutrition_to_422(monkeypatch):
    def fake_build(_ids):
        raise RecipeCalculationError(
            "exact nutrition facts not found"
        )

    monkeypatch.setattr(
        starter_recipe,
        "build_starter_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": ["mango"],
        },
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "build_unavailable",
        "reason": "nutrition_unavailable",
    }


def test_build_smoothie_does_not_expose_unexpected_failure(monkeypatch):
    def fake_build(_ids):
        raise RuntimeError("internal secret")

    monkeypatch.setattr(
        starter_recipe,
        "build_starter_recipe",
        fake_build,
    )

    response = _client().post(
        "/api/build-smoothie",
        json={
            "ingredient_ids": ["mango"],
        },
    )

    assert response.status_code == 500

    body = response.get_json()

    assert body == {
        "error": "build_failed",
    }
    assert "secret" not in response.get_data(as_text=True)
