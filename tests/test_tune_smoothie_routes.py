import pytest

import startup_recovered as app_module
import tune_smoothie_api_service
from recipe_calculator import RecipeCalculationError
from recipe_mass import RecipeMassResolutionError
from smoothie_tuner import (
    SmoothieTuningInfeasibleError,
    SmoothieTuningSolverError,
)
from tune_smoothie_api_service import TuneSmoothieRequestError


TEST_USER_ID = 123
TEST_TOKEN = "tune-test-session-token"


class _AuthCursor:
    def __init__(self, token=TEST_TOKEN):
        self.token = token

    def execute(self, _query, _params):
        return None

    def fetchone(self):
        return {
            "active_session_token": self.token,
        }

    def close(self):
        return None


class _AuthConnection:
    def __init__(self, token=TEST_TOKEN):
        self.token = token

    def cursor(self):
        return _AuthCursor(self.token)

    def close(self):
        return None


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(
        app_module.app.config,
        "TESTING",
        True,
    )
    monkeypatch.setitem(
        app_module.app.config,
        "WTF_CSRF_ENABLED",
        False,
    )

    monkeypatch.setattr(
        app_module,
        "get_conn",
        lambda: _AuthConnection(),
    )

    return app_module.app.test_client()


def _authenticate(client):
    with client.session_transaction() as sess:
        sess["user_id"] = TEST_USER_ID
        sess["active_session_token"] = TEST_TOKEN


def test_ranges_requires_authentication(client):
    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "auth_required",
    }


def test_invalidated_session_is_rejected(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_conn",
        lambda: _AuthConnection("different-token"),
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "session_invalidated",
    }


def test_free_user_is_blocked_before_tuning(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "free",
    )

    called = False

    def should_not_run(_payload):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_ranges_response",
        should_not_run,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 403

    body = response.get_json()

    assert body["error"] == "upgrade_required"
    assert body["feature"] == "tune_my_smoothie"
    assert called is False


def test_entitlement_lookup_fails_closed(
    client,
    monkeypatch,
):
    _authenticate(client)

    def fail_plan_lookup(_user_id):
        raise RuntimeError("subscription lookup failed")

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        fail_plan_lookup,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == (
        "entitlement_unavailable"
    )


def test_pro_user_can_get_ranges(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    expected = {
        "ranges": {
            "protein": {
                "current": 18.0,
                "minimum": 14.0,
                "maximum": 30.0,
            }
        }
    }

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_ranges_response",
        lambda _payload: expected,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={
            "ingredients": [],
        },
    )

    assert response.status_code == 200
    assert response.get_json() == expected


def test_pro_user_can_tune_recipe(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    expected = {
        "ingredients": [
            {
                "ingredient": "Greek Yogurt",
                "before_weight_g": 100.0,
                "after_weight_g": 150.0,
            }
        ],
        "after": {
            "weight_g": 200.0,
        },
    }

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_response",
        lambda _payload: expected,
    )

    response = client.post(
        "/api/tune-smoothie",
        json={
            "targets": {
                "protein": 15.0,
            }
        },
    )

    assert response.status_code == 200
    assert response.get_json() == expected


def test_invalid_json_returns_400(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    response = client.post(
        "/api/tune-smoothie",
        data="{not-valid-json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_request"


def test_service_request_error_returns_400(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    def fail_request(_payload):
        raise TuneSmoothieRequestError(
            "ingredients must be a non-empty list"
        )

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_ranges_response",
        fail_request,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["error"] == "invalid_request"
    assert "ingredients" in body["message"]


def test_unresolved_mass_returns_clear_422(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    def fail_mass(_payload):
        raise RecipeMassResolutionError(
            "mass conversion is unresolved for 'oat milk'"
        )

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_ranges_response",
        fail_mass,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 422

    body = response.get_json()

    assert body["error"] == "tune_unavailable"
    assert body["reason"] == "mass_unresolved"


def test_missing_nutrition_returns_clear_422(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    def fail_nutrition(_payload):
        raise RecipeCalculationError(
            "exact nutrition facts not found"
        )

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_ranges_response",
        fail_nutrition,
    )

    response = client.post(
        "/api/tune-smoothie/ranges",
        json={},
    )

    assert response.status_code == 422

    body = response.get_json()

    assert body["error"] == "tune_unavailable"
    assert body["reason"] == "nutrition_unavailable"


def test_infeasible_target_returns_clear_422(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    def fail_target(_payload):
        raise SmoothieTuningInfeasibleError(
            "target is above feasible maximum"
        )

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_response",
        fail_target,
    )

    response = client.post(
        "/api/tune-smoothie",
        json={},
    )

    assert response.status_code == 422

    body = response.get_json()

    assert body["error"] == "tune_unavailable"
    assert body["reason"] == "target_infeasible"


def test_solver_failure_does_not_leak_details(
    client,
    monkeypatch,
):
    _authenticate(client)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    def fail_solver(_payload):
        raise SmoothieTuningSolverError(
            "internal solver diagnostic"
        )

    monkeypatch.setattr(
        tune_smoothie_api_service,
        "build_tune_response",
        fail_solver,
    )

    response = client.post(
        "/api/tune-smoothie",
        json={},
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "tuning_failed",
    }
