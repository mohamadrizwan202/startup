"""
Add a durable identity to each editable personalized smoothie.

Existing ledger rows remain valid trial-usage history. New personalized
smoothies receive one UUID identity, which can be edited without another
generation charge by the owning account.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


def _upgrade_personalized_smoothie_generations(cur) -> None:
    cur.execute(
        """
        ALTER TABLE public.personalized_smoothie_generations
        ADD COLUMN IF NOT EXISTS personalization_id UUID
        """
    )

    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS
            personalized_generations_personalization_id_uidx
        ON public.personalized_smoothie_generations (
            personalization_id
        )
        WHERE personalization_id IS NOT NULL
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
        "personalization_id",
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
            _upgrade_personalized_smoothie_generations(cur)
            _verify_personalized_smoothie_generations_table(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: personalized smoothie recipe identity is ready"
    )


if __name__ == "__main__":
    main()
