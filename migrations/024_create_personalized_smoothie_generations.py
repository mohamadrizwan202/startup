"""
Create the web personalization smoothie-generation ledger.

Purpose:
- Record successful personalized smoothie generations.
- Support the account-wide first-3-free personalization entitlement.
- Distinguish free-trial generations from Pro generations.
- Preserve trial usage if a Person is deleted.
- Remove generation history if the owning user is deleted.

Columns:
- id
- user_id
- person_id
- goal_slug
- timing_slug
- access_type
- created_at
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


def _create_personalized_smoothie_generations_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS
            public.personalized_smoothie_generations (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL
                    REFERENCES public.users(id)
                    ON DELETE CASCADE,
                person_id INTEGER
                    REFERENCES public.persons(id)
                    ON DELETE SET NULL,
                goal_slug VARCHAR(100) NOT NULL,
                timing_slug VARCHAR(100) NOT NULL,
                access_type VARCHAR(20) NOT NULL,
                created_at TIMESTAMP NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT personalized_generations_goal_not_blank
                    CHECK (BTRIM(goal_slug) <> ''),
                CONSTRAINT personalized_generations_timing_not_blank
                    CHECK (BTRIM(timing_slug) <> ''),
                CONSTRAINT personalized_generations_access_type_valid
                    CHECK (
                        access_type IN (
                            'free_trial',
                            'pro'
                        )
                    )
            )
        """
    )

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS
            personalized_generations_user_access_created_idx
        ON public.personalized_smoothie_generations (
            user_id,
            access_type,
            created_at DESC
        )
        """
    )


def _verify_personalized_smoothie_generations_table(cur) -> None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'personalized_smoothie_generations'
        ORDER BY ordinal_position
        """
    )

    columns = [row[0] for row in cur.fetchall()]

    expected = [
        "id",
        "user_id",
        "person_id",
        "goal_slug",
        "timing_slug",
        "access_type",
        "created_at",
    ]

    if columns != expected:
        raise RuntimeError(
            "personalized_smoothie_generations has unexpected columns: "
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
            _create_personalized_smoothie_generations_table(cur)
            _verify_personalized_smoothie_generations_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: personalized smoothie generation ledger is ready"
    )


if __name__ == "__main__":
    main()
