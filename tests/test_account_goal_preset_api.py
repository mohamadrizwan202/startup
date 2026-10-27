import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

for key in (
    "DATABASE_URL",
    "DATABASE_URL_RUNTIME",
    "DATABASE_URL_MIGRATE",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_WEBHOOK_SECRET",
    "STRIPE_PRO_MONTHLY_PRICE_ID",
    "REDIS_URL",
    "RENDER",
):
    os.environ[key] = ""

os.environ["ANTHROPIC_API_KEY"] = "test-only"
os.environ["DB_USE_RUNTIME_ROLE"] = "0"
os.environ["RUN_SCHEMA"] = "0"
os.environ["PF_DISABLE_RATELIMIT"] = "1"
os.environ["ENABLE_INTERNAL_ROUTES"] = "0"
os.environ["SECRET_KEY"] = "account-goal-preset-tests"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402
import goal_preset_recipe  # noqa: E402
from account_goal_recipe_profiles import ACCOUNT_GOAL_RECIPE_PROFILES  # noqa: E402

_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "account_goal_preset.sqlite3"
db.USE_POSTGRES = False

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 8121,
    "email": "account-goal-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}

_VALID_GOALS = tuple(ACCOUNT_GOAL_RECIPE_PROFILES)[:6]
_ACCOUNT_ONLY_CATEGORY = "Anemia Prevention"
_ACCOUNT_ONLY_SLUG = "iron-support"


def _create_schema():
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        for table in (
            "user_health_goal_preferences",
            "ingredient_categories",
            "personalized_smoothie_generations",
            "subscriptions",
            "person_ingredient_preferences",
            "person_preferences",
            "persons",
        ):
            conn.execute(f"DROP TABLE IF EXISTS {table}")

        conn.execute(
            """
            CREATE TABLE ingredient_categories (
                category TEXT NOT NULL,
                ingredient TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO ingredient_categories (category, ingredient)
            VALUES (?, '')
            """,
            [(category_value,) for category_value in ACCOUNT_GOAL_RECIPE_PROFILES],
        )

        conn.execute(
            """
            CREATE TABLE user_health_goal_preferences (
                user_id INTEGER NOT NULL,
                category_value TEXT NOT NULL,
                display_order INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE personalized_smoothie_generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                person_id INTEGER,
                goal_slug TEXT NOT NULL,
                timing_slug TEXT NOT NULL,
                access_type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                personalization_id TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _save_goals(values, *, user_id=TEST_USER["id"]):
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(
            """
            DELETE FROM user_health_goal_preferences
            WHERE user_id = ?
            """,
            (user_id,),
        )
        conn.executemany(
            """
            INSERT INTO user_health_goal_preferences (
                user_id,
                category_value,
                display_order
            )
            VALUES (?, ?, ?)
            """,
            [
                (user_id, value, display_order)
                for display_order, value in enumerate(values, start=1)
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _ledger_count():
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM personalized_smoothie_generations"
        ).fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    _create_schema()

    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
        SECRET_KEY="account-goal-preset-tests",
    )

    monkeypatch.setattr(
        appmod,
        "get_user_by_id",
        lambda user_id: (
            TEST_USER
            if int(user_id) == TEST_USER["id"]
            else None
        ),
    )

    with appmod.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["_user_id"] = str(TEST_USER["id"])
            session["_fresh"] = True
        yield test_client


def test_account_goal_preset_rejects_unauthenticated_request():
    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
    )

    with appmod.app.test_client() as unauthenticated_client:
        response = unauthenticated_client.post(
            "/api/account-goal-preset",
            json={
                "category_value": _ACCOUNT_ONLY_CATEGORY,
                "timing": "breakfast",
            },
            follow_redirects=False,
        )

    assert response.status_code in {302, 401}


def test_account_goal_preset_rejects_partial_saved_goals(
    client,
    monkeypatch,
):
    _save_goals(_VALID_GOALS[:5])

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_account_goal_preset_recipe",
        lambda **_kwargs: pytest.fail(
            "builder must not run for partial saved goals"
        ),
    )

    response = client.post(
        "/api/account-goal-preset",
        json={
            "category_value": _ACCOUNT_ONLY_CATEGORY,
            "timing": "breakfast",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "account_health_goals_invalid"
    assert _ledger_count() == 0


def test_account_goal_preset_rejects_unowned_and_unknown_categories(
    client,
    monkeypatch,
):
    _save_goals(_VALID_GOALS)

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_account_goal_preset_recipe",
        lambda **_kwargs: pytest.fail(
            "builder must not run for denied categories"
        ),
    )

    unowned_category = next(
        category_value
        for category_value in ACCOUNT_GOAL_RECIPE_PROFILES
        if category_value not in _VALID_GOALS
    )
    unowned_response = client.post(
        "/api/account-goal-preset",
        json={
            "category_value": unowned_category,
            "timing": "breakfast",
        },
    )
    unknown_response = client.post(
        "/api/account-goal-preset",
        json={
            "category_value": "not-a-real-category",
            "timing": "breakfast",
        },
    )

    assert unowned_response.status_code == 403
    assert unowned_response.get_json()["error"] == (
        "account_health_goal_not_saved"
    )
    assert unknown_response.status_code == 400
    assert unknown_response.get_json()["error"] == "invalid_request"
    assert _ledger_count() == 0


def test_authorized_account_only_goal_builds_without_credit_write(
    client,
    monkeypatch,
):
    _save_goals(_VALID_GOALS)
    captured = {}

    def fake_build(*, category_value, timing):
        captured["category_value"] = category_value
        captured["timing"] = timing
        return {
            "goal": _ACCOUNT_ONLY_SLUG,
            "timing": timing,
            "variant": "a",
            "ingredients": [],
            "batch": {"weight_g": 400.0, "nutrition": {}},
            "preset_contract": {},
        }

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_account_goal_preset_recipe",
        fake_build,
    )

    response = client.post(
        "/api/account-goal-preset",
        json={
            "category_value": _ACCOUNT_ONLY_CATEGORY,
            "timing": "breakfast",
        },
    )

    assert response.status_code == 200
    assert captured == {
        "category_value": _ACCOUNT_ONLY_CATEGORY,
        "timing": "breakfast",
    }
    assert response.get_json()["recipe"]["preset_contract"][
        "selection_source"
    ] == "account_health_goal_preset"
    assert _ledger_count() == 0


def test_account_only_options_and_personalization_are_owner_guarded(
    client,
    monkeypatch,
):
    _save_goals(_VALID_GOALS)

    authorized_options = client.get(
        "/api/personalization/ingredient-options"
        f"?goal={_ACCOUNT_ONLY_SLUG}"
    )
    assert authorized_options.status_code == 200
    assert authorized_options.get_json()["goal"] == _ACCOUNT_ONLY_SLUG

    unowned_goals = tuple(
        category_value
        for category_value in ACCOUNT_GOAL_RECIPE_PROFILES
        if category_value != _ACCOUNT_ONLY_CATEGORY
    )[:6]
    _save_goals(unowned_goals)

    denied_options = client.get(
        "/api/personalization/ingredient-options"
        f"?goal={_ACCOUNT_ONLY_SLUG}"
    )
    assert denied_options.status_code == 403
    assert denied_options.get_json()["error"] == (
        "account_health_goal_not_saved"
    )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_personalized_goal_preset_recipe",
        lambda **_kwargs: pytest.fail(
            "personalized builder must not run for an unowned account goal"
        ),
    )

    denied_personalization = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": _ACCOUNT_ONLY_SLUG,
            "timing": "breakfast",
            "current_variant": "a",
            "ingredients": [
                {"id": "pea-milk", "amount": 120},
                {"id": "orange", "amount": 80},
                {"id": "spinach", "amount": 30},
            ],
        },
    )

    assert denied_personalization.status_code == 403
    assert denied_personalization.get_json()["error"] == (
        "account_health_goal_not_saved"
    )
    assert _ledger_count() == 0


def test_signed_in_valid_six_renders_only_saved_goal_cards(
    client,
    monkeypatch,
):
    _save_goals(_VALID_GOALS)
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda *_args, **_kwargs: "free",
    )

    response = client.get("/app")

    assert response.status_code == 200
    html = response.get_data(as_text=True)

    saved_markers = [
        f'data-account-health-goal="{category_value}"'
        for category_value in _VALID_GOALS
    ]
    assert html.count("data-account-health-goal=") == 6
    assert [html.index(marker) for marker in saved_markers] == sorted(
        html.index(marker)
        for marker in saved_markers
    )

    for category_value in _VALID_GOALS:
        assert (
            appmod._ACCOUNT_HEALTH_GOAL_LABELS[category_value]
            in html
        )

    for public_goal in (
        "skin-glow",
        "gut-health",
        "brain-focus",
        "heart-support",
        "energy-stamina",
        "muscle-health",
    ):
        assert f'data-goal="{public_goal}"' not in html


def test_guest_and_partial_saved_goals_render_default_cards(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda *_args, **_kwargs: "free",
    )
    _save_goals(_VALID_GOALS[:5])

    partial_response = client.get("/app")
    assert partial_response.status_code == 200
    partial_html = partial_response.get_data(as_text=True)

    with appmod.app.test_client() as guest_client:
        guest_response = guest_client.get("/app")

    assert guest_response.status_code == 200
    guest_html = guest_response.get_data(as_text=True)

    for html in (partial_html, guest_html):
        assert "data-account-health-goal=" not in html
        for public_goal in (
            "skin-glow",
            "gut-health",
            "brain-focus",
            "heart-support",
            "energy-stamina",
            "muscle-health",
        ):
            assert f'data-goal="{public_goal}"' in html
