import sqlite3

import pytest

import db


EXPECTED_PERSON_PREFERENCE_COLUMNS = [
    "id",
    "person_id",
    "goal_slug",
    "timing_slug",
    "created_at",
    "updated_at",
]


def _prepare_isolated_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "web_person_preferences.sqlite3"

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
        ("preference-test@example.com", "test-hash"),
    )

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("preference-test@example.com",),
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


def test_web_person_preferences_schema_is_exact(monkeypatch, tmp_path):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(person_preferences)"
            ).fetchall()
        ]

        assert columns == EXPECTED_PERSON_PREFERENCE_COLUMNS

    finally:
        conn.close()


def test_web_person_preferences_allows_one_row_per_person(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        person_id = _create_person(conn)

        conn.execute(
            """
            INSERT INTO person_preferences (person_id, goal_slug)
            VALUES (?, ?)
            """,
            (person_id, "skin-glow"),
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO person_preferences (person_id, goal_slug)
                VALUES (?, ?)
                """,
                (person_id, "brain-focus"),
            )
            conn.commit()

    finally:
        conn.close()


def test_web_person_preferences_delete_with_person(
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
            INSERT INTO person_preferences (person_id, goal_slug)
            VALUES (?, ?)
            """,
            (person_id, "gut-health"),
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
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person_id,),
        ).fetchone()[0]

        assert remaining == 0

    finally:
        conn.close()



def test_web_person_preferences_timing_can_be_unset(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        person_id = _create_person(conn)

        conn.execute(
            """
            INSERT INTO person_preferences (
                person_id,
                goal_slug
            )
            VALUES (?, ?)
            """,
            (person_id, "brain-focus"),
        )
        conn.commit()

        timing_slug = conn.execute(
            """
            SELECT timing_slug
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person_id,),
        ).fetchone()[0]

        assert timing_slug is None

    finally:
        conn.close()


def test_web_person_preferences_stores_timing_slug(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        person_id = _create_person(conn)

        conn.execute(
            """
            INSERT INTO person_preferences (
                person_id,
                goal_slug,
                timing_slug
            )
            VALUES (?, ?, ?)
            """,
            (person_id, "brain-focus", "breakfast"),
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT goal_slug, timing_slug
            FROM person_preferences
            WHERE person_id = ?
            """,
            (person_id,),
        ).fetchone()

        assert row == ("brain-focus", "breakfast")

    finally:
        conn.close()
