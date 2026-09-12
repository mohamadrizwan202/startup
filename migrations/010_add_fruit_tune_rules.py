"""
Add reviewed PureFyul V1 Tune rules for the ready whole-fruit family.

These are PureFyul culinary/product tuning guardrails, not serving
recommendations or medical recommendations.

Explicit runtime rules added here:

- blueberry:      30-180 g
- strawberry:     30-180 g
- raspberry:      30-180 g
- blackberry:     30-180 g
- banana:         50-160 g
- pineapple:      30-180 g
- papaya:         30-160 g
- kiwi:           25-150 g
- guava:          40-160 g
- dragon fruit:   40-220 g
- apple:          40-220 g
- peach:          50-220 g
- grapes:         35-200 g
- watermelon:     80-280 g
- honeydew:       40-180 g
- honeydew melon: 40-180 g

Already live and intentionally not recreated here:
- mango: 60-125 g
- blueberries: 30-180 g (legacy/existing compatibility identity)

Fail-closed pending exact production identity/data resolution:
- cantaloupe
- pear / pears
- cherry / cherries
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


RULES = (
    ("blueberry", 30.0, 180.0),
    ("strawberry", 30.0, 180.0),
    ("raspberry", 30.0, 180.0),
    ("blackberry", 30.0, 180.0),
    ("banana", 50.0, 160.0),
    ("pineapple", 30.0, 180.0),
    ("papaya", 30.0, 160.0),
    ("kiwi", 25.0, 150.0),
    ("guava", 40.0, 160.0),
    ("dragon fruit", 40.0, 220.0),
    ("apple", 40.0, 220.0),
    ("peach", 50.0, 220.0),
    ("grapes", 35.0, 200.0),
    ("watermelon", 80.0, 280.0),
    ("honeydew", 40.0, 180.0),
    ("honeydew melon", 40.0, 180.0),
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
        "SUCCESS: 16 PureFyul V1 fruit Tune rules are ready"
    )


if __name__ == "__main__":
    main()
