import csv
import io
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# HARD TEST ISOLATION
#
# Match the repository's existing backend test pattern. Prevent startup from
# connecting to production databases/services.
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
os.environ["SECRET_KEY"] = "purefyul-recipe-export-tests-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()
db.DB_PATH = Path(_TEST_TMPDIR.name) / "recipe_export_test.sqlite3"

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 30,
    "email": "recipe-export-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


@pytest.fixture
def client(monkeypatch):
    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="purefyul-recipe-export-tests-only",
    )

    monkeypatch.setattr(
        appmod,
        "get_user_by_id",
        lambda user_id: TEST_USER if int(user_id) == TEST_USER["id"] else None,
    )

    # Export behavior is what is under test here, not billing state.
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda user_id: "pro" if int(user_id) == TEST_USER["id"] else "free",
    )

    with appmod.app.test_client() as test_client:
        with test_client.session_transaction() as sess:
            sess["_user_id"] = str(TEST_USER["id"])
            sess["_fresh"] = True

        yield test_client


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
                notes TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _parse_csv_response(response):
    assert response.status_code == 200
    assert response.content_type.startswith("text/csv")
    return list(csv.reader(io.StringIO(response.get_data(as_text=True))))


def test_recipe_export_sqlite_preserves_values_and_user_isolation(
    client,
    monkeypatch,
):
    monkeypatch.setattr(appmod.db, "USE_POSTGRES", False)

    _create_saved_recipes_table()

    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(
            """
            INSERT INTO saved_recipes
                (
                    user_id,
                    name,
                    ingredients,
                    nutrition_summary,
                    health_goal,
                    notes,
                    created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                TEST_USER["id"],
                "Morning Smoothie",
                json.dumps(
                    [
                        {
                            "name": "Papaya",
                            "quantity": 110,
                            "unit": "g",
                        },
                        {
                            "name": "Oat milk",
                            "quantity": 150,
                            "unit": "mL",
                        },
                        {
                            "name": "Chia seeds",
                            "quantity": 10,
                            "unit": "g",
                        },
                    ]
                ),
                json.dumps(
                    {
                        "calories": 275,
                        "protein": 12.5,
                        "carbs": 42,
                        "fat": 8,
                        "fiber": 9,
                        "sugar": 18,
                    }
                ),
                "Gut Health",
                "Timing: Breakfast",
                "2026-09-14 16:30:00",
            ),
        )

        # Must never appear in TEST_USER's export.
        conn.execute(
            """
            INSERT INTO saved_recipes
                (
                    user_id,
                    name,
                    ingredients,
                    nutrition_summary,
                    health_goal,
                    notes,
                    created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                "Other User Smoothie",
                json.dumps(
                    [
                        {
                            "name": "Banana",
                            "quantity": 100,
                            "unit": "g",
                        }
                    ]
                ),
                json.dumps({"calories": 999}),
                "",
                "",
                "2026-09-14 16:31:00",
            ),
        )

        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/recipes/export")
    rows = _parse_csv_response(response)

    assert rows[0] == [
        "Name",
        "Health Goal",
        "Ingredients",
        "Calories",
        "Protein(g)",
        "Carbs(g)",
        "Fat(g)",
        "Fiber(g)",
        "Sugar(g)",
        "Notes",
        "Saved On",
    ]

    assert len(rows) == 2

    assert rows[1] == [
        "Morning Smoothie",
        "Gut Health",
        "Papaya 110g, Oat milk 150mL, Chia seeds 10g",
        "275",
        "12.5",
        "42",
        "8",
        "9",
        "18",
        "Timing: Breakfast",
        "2026-09-14 16:30:00",
    ]

    assert "Other User Smoothie" not in response.get_data(as_text=True)


class FakePostgresCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed_sql = None
        self.executed_params = None

    def execute(self, sql, params):
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self):
        return self.rows


class FakePostgresConnection:
    def __init__(self, rows):
        self.cursor_instance = FakePostgresCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_recipe_export_accepts_postgres_jsonb_objects(
    client,
    monkeypatch,
):
    postgres_rows = [
        {
            "id": 1,
            "user_id": TEST_USER["id"],
            "name": "Postgres Smoothie",
            "ingredients": [
                {
                    "name": "Blueberry",
                    "quantity": 80,
                    "unit": "g",
                },
                {
                    "name": "Greek yogurt",
                    "quantity": 120,
                    "unit": "g",
                },
            ],
            "nutrition_summary": {
                "calories": 210,
                "protein": 18,
                "carbs": 24,
                "fat": 5,
                "fiber": 5,
                "sugar": 14,
            },
            "health_goal": "High Protein",
            "notes": "",
            "created_at": "2026-09-14 16:31:00",
        }
    ]

    fake_conn = FakePostgresConnection(postgres_rows)

    monkeypatch.setattr(appmod.db, "USE_POSTGRES", True)
    monkeypatch.setattr(appmod.db, "get_conn", lambda: fake_conn)

    response = client.get("/api/recipes/export")
    rows = _parse_csv_response(response)

    assert len(rows) == 2

    assert rows[1] == [
        "Postgres Smoothie",
        "High Protein",
        "Blueberry 80g, Greek yogurt 120g",
        "210",
        "18",
        "24",
        "5",
        "5",
        "14",
        "",
        "2026-09-14 16:31:00",
    ]

    assert (
        "WHERE user_id = %s"
        in fake_conn.cursor_instance.executed_sql
    )
    assert fake_conn.cursor_instance.executed_params == (
        TEST_USER["id"],
    )
    assert fake_conn.closed is True


def test_recipe_export_free_user_remains_blocked(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        appmod,
        "get_user_plan",
        lambda _user_id: "free",
    )

    response = client.get("/api/recipes/export")

    assert response.status_code == 403
    assert response.get_json()["error"] == "upgrade_required"
