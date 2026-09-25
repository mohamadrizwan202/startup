"""
Create the web SaaS personalization persons table.

Purpose:
- A logged-in PureFyul user may save multiple people for web personalization.
- Keep this feature separate from the existing B2B/app user_profiles system.

This table contains only:
- id
- user_id
- name
- is_default
- created_at
- updated_at

It does not modify:
- user_profiles
- demographic/profile fields
- subscriptions
- saved recipes
- nutrition data
- B2B/app personalization
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


def _create_persons_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.persons (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL
                REFERENCES public.users(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            is_default BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT persons_name_not_blank
                CHECK (BTRIM(name) <> '')
        )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS persons_user_id_idx
        ON public.persons (user_id)
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS persons_one_default_per_user_uidx
        ON public.persons (user_id)
        WHERE is_default = TRUE
        """
    )


def _verify_persons_table(cur) -> None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'persons'
        ORDER BY ordinal_position
        """
    )

    columns = [row[0] for row in cur.fetchall()]

    expected = [
        "id",
        "user_id",
        "name",
        "is_default",
        "created_at",
        "updated_at",
    ]

    if columns != expected:
        raise RuntimeError(
            "persons table has unexpected columns: "
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
            _create_persons_table(cur)
            _verify_persons_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print("SUCCESS: web personalization persons table is ready")


if __name__ == "__main__":
    main()
