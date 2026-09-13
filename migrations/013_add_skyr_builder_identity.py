"""
Add the missing PureFyul V1 Skyr builder identity.

Migration 012 successfully added:
- Skyr nutrition
- Skyr Tune rule

But its builder helper was defined without being invoked, so Skyr was not
inserted into ingredient_categories and therefore was not exposed by
/api/ingredient-search.

This forward-only migration adds exactly one reviewed Skyr builder row.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


SKYR_ROW = (
    "skyr",
    "Muscle Health",
    "Protein-Rich Foods",
    "High-protein cultured dairy option",
    "Protein",
    "Reviewed V1 Skyr nutrition provides 11 g protein per 100 g.",
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
            cur.execute(
                """
                SELECT COUNT(*)
                FROM public.ingredient_categories
                WHERE LOWER(BTRIM(ingredient)) = 'skyr'
                  AND category = 'Muscle Health'
                  AND subcategory = 'Protein-Rich Foods'
                """
            )

            count = cur.fetchone()[0]

            if count == 0:
                cur.execute(
                    """
                    INSERT INTO public.ingredient_categories (
                        ingredient,
                        category,
                        subcategory,
                        health_benefits,
                        key_nutrients,
                        description
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    SKYR_ROW,
                )
            elif count > 1:
                raise RuntimeError(
                    f"Unexpected duplicate Skyr builder rows: {count}"
                )

            cur.execute(
                """
                SELECT
                    ingredient,
                    category,
                    subcategory,
                    health_benefits,
                    key_nutrients,
                    description
                FROM public.ingredient_categories
                WHERE LOWER(BTRIM(ingredient)) = 'skyr'
                  AND category = 'Muscle Health'
                  AND subcategory = 'Protein-Rich Foods'
                """
            )

            row = cur.fetchone()

            if row != SKYR_ROW:
                raise RuntimeError(
                    f"Skyr builder verification failed: {row!r}"
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print("SUCCESS: Skyr builder identity is ready")


if __name__ == "__main__":
    main()
