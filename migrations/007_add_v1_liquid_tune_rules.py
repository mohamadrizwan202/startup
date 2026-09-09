"""
Add reviewed PureFyul V1 Tune rules for six liquid ingredients.

Plant-milk product guardrail:
- user-facing range: 70-260 mL

Coconut-water product guardrail:
- user-facing range: 100-240 mL

Solver-facing gram bounds are derived from the explicit liquid mass
conversions already registered in recipe_mass.py.

These are PureFyul culinary/product tuning guardrails, not serving
recommendations or medical recommendations.
"""

from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv


SOURCE_TYPE = "purefyul_product_policy"
REVIEW_STATUS = "approved"
RATIONALE = (
    "Reviewed PureFyul V1 culinary/product Tune guardrail; "
    "not a serving recommendation."
)

RULES = [
    ("soy milk", 70.931, 263.458),
    ("almond milk", 70.014, 260.052),
    ("rice milk", 73.472, 272.896),
    ("macadamia milk", 69.370, 257.660),
    ("cashew milk", 72.100, 267.800),
    ("coconut water", 102.000, 244.800),
]


def main() -> None:
    load_dotenv(".env")

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is required")

    conn = psycopg.connect(database_url)

    try:
        with conn.cursor() as cur:
            for (
                lookup_name,
                min_weight_g,
                max_weight_g,
            ) in RULES:
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
                WHERE nutrition_lookup_name = ANY(%s)
                ORDER BY nutrition_lookup_name
                """,
                ([rule[0] for rule in RULES],),
            )

            rows = cur.fetchall()

            actual = {
                row[0]: row
                for row in rows
            }

            if len(actual) != len(RULES):
                raise RuntimeError(
                    "V1 liquid Tune rule verification failed: "
                    f"expected {len(RULES)} rows, got {len(actual)}"
                )

            for (
                lookup_name,
                min_weight_g,
                max_weight_g,
            ) in RULES:
                expected = (
                    lookup_name,
                    min_weight_g,
                    max_weight_g,
                    SOURCE_TYPE,
                    None,
                    REVIEW_STATUS,
                    True,
                )

                if actual.get(lookup_name) != expected:
                    raise RuntimeError(
                        "V1 liquid Tune rule verification failed "
                        f"for {lookup_name!r}: "
                        f"{actual.get(lookup_name)!r}"
                    )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: 6 reviewed V1 liquid Tune rules are ready"
    )


if __name__ == "__main__":
    main()
