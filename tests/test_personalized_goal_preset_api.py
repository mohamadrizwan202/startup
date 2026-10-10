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
os.environ["SECRET_KEY"] = "personalized-goal-preset-tests"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402
import goal_preset_recipe  # noqa: E402
import recipe_calculator  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()

db.DB_PATH = Path(_TEST_TMPDIR.name) / "personalized_goal_preset.sqlite3"
db.USE_POSTGRES = False

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 71,
    "email": "personalized-goal-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


def _create_schema():
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        conn.execute("DROP TABLE IF EXISTS person_ingredient_preferences")
        conn.execute("DROP TABLE IF EXISTS personalized_smoothie_generations")
        conn.execute("DROP TABLE IF EXISTS subscriptions")
        conn.execute("DROP TABLE IF EXISTS person_preferences")
        conn.execute("DROP TABLE IF EXISTS persons")

        conn.execute(
            """
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE person_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL UNIQUE,
                goal_slug TEXT NOT NULL,
                timing_slug TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE person_ingredient_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                ingredient_id TEXT NOT NULL,
                preference_type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    _create_schema()

    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="personalized-goal-preset-tests",
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
        with test_client.session_transaction() as sess:
            sess["_user_id"] = str(TEST_USER["id"])
            sess["_fresh"] = True

        yield test_client


def _fake_personalized_recipe(monkeypatch, captured):
    def fake_build(
        *,
        goal,
        timing,
        variant,
        ingredient_ids,
    ):
        captured["goal"] = goal
        captured["timing"] = timing
        captured["variant"] = variant
        captured["ingredient_ids"] = list(ingredient_ids)

        return {
            "goal": goal,
            "timing": timing,
            "variant": variant,
            "ingredients": [
                {"id": ingredient_id}
                for ingredient_id in ingredient_ids
            ],
            "batch": {"weight_g": 400, "nutrition": {}},
            "preset_contract": {"personalized": True},
        }

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_personalized_goal_preset_recipe",
        fake_build,
    )


def _ledger_count():
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        return conn.execute(
            "SELECT COUNT(*) FROM personalized_smoothie_generations"
        ).fetchone()[0]

    finally:
        conn.close()


def _create_person_without_preferences():
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (TEST_USER["id"], "Me", 1),
        )
        conn.commit()
        return cursor.lastrowid

    finally:
        conn.close()


def _create_person_with_preference(
    ingredient_id="guava",
    preference_type="preferred",
):
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (TEST_USER["id"], "Me", 1),
        )
        person_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO person_ingredient_preferences (
                person_id,
                ingredient_id,
                preference_type
            )
            VALUES (?, ?, ?)
            """,
            (
                person_id,
                ingredient_id,
                preference_type,
            ),
        )
        conn.commit()

        return person_id

    finally:
        conn.close()


def test_personalized_goal_preset_uses_explicit_edits_and_records_credit(
    client,
    monkeypatch,
):
    captured = {}
    _fake_personalized_recipe(monkeypatch, captured)
    person_id = _create_person_with_preference()

    ingredient_ids = [
        "guava",
        "pea-milk",
        "cucumber",
        "cauliflower",
        "hemp-seeds",
        "flax-seeds",
    ]

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ingredient_ids,
        },
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["success"] is True
    assert captured == {
        "goal": "skin-glow",
        "timing": "breakfast",
        "variant": "a",
        "ingredient_ids": ingredient_ids,
    }
    assert body["recipe"]["variant"] == "a"
    assert body["recipe"]["preset_contract"]["personalized"] is True
    assert body["recipe"]["preset_contract"]["person_id"] == person_id
    assert (
        body["recipe"]["preset_contract"]["selection_source"]
        == "explicit_ingredient_editor"
    )
    assert body["access"]["free_used"] == 1
    assert body["access"]["free_remaining"] == 2
    assert _ledger_count() == 1


def test_personalized_goal_preset_persists_editor_preferences_in_same_request(
    client,
    monkeypatch,
):
    captured = {}
    _fake_personalized_recipe(monkeypatch, captured)
    person_id = _create_person_without_preferences()

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ["guava", "pea-milk", "banana"],
        },
    )

    assert response.status_code == 200

    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        preference = conn.execute(
            """
            SELECT goal_slug, timing_slug
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person_id,),
        ).fetchone()

        ingredient_preferences = conn.execute(
            """
            SELECT ingredient_id, preference_type
            FROM person_ingredient_preferences
            WHERE person_id = ?
            ORDER BY preference_type, ingredient_id
            """,
            (person_id,),
        ).fetchall()

    finally:
        conn.close()

    assert preference == ("skin-glow", "breakfast")
    assert ingredient_preferences == [
        ("cauliflower", "avoid"),
        ("cucumber", "avoid"),
        ("flax-seeds", "avoid"),
        ("hemp-seeds", "avoid"),
        ("lime-juice", "avoid"),
        ("banana", "preferred"),
        ("guava", "preferred"),
        ("pea-milk", "preferred"),
    ]
    assert _ledger_count() == 1


def test_personalized_goal_preset_requires_setup_before_generation(
    client,
    monkeypatch,
):
    def fail_if_called(**_kwargs):
        raise AssertionError(
            "recipe generation must not run before setup"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_personalized_goal_preset_recipe",
        fail_if_called,
    )

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ["guava"],
        },
    )

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "setup_required",
        "setup": {
            "person_required": True,
            "preferences_required": True,
        },
    }
    assert _ledger_count() == 0


def test_personalized_goal_preset_rejects_too_few_ingredients_without_credit(
    client,
    monkeypatch,
):
    _create_person_with_preference()

    def reject_build(**_kwargs):
        raise goal_preset_recipe.GoalPresetRecipeInputError(
            "at least 3 ingredients are required"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_personalized_goal_preset_recipe",
        reject_build,
    )

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ["guava", "pea-milk"],
        },
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_request",
        "message": "at least 3 ingredients are required",
    }
    assert _ledger_count() == 0


def test_personalized_goal_preset_does_not_record_credit_when_build_fails(
    client,
    monkeypatch,
):
    _create_person_with_preference()

    def fail_build(**_kwargs):
        raise recipe_calculator.RecipeCalculationError(
            "exact nutrition facts not found"
        )

    monkeypatch.setattr(
        goal_preset_recipe,
        "build_personalized_goal_preset_recipe",
        fail_build,
    )

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ["guava", "pea-milk"],
        },
    )

    assert response.status_code == 422
    assert response.get_json()["reason"] == "nutrition_unavailable"
    assert _ledger_count() == 0


def test_personalized_goal_preset_reuses_one_database_connection(
    client,
    monkeypatch,
):
    captured = {}
    _fake_personalized_recipe(monkeypatch, captured)
    person_id = _create_person_with_preference()
    real_get_conn = db.get_conn
    connection_calls = 0

    def counted_get_conn():
        nonlocal connection_calls
        connection_calls += 1
        return real_get_conn()

    monkeypatch.setattr(db, "get_conn", counted_get_conn)

    response = client.post(
        "/api/personalized-goal-preset",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
            "current_variant": "a",
            "ingredient_ids": ["guava", "pea-milk"],
            "person_id": person_id,
        },
    )

    assert response.status_code == 200
    assert connection_calls == 1
