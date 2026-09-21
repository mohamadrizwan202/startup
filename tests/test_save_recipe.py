import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# HARD TEST ISOLATION
# ---------------------------------------------------------------------------
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
os.environ["SECRET_KEY"] = "purefyul-save-recipe-tests-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "save_recipe_test.sqlite3"

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 41,
    "email": "save-recipe-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


def _create_saved_recipes_table():
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute("DROP TABLE IF EXISTS saved_recipes")
        conn.execute(
            """
            CREATE TABLE saved_recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                nutrition_summary TEXT,
                health_goal TEXT,
                timing TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    _create_saved_recipes_table()

    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="purefyul-save-recipe-tests-only",
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

    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: (
            "pro"
            if int(user_id) == TEST_USER["id"]
            else "free"
        ),
    )

    with appmod.app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess["_user_id"] = str(TEST_USER["id"])
            sess["_fresh"] = True

        yield test_client


def test_save_recipe_persists_goal_and_timing(client):
    payload = {
        "name": "Gut Health Smoothie",
        "ingredients": [
            {"name": "Kefir", "quantity": 113, "unit": "ml"},
            {"name": "Kiwi", "quantity": 68, "unit": "g"},
        ],
        "nutrition_summary": {
            "calories": 346,
            "protein": 12.8,
            "carbs": 54.5,
            "fat": 10.6,
            "fiber": 11.0,
            "sugar": 20.0,
        },
        "health_goal": "Gut Health",
        "timing": "Dinner",
        "notes": "Timing: Dinner",
    }

    response = client.post(
        "/api/recipes",
        json=payload,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["id"] > 0

    conn = sqlite3.connect(str(db.DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        row = conn.execute(
            """
            SELECT
                user_id,
                name,
                ingredients,
                nutrition_summary,
                health_goal,
                timing,
                notes
            FROM saved_recipes
            WHERE id = ?
            """,
            (body["id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["user_id"] == TEST_USER["id"]
    assert row["name"] == "Gut Health Smoothie"
    assert json.loads(row["ingredients"]) == payload["ingredients"]
    assert json.loads(row["nutrition_summary"]) == payload["nutrition_summary"]
    assert row["health_goal"] == "Gut Health"
    assert row["timing"] == "Dinner"
    assert row["notes"] == "Timing: Dinner"

    get_response = client.get("/api/recipes")

    assert get_response.status_code == 200

    recipes = get_response.get_json()["recipes"]

    assert len(recipes) == 1
    assert recipes[0]["name"] == "Gut Health Smoothie"
    assert recipes[0]["health_goal"] == "Gut Health"
    assert recipes[0]["timing"] == "Dinner"
