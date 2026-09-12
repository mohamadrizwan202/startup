"""
Add the reviewed PureFyul V1 Tune rule for oats.

Product guardrail:

- solver-facing gram range: 10-60 g

This is a PureFyul culinary/product tuning guardrail, not a serving
recommendation or medical recommendation.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


LOOKUP_NAME = "oats"
MIN_WEIGHT_G = 10.0
MAX_WEIGHT_G = 60.0
SOURCE_TYPE = "purefyul_product_policy"
RATIONALE = (
    "Reviewed PureFyul V1 culinary/product Tune guardrail; "
    "not a serving recommendation."
)
REVIEW_STATUS = "approved"


def main() -> None:
    load_dotenv(".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    conn = psycopg.connect(database_url)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public.ingredient_tuning_rules (
                    nutrition_lookup_name,
                    min_weight_g,
                    max_weight_g,
                    source_type,
                    source_reference,
                    rationale,
                    review_status,
                    enabled
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    NULL,
                    %s,
                    %s,
                    TRUE
                )
                ON CONFLICT (nutrition_lookup_name)
                DO UPDATE SET
                    min_weight_g = EXCLUDED.min_weight_g,
                    max_weight_g = EXCLUDED.max_weight_g,
                    source_type = EXCLUDED.source_type,
                    source_reference = EXCLUDED.source_reference,
                    rationale = EXCLUDED.rationale,
                    review_status = EXCLUDED.review_status,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
                """,
                (
                    LOOKUP_NAME,
                    MIN_WEIGHT_G,
                    MAX_WEIGHT_G,
                    SOURCE_TYPE,
                    RATIONALE,
                    REVIEW_STATUS,
                ),
            )

            cur.execute(
                """
                SELECT
                    nutrition_lookup_name,
                    min_weight_g,
                    max_weight_g,
                    source_type,
                    source_reference,
                    review_status,
                    enabled
                FROM public.ingredient_tuning_rules
                WHERE LOWER(BTRIM(nutrition_lookup_name)) = %s
                """,
                (LOOKUP_NAME,),
            )

            row = cur.fetchone()

            expected = (
                LOOKUP_NAME,
                MIN_WEIGHT_G,
                MAX_WEIGHT_G,
                SOURCE_TYPE,
                None,
                REVIEW_STATUS,
                True,
            )

            if row != expected:
                raise RuntimeError(
                    f"oats Tune rule verification failed: {row!r}"
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: oats Tune rule is ready "
        "(10-60 g)"
    )


if __name__ == "__main__":
    main()
