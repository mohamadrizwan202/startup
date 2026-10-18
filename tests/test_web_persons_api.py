import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# HARD TEST ISOLATION — WEB PERSONALIZATION ONLY
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
os.environ["SECRET_KEY"] = "purefyul-web-persons-api-tests-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["FLASK_DEBUG"] = "0"

import db  # noqa: E402


_TEST_TMPDIR = tempfile.TemporaryDirectory()

db.DB_PATH = Path(_TEST_TMPDIR.name) / "web_persons_api_test.sqlite3"
db.USE_POSTGRES = False

import startup_recovered as appmod  # noqa: E402


TEST_USER = {
    "id": 71,
    "email": "web-persons-test@example.com",
    "password_hash": "not-used",
    "created_at": "",
}


def _create_persons_table():
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(
            "DROP TABLE IF EXISTS person_ingredient_preferences"
        )
        conn.execute("DROP TABLE IF EXISTS persons")
        conn.execute(
            """
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (TRIM(name) <> ''),
                CHECK (is_default IN (0, 1))
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX persons_one_default_per_user_uidx
            ON persons(user_id)
            WHERE is_default = 1
            """
        )

        conn.execute("DROP TABLE IF EXISTS person_preferences")
        conn.execute(
            """
            CREATE TABLE person_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL
                    REFERENCES persons(id) ON DELETE CASCADE,
                goal_slug TEXT NOT NULL,
                timing_slug TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX person_preferences_person_id_uidx
            ON person_preferences(person_id)
            """
        )

        conn.execute(
            """
            CREATE TABLE person_ingredient_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL
                    REFERENCES persons(id) ON DELETE CASCADE,
                ingredient_id TEXT NOT NULL,
                preference_type TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (TRIM(ingredient_id) <> ''),
                CHECK (
                    preference_type IN (
                        'preferred',
                        'avoid'
                    )
                )
            )
            """
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX
                person_ingredient_preferences_person_ingredient_uidx
            ON person_ingredient_preferences(
                person_id,
                ingredient_id
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    _create_persons_table()

    appmod.app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="purefyul-web-persons-api-tests-only",
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


def test_create_first_person_becomes_default(client):
    response = client.post(
        "/api/persons",
        json={"name": "  Me  "},
    )

    assert response.status_code == 201

    body = response.get_json()

    assert body["person"]["name"] == "Me"
    assert body["person"]["is_default"] is True

    conn = sqlite3.connect(str(db.DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT user_id, name, is_default
            FROM persons
            WHERE id = ?
            """,
            (body["person"]["id"],),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["user_id"] == TEST_USER["id"]
    assert row["name"] == "Me"
    assert row["is_default"] == 1


def test_second_person_is_not_default(client):
    first = client.post(
        "/api/persons",
        json={"name": "Me"},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/persons",
        json={"name": "Partner"},
    )
    assert second.status_code == 201

    assert second.get_json()["person"]["is_default"] is False


def test_get_persons_is_user_scoped_and_default_first(client):
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (999, "Other User", 1),
        )
        conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (TEST_USER["id"], "Partner", 0),
        )
        conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (TEST_USER["id"], "Me", 1),
        )
        conn.commit()
    finally:
        conn.close()

    response = client.get("/api/persons")

    assert response.status_code == 200

    persons = response.get_json()["persons"]

    assert [person["name"] for person in persons] == [
        "Me",
        "Partner",
    ]
    assert persons[0]["is_default"] is True
    assert all(person["name"] != "Other User" for person in persons)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "x" * 101,
    ],
)
def test_create_person_rejects_invalid_name(client, name):
    response = client.post(
        "/api/persons",
        json={"name": name},
    )

    assert response.status_code == 400


def test_update_person_name(client):
    created = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{created['id']}",
        json={"name": "Hanzla"},
    )

    assert response.status_code == 200
    person = response.get_json()["person"]

    assert person["name"] == "Hanzla"
    assert person["is_default"] is True


def test_make_another_person_default(client):
    first = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    second = client.post(
        "/api/persons",
        json={"name": "Partner"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{second['id']}",
        json={"is_default": True},
    )

    assert response.status_code == 200
    assert response.get_json()["person"]["is_default"] is True

    persons = client.get("/api/persons").get_json()["persons"]

    assert persons[0]["id"] == second["id"]
    assert persons[0]["is_default"] is True

    original = next(
        person for person in persons
        if person["id"] == first["id"]
    )
    assert original["is_default"] is False


def test_person_update_is_owner_scoped(client):
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (999, "Other User", 1),
        )
        other_person_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    response = client.patch(
        f"/api/persons/{other_person_id}",
        json={"name": "Changed"},
    )

    assert response.status_code == 404


def test_delete_non_default_person(client):
    client.post(
        "/api/persons",
        json={"name": "Me"},
    )

    second = client.post(
        "/api/persons",
        json={"name": "Partner"},
    ).get_json()["person"]

    response = client.delete(
        f"/api/persons/{second['id']}"
    )

    assert response.status_code == 200

    persons = client.get("/api/persons").get_json()["persons"]

    assert [person["name"] for person in persons] == ["Me"]
    assert persons[0]["is_default"] is True


def test_delete_default_promotes_remaining_person(client):
    first = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    client.post(
        "/api/persons",
        json={"name": "Partner"},
    )

    response = client.delete(
        f"/api/persons/{first['id']}"
    )

    assert response.status_code == 200

    persons = client.get("/api/persons").get_json()["persons"]

    assert len(persons) == 1
    assert persons[0]["name"] == "Partner"
    assert persons[0]["is_default"] is True


def test_delete_last_person_allows_empty_list(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.delete(
        f"/api/persons/{person['id']}"
    )

    assert response.status_code == 200
    assert client.get("/api/persons").get_json()["persons"] == []


def test_person_delete_is_owner_scoped(client):
    conn = sqlite3.connect(str(db.DB_PATH))
    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (999, "Other User", 1),
        )
        other_person_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()

    response = client.delete(
        f"/api/persons/{other_person_id}"
    )

    assert response.status_code == 404



# ---------------------------------------------------------------------------
# WEB PERSONALIZATION: PERSON GOAL PREFERENCES
# ---------------------------------------------------------------------------


def test_get_person_preferences_returns_none_before_setup(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.get(
        f"/api/persons/{person['id']}/preferences"
    )

    assert response.status_code == 200
    assert response.get_json()["preference"] is None


def test_set_person_goal_preference(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"goal": "brain-focus"},
    )

    assert response.status_code == 200

    preference = response.get_json()["preference"]

    assert preference["goal"] == "brain-focus"

    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        row = conn.execute(
            """
            SELECT person_id, goal_slug
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person["id"],),
        ).fetchone()

    finally:
        conn.close()

    assert row is not None
    assert row[0] == person["id"]
    assert row[1] == "brain-focus"


def test_update_person_goal_preference_reuses_same_row(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    first = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"goal": "skin-glow"},
    )

    assert first.status_code == 200

    second = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"goal": "heart-support"},
    )

    assert second.status_code == 200
    assert second.get_json()["preference"]["goal"] == "heart-support"

    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        rows = conn.execute(
            """
            SELECT goal_slug
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person["id"],),
        ).fetchall()

    finally:
        conn.close()

    assert rows == [("heart-support",)]


@pytest.mark.parametrize(
    "goal",
    [
        "",
        "   ",
        "sleep-support",
    ],
)
def test_person_goal_preference_rejects_unsupported_goal(
    client,
    goal,
):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"goal": goal},
    )

    assert response.status_code == 400


def test_person_preferences_are_owner_scoped(client):
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (999, "Other User", 1),
        )
        other_person_id = cursor.lastrowid
        conn.commit()

    finally:
        conn.close()

    get_response = client.get(
        f"/api/persons/{other_person_id}/preferences"
    )

    patch_response = client.patch(
        f"/api/persons/{other_person_id}/preferences",
        json={"goal": "skin-glow"},
    )

    assert get_response.status_code == 404
    assert patch_response.status_code == 404



def test_get_person_preferences_returns_unset_timing(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"goal": "brain-focus"},
    )

    assert response.status_code == 200

    preference = client.get(
        f"/api/persons/{person['id']}/preferences"
    ).get_json()["preference"]

    assert preference["goal"] == "brain-focus"
    assert preference["timing"] is None


def test_set_person_goal_and_timing_together(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
        },
    )

    assert response.status_code == 200

    preference = response.get_json()["preference"]

    assert preference["goal"] == "skin-glow"
    assert preference["timing"] == "breakfast"


def test_person_preferences_requires_goal_before_timing(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"timing": "dinner"},
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "goal_required",
    }


def test_postgres_person_preferences_patch_uses_single_statement(
    client,
    monkeypatch,
):
    class FakeCursor:
        def __init__(self):
            self.execute_calls = []

        def execute(self, sql, parameters):
            self.execute_calls.append((sql, parameters))

        def fetchone(self):
            return {
                "person_found": True,
                "goal_required": False,
                "goal_slug": "skin-glow",
                "timing_slug": "breakfast",
                "created_at": "created",
                "updated_at": "updated",
            }

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.commit_count = 0
            self.rollback_count = 0
            self.closed = False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commit_count += 1

        def rollback(self):
            self.rollback_count += 1

        def close(self):
            self.closed = True

    connection = FakeConnection()

    monkeypatch.setattr(db, "USE_POSTGRES", True)
    monkeypatch.setattr(
        db,
        "get_conn",
        lambda: connection,
    )

    response = client.patch(
        "/api/persons/123/preferences",
        json={
            "goal": "skin-glow",
            "timing": "breakfast",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["preference"] == {
        "goal": "skin-glow",
        "timing": "breakfast",
        "created_at": "created",
        "updated_at": "updated",
    }

    execute_calls = (
        connection.cursor_instance.execute_calls
    )

    assert len(execute_calls) == 1

    sql, parameters = execute_calls[0]

    assert "ON CONFLICT (person_id)" in sql
    assert "RETURNING" in sql
    assert parameters == (
        123,
        TEST_USER["id"],
        True,
        "skin-glow",
        True,
        "breakfast",
    )
    assert connection.commit_count == 1
    assert connection.rollback_count == 0
    assert connection.closed is True


def test_update_person_timing_preserves_goal(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    first = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={
            "goal": "gut-health",
            "timing": "breakfast",
        },
    )

    assert first.status_code == 200

    second = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={"timing": "dinner"},
    )

    assert second.status_code == 200

    preference = second.get_json()["preference"]

    assert preference["goal"] == "gut-health"
    assert preference["timing"] == "dinner"


@pytest.mark.parametrize(
    "timing",
    [
        "",
        "   ",
        "brunch",
    ],
)
def test_person_preferences_rejects_unsupported_timing(
    client,
    timing,
):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.patch(
        f"/api/persons/{person['id']}/preferences",
        json={
            "goal": "brain-focus",
            "timing": timing,
        },
    )

    assert response.status_code == 400



# ---------------------------------------------------------------------------
# WEB PERSONALIZATION: PERSON INGREDIENT PREFERENCES
# ---------------------------------------------------------------------------


def test_get_person_ingredient_preferences_starts_empty(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.get(
        f"/api/persons/{person['id']}/ingredient-preferences"
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "preferred": [],
        "avoid": [],
    }


def test_replace_person_ingredient_preferences(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.put(
        f"/api/persons/{person['id']}/ingredient-preferences",
        json={
            "preferred": [
                "blueberry",
                "oat-milk",
            ],
            "avoid": [
                "banana",
            ],
        },
    )

    assert response.status_code == 200

    assert response.get_json() == {
        "preferred": [
            "blueberry",
            "oat-milk",
        ],
        "avoid": [
            "banana",
        ],
    }

    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        rows = conn.execute(
            """
            SELECT ingredient_id, preference_type
            FROM person_ingredient_preferences
            WHERE person_id = ?
            ORDER BY preference_type, ingredient_id
            """,
            (person["id"],),
        ).fetchall()

    finally:
        conn.close()

    assert rows == [
        ("banana", "avoid"),
        ("blueberry", "preferred"),
        ("oat-milk", "preferred"),
    ]


def test_replace_person_ingredient_preferences_removes_old_choices(
    client,
):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    first = client.put(
        f"/api/persons/{person['id']}/ingredient-preferences",
        json={
            "preferred": [
                "blueberry",
                "banana",
            ],
            "avoid": [
                "oat-milk",
            ],
        },
    )

    assert first.status_code == 200

    second = client.put(
        f"/api/persons/{person['id']}/ingredient-preferences",
        json={
            "preferred": [
                "strawberry",
            ],
            "avoid": [
                "banana",
            ],
        },
    )

    assert second.status_code == 200

    assert second.get_json() == {
        "preferred": [
            "strawberry",
        ],
        "avoid": [
            "banana",
        ],
    }


@pytest.mark.parametrize(
    ("field", "ingredient_id"),
    [
        ("preferred", "not-a-reviewed-ingredient"),
        ("avoid", "not-a-reviewed-ingredient"),
    ],
)
def test_person_ingredient_preferences_rejects_unsupported_ingredient(
    client,
    field,
    ingredient_id,
):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    payload = {
        "preferred": [],
        "avoid": [],
    }
    payload[field] = [ingredient_id]

    response = client.put(
        f"/api/persons/{person['id']}/ingredient-preferences",
        json=payload,
    )

    assert response.status_code == 400


def test_person_ingredient_preferences_rejects_overlap(client):
    person = client.post(
        "/api/persons",
        json={"name": "Me"},
    ).get_json()["person"]

    response = client.put(
        f"/api/persons/{person['id']}/ingredient-preferences",
        json={
            "preferred": [
                "banana",
            ],
            "avoid": [
                "banana",
            ],
        },
    )

    assert response.status_code == 400


def test_person_ingredient_preferences_are_owner_scoped(client):
    conn = sqlite3.connect(str(db.DB_PATH))

    try:
        cursor = conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (999, "Other User", 1),
        )
        other_person_id = cursor.lastrowid
        conn.commit()

    finally:
        conn.close()

    get_response = client.get(
        f"/api/persons/{other_person_id}/ingredient-preferences"
    )

    put_response = client.put(
        f"/api/persons/{other_person_id}/ingredient-preferences",
        json={
            "preferred": [
                "blueberry",
            ],
            "avoid": [],
        },
    )

    assert get_response.status_code == 404
    assert put_response.status_code == 404


def test_personalized_goal_preset_access_returns_current_account_access(
    client,
    monkeypatch,
):
    expected_access = {
        "plan": "free",
        "allowed": True,
        "access_type": "free_trial",
        "free_limit": 3,
        "free_used": 1,
        "free_remaining": 2,
    }

    monkeypatch.setattr(
        appmod,
        "_get_personalized_generation_access",
        lambda user_id: expected_access,
    )

    response = client.get(
        "/api/personalized-goal-preset/access"
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "access": expected_access,
    }


def test_personalization_ingredient_options_returns_reviewed_catalog(client):
    response = client.get(
        "/api/personalization/ingredient-options"
    )

    assert response.status_code == 200

    body = response.get_json()
    options = body["ingredients"]

    assert len(options) == 36
    assert all(
        set(option) == {"id", "display_name", "unit"}
        for option in options
    )

    ids = [option["id"] for option in options]

    assert len(ids) == len(set(ids))

    by_id = {
        option["id"]: option["display_name"]
        for option in options
    }

    assert by_id["oat-milk"] == "Oat Milk"
    assert by_id["banana"] == "Banana"
    assert by_id["greek-yogurt"] == "Greek Yogurt"

def test_personalization_ingredient_options_include_goal_aligned_ids(
    client,
):
    response = client.get(
        "/api/personalization/ingredient-options?goal=skin-glow"
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["goal"] == "skin-glow"
    assert len(body["ingredients"]) == 36

    aligned_ids = set(body["goal_aligned_ingredient_ids"])

    assert {
        "guava",
        "kiwi",
        "papaya",
    } <= aligned_ids
    assert "banana" not in aligned_ids


def test_personalization_ingredient_options_rejects_invalid_goal(
    client,
):
    response = client.get(
        "/api/personalization/ingredient-options"
        "?goal=not-a-real-goal"
    )

    assert response.status_code == 400

    body = response.get_json()
    assert body["error"] == "invalid_request"
    assert "unsupported personalization goal" in body["message"]
