"""
Create ordered account health-goal preferences for registered users.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


def _create_user_health_goal_preferences_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.user_health_goal_preferences (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL
                REFERENCES public.users(id) ON DELETE CASCADE,
            category_value VARCHAR(255) NOT NULL,
            display_order SMALLINT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

            CONSTRAINT user_health_goal_preferences_category_not_blank
                CHECK (BTRIM(category_value) <> ''),
            CONSTRAINT user_health_goal_preferences_display_order_valid
                CHECK (display_order BETWEEN 1 AND 6),
            CONSTRAINT user_health_goal_preferences_user_category_unique
                UNIQUE (user_id, category_value),
            CONSTRAINT user_health_goal_preferences_user_order_unique
                UNIQUE (user_id, display_order)
        )
        """
    )


def _verify_user_health_goal_preferences_table(cur) -> None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'user_health_goal_preferences'
        ORDER BY ordinal_position
        """
    )

    columns = [row[0] for row in cur.fetchall()]
    expected_columns = [
        "id",
        "user_id",
        "category_value",
        "display_order",
        "created_at",
    ]
    if columns != expected_columns:
        raise RuntimeError(
            "user_health_goal_preferences has unexpected columns: "
            f"expected={expected_columns!r}, actual={columns!r}"
        )

    cur.execute(
        """
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.user_health_goal_preferences'::regclass
        """
    )
    constraint_names = {row[0] for row in cur.fetchall()}
    required_constraints = {
        "user_health_goal_preferences_pkey",
        "user_health_goal_preferences_category_not_blank",
        "user_health_goal_preferences_display_order_valid",
        "user_health_goal_preferences_user_category_unique",
        "user_health_goal_preferences_user_order_unique",
    }
    missing_constraints = required_constraints - constraint_names
    if missing_constraints:
        raise RuntimeError(
            "user_health_goal_preferences is missing constraints: "
            f"{sorted(missing_constraints)!r}"
        )

    cur.execute(
        """
        SELECT confdeltype
        FROM pg_constraint
        WHERE conrelid = 'public.user_health_goal_preferences'::regclass
          AND contype = 'f'
        """
    )
    if cur.fetchall() != [("c",)]:
        raise RuntimeError(
            "user_health_goal_preferences must have one "
            "ON DELETE CASCADE foreign key"
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
            _create_user_health_goal_preferences_table(cur)
            _verify_user_health_goal_preferences_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print("SUCCESS: account health-goal preferences are ready")


if __name__ == "__main__":
    main()
