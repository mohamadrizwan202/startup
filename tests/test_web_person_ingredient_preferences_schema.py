import sqlite3

import pytest

import db


EXPECTED_COLUMNS = [
    "id",
    "person_id",
    "ingredient_id",
    "preference_type",
    "created_at",
    "updated_at",
]


def _prepare_isolated_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "web_person_ingredient_preferences.sqlite3"

    monkeypatch.setenv("ENABLE_DB_MIGRATIONS", "1")
    monkeypatch.setattr(db, "DATABASE_URL_MIGRATE", "")
    monkeypatch.setattr(db, "RUNTIME_DB_URL", "")
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "DB_PATH", database_path)

    db.ensure_schema()

    return database_path


def _create_person(conn):
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        ("ingredient-pref-test@example.com", "test-hash"),
    )

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("ingredient-pref-test@example.com",),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO persons (user_id, name, is_default)
        VALUES (?, ?, ?)
        """,
        (user_id, "Me", 1),
    )

    conn.commit()

    return conn.execute(
        "SELECT id FROM persons WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]


def test_person_ingredient_preferences_schema_is_exact(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(person_ingredient_preferences)"
            ).fetchall()
        ]

        assert columns == EXPECTED_COLUMNS

    finally:
        conn.close()


def test_person_ingredient_preferences_allows_one_row_per_ingredient(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        person_id = _create_person(conn)

        conn.execute(
            """
            INSERT INTO person_ingredient_preferences (
                person_id,
                ingredient_id,
                preference_type
            )
            VALUES (?, ?, ?)
            """,
            (person_id, "blueberry", "preferred"),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO person_ingredient_preferences (
                    person_id,
                    ingredient_id,
                    preference_type
                )
                VALUES (?, ?, ?)
                """,
                (person_id, "blueberry", "avoid"),
            )
            conn.commit()

    finally:
        conn.close()


@pytest.mark.parametrize(
    "preference_type",
    [
        "",
        "like",
        "dislike",
        "allergy",
    ],
)
def test_person_ingredient_preferences_rejects_invalid_type(
    monkeypatch,
    tmp_path,
    preference_type,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        person_id = _create_person(conn)

        with pytest.raises(sqlite3.IntegrityError):
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
                    "banana",
                    preference_type,
                ),
            )
            conn.commit()

    finally:
        conn.close()


def test_person_ingredient_preferences_delete_with_person(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        person_id = _create_person(conn)

        conn.execute(
            """
            INSERT INTO person_ingredient_preferences (
                person_id,
                ingredient_id,
                preference_type
            )
            VALUES (?, ?, ?)
            """,
            (person_id, "oat-milk", "preferred"),
        )
        conn.commit()

        conn.execute(
            "DELETE FROM persons WHERE id = ?",
            (person_id,),
        )
        conn.commit()

        remaining = conn.execute(
            """
            SELECT COUNT(*)
            FROM person_ingredient_preferences
            WHERE person_id = ?
            """,
            (person_id,),
        ).fetchone()[0]

        assert remaining == 0

    finally:
        conn.close()
