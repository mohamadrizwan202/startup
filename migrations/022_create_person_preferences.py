"""
Create the web personalization person_preferences table.

Purpose:
- Store personalization settings for a saved Person.
- Keep web personalization separate from the app profile system.
- Reuse the existing deterministic goal preset slugs rather than creating
  a duplicate goals table.

This first version contains only:
- id
- person_id
- goal_slug
- timing_slug
- created_at
- updated_at

Future personalization fields such as timing and ingredient preferences
will be added separately after their contracts are verified.
"""

from __future__ import annotations

import os

import psycopg

from dotenv import load_dotenv


def _create_person_preferences_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.person_preferences (
            id SERIAL PRIMARY KEY,
            person_id INTEGER NOT NULL
              REFERENCES public.persons(id) ON DELETE CASCADE,
            goal_slug VARCHAR(100) NOT NULL,
            timing_slug VARCHAR(100),
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            person_preferences_person_id_uidx
        ON public.person_preferences (person_id)
        """
    )


def _verify_person_preferences_table(cur) -> None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'person_preferences'
        ORDER BY ordinal_position
        """
    )

    columns = [row[0] for row in cur.fetchall()]

    expected = [
        "id",
        "person_id",
        "goal_slug",
        "timing_slug",
        "created_at",
        "updated_at",
    ]

    if columns != expected:
        raise RuntimeError(
            "person_preferences table has unexpected columns: "
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
            _create_person_preferences_table(cur)
            _verify_person_preferences_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: web personalization person_preferences table is ready"
    )


if __name__ == "__main__":
    main()
