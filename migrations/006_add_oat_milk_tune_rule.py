"""
Add the reviewed PureFyul V1 Tune rule for oat milk.

Product guardrail:
- user-facing volume range: 70-260 mL
- explicit oat-milk density conversion: 1.0254 g/mL
- solver-facing gram range: 71.778-266.604 g

This is a PureFyul culinary/product tuning guardrail, not a serving
recommendation or medical recommendation.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


LOOKUP_NAME = "oat milk"
MIN_WEIGHT_G = 71.778
MAX_WEIGHT_G = 266.604
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
                    f"oat milk Tune rule verification failed: {row!r}"
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: oat milk Tune rule is ready "
        "(70-260 mL / 71.778-266.604 g)"
    )


if __name__ == "__main__":
    main()
