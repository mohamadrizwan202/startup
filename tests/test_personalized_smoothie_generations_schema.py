import sqlite3

import db


EXPECTED_COLUMNS = [
    "id",
    "user_id",
    "person_id",
    "goal_slug",
    "timing_slug",
    "access_type",
    "created_at",
]


def _prepare_isolated_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "personalized_generations.sqlite3"

    monkeypatch.setenv("ENABLE_DB_MIGRATIONS", "1")
    monkeypatch.setattr(db, "DATABASE_URL_MIGRATE", "")
    monkeypatch.setattr(db, "RUNTIME_DB_URL", "")
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "DB_PATH", database_path)

    db.ensure_schema()

    return database_path


def _create_user_and_person(conn):
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        ("trial-ledger-test@example.com", "test-hash"),
    )

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("trial-ledger-test@example.com",),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO persons (user_id, name, is_default)
        VALUES (?, ?, ?)
        """,
        (user_id, "Me", 1),
    )

    person_id = conn.execute(
        "SELECT id FROM persons WHERE user_id = ?",
        (user_id,),
    ).fetchone()[0]

    conn.commit()

    return user_id, person_id


def test_personalized_generation_schema_is_exact(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(personalized_smoothie_generations)"
            ).fetchall()
        ]

        assert columns == EXPECTED_COLUMNS

    finally:
        conn.close()


def test_personalized_generation_ledger_allows_multiple_successes(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))

    try:
        user_id, person_id = _create_user_and_person(conn)

        for goal_slug in (
            "skin-glow",
            "brain-focus",
            "gut-health",
        ):
            conn.execute(
                """
                INSERT INTO personalized_smoothie_generations (
                    user_id,
                    person_id,
                    goal_slug,
                    timing_slug,
                    access_type
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    person_id,
                    goal_slug,
                    "breakfast",
                    "free_trial",
                ),
            )

        conn.commit()

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM personalized_smoothie_generations
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]

        assert count == 3

    finally:
        conn.close()


def test_deleting_person_preserves_generation_usage(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        user_id, person_id = _create_user_and_person(conn)

        conn.execute(
            """
            INSERT INTO personalized_smoothie_generations (
                user_id,
                person_id,
                goal_slug,
                timing_slug,
                access_type
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                person_id,
                "heart-support",
                "dinner",
                "free_trial",
            ),
        )
        conn.commit()

        conn.execute(
            "DELETE FROM persons WHERE id = ?",
            (person_id,),
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT user_id, person_id
            FROM personalized_smoothie_generations
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        assert row == (user_id, None)

    finally:
        conn.close()


def test_deleting_user_removes_generation_history(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        user_id, person_id = _create_user_and_person(conn)

        conn.execute(
            """
            INSERT INTO personalized_smoothie_generations (
                user_id,
                person_id,
                goal_slug,
                timing_slug,
                access_type
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                person_id,
                "muscle-health",
                "lunch",
                "free_trial",
            ),
        )
        conn.commit()

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )
        conn.commit()

        count = conn.execute(
            """
            SELECT COUNT(*)
            FROM personalized_smoothie_generations
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()[0]

        assert count == 0

    finally:
        conn.close()
