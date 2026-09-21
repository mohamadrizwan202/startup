"""
Add meal timing context to saved recipes.

PureFyul's Goal → Time builder treats timing as part of the recipe context
(Breakfast, Morning Snack, Lunch, Afternoon Snack, Dinner, Bedtime).

This migration adds one nullable column only:
- saved_recipes.timing

It does not modify existing recipe rows, permissions, pricing,
ingredients, nutrition data, or save behavior.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


def _add_timing_column(cur) -> None:
    cur.execute(
        """
        ALTER TABLE public.saved_recipes
        ADD COLUMN IF NOT EXISTS timing VARCHAR(100)
        """
    )


def _verify_timing_column(cur) -> None:
    cur.execute(
        """
        SELECT data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'saved_recipes'
          AND column_name = 'timing'
        """
    )

    row = cur.fetchone()

    if row is None:
        raise RuntimeError(
            "saved_recipes.timing was not created"
        )

    data_type, max_length = row

    if data_type != "character varying" or max_length != 100:
        raise RuntimeError(
            "saved_recipes.timing has unexpected schema: "
            f"data_type={data_type!r}, max_length={max_length!r}"
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
            _add_timing_column(cur)
            _verify_timing_column(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: saved_recipes timing column is ready"
    )


if __name__ == "__main__":
    main()
