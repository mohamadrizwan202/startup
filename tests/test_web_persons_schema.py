import sqlite3

import db


EXPECTED_PERSON_COLUMNS = [
    "id",
    "user_id",
    "name",
    "is_default",
    "created_at",
    "updated_at",
]


def _prepare_isolated_schema(monkeypatch, tmp_path):
    database_path = tmp_path / "web_persons.sqlite3"

    monkeypatch.setenv("ENABLE_DB_MIGRATIONS", "1")
    monkeypatch.setattr(db, "DATABASE_URL_MIGRATE", "")
    monkeypatch.setattr(db, "RUNTIME_DB_URL", "")
    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "DB_PATH", database_path)

    db.ensure_schema()

    return database_path


def test_web_persons_schema_is_isolated_and_exact(monkeypatch, tmp_path):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    try:
        columns = [
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(persons)"
            ).fetchall()
        ]

        assert columns == EXPECTED_PERSON_COLUMNS
    finally:
        conn.close()


def test_web_persons_allows_only_one_default_per_user(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            ("person-test@example.com", "test-hash"),
        )

        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("person-test@example.com",),
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO persons (user_id, name, is_default)
            VALUES (?, ?, ?)
            """,
            (user_id, "Me", 1),
        )
        conn.commit()

        try:
            conn.execute(
                """
                INSERT INTO persons (user_id, name, is_default)
                VALUES (?, ?, ?)
                """,
                (user_id, "Partner", 1),
            )
            conn.commit()
            raise AssertionError(
                "second default person was incorrectly allowed"
            )
        except sqlite3.IntegrityError:
            conn.rollback()
    finally:
        conn.close()


def test_web_persons_rejects_blank_name(monkeypatch, tmp_path):
    database_path = _prepare_isolated_schema(monkeypatch, tmp_path)

    conn = sqlite3.connect(str(database_path))
    try:
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            ("blank-name-test@example.com", "test-hash"),
        )

        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?",
            ("blank-name-test@example.com",),
        ).fetchone()[0]

        try:
            conn.execute(
                """
                INSERT INTO persons (user_id, name)
                VALUES (?, ?)
                """,
                (user_id, "   "),
            )
            conn.commit()
            raise AssertionError(
                "blank person name was incorrectly allowed"
            )
        except sqlite3.IntegrityError:
            conn.rollback()
    finally:
        conn.close()
