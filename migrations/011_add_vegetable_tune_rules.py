"""
Add reviewed PureFyul V1 Tune rules for the ready vegetables/greens family.

These are PureFyul culinary/product tuning guardrails, not serving
recommendations or medical recommendations.

Explicit runtime rules added here:

- kale:             25-90 g
- romaine lettuce:  30-150 g
- cucumber:         25-180 g
- celery:           20-120 g
- broccoli:         20-90 g
- cauliflower:      25-110 g
- carrots:          25-140 g
- beets:            15-125 g

Already live and intentionally not recreated here:
- spinach: 10-75 g

Identity decisions:
- "romaine lettuce" is the verified production nutrition identity.
- "carrots" is the verified production nutrition identity; "carrot" remains
  fail-closed because no exact nutrition row exists.
- "beets" is the verified production nutrition identity.
- "beet greens" is a different ingredient and is not assigned the beet rule.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


RULES = (
    ("kale", 25.0, 90.0),
    ("romaine lettuce", 30.0, 150.0),
    ("cucumber", 25.0, 180.0),
    ("celery", 20.0, 120.0),
    ("broccoli", 20.0, 90.0),
    ("cauliflower", 25.0, 110.0),
    ("carrots", 25.0, 140.0),
    ("beets", 15.0, 125.0),
)

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
            for lookup_name, min_weight_g, max_weight_g in RULES:
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
                        lookup_name,
                        min_weight_g,
                        max_weight_g,
                        SOURCE_TYPE,
                        RATIONALE,
                        REVIEW_STATUS,
                    ),
                )

            for lookup_name, min_weight_g, max_weight_g in RULES:
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
                    (lookup_name,),
                )

                row = cur.fetchone()

                expected = (
                    lookup_name,
                    min_weight_g,
                    max_weight_g,
                    SOURCE_TYPE,
                    None,
                    REVIEW_STATUS,
                    True,
                )

                if row != expected:
                    raise RuntimeError(
                        f"{lookup_name} Tune rule verification failed: {row!r}"
                    )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: 8 PureFyul V1 vegetable/greens Tune rules are ready"
    )


if __name__ == "__main__":
    main()
