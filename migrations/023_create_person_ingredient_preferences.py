"""
Create web personalization ingredient preferences.

Purpose:
- Store preferred and avoided reviewed-preset ingredients per Person.
- Use stable reviewed-preset ingredient IDs.
- Keep this separate from the app profile system.
- Keep nutrition lookup names out of user preference identity.

Columns:
- id
- person_id
- ingredient_id
- preference_type
- created_at
- updated_at
"""

from __future__ import annotations

import os

import psycopg

from dotenv import load_dotenv


def _create_person_ingredient_preferences_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
            public.person_ingredient_preferences (
                id SERIAL PRIMARY KEY,
                person_id INTEGER NOT NULL
                    REFERENCES public.persons(id)
                    ON DELETE CASCADE,
                ingredient_id VARCHAR(100) NOT NULL,
                preference_type VARCHAR(20) NOT NULL,
                created_at TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT
                    person_ingredient_preferences_id_not_blank
                    CHECK (BTRIM(ingredient_id) <> ''),

                CONSTRAINT
                    person_ingredient_preferences_type_valid
                    CHECK (
                        preference_type IN (
                            'preferred',
                            'avoid'
                        )
                    )
            )
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            person_ingredient_preferences_person_ingredient_uidx
        ON public.person_ingredient_preferences (
            person_id,
            ingredient_id
        )
        """
    )


def _verify_person_ingredient_preferences_table(cur) -> None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'person_ingredient_preferences'
        ORDER BY ordinal_position
        """
    )

    columns = [row[0] for row in cur.fetchall()]

    expected = [
        "id",
        "person_id",
        "ingredient_id",
        "preference_type",
        "created_at",
        "updated_at",
    ]

    if columns != expected:
        raise RuntimeError(
            "person_ingredient_preferences has unexpected columns: "
            f"expected={expected!r}, actual={columns!r}"
        )


def main() -> None:
    load_dotenv(".env")

    database_url = (
        os.getenv("DATABASE_URL_MIGRATE")
        or os.getenv("DATABASE_URL")
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL_MIGRATE or DATABASE_URL is required"
        )

    conn = psycopg.connect(database_url)

    try:
        with conn.cursor() as cur:
            _create_person_ingredient_preferences_table(cur)
            _verify_person_ingredient_preferences_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: web personalization ingredient preferences table is ready"
    )


if __name__ == "__main__":
    main()
