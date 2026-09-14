"""
Complete PureFyul V1 Avocado Tune support.

Canonical runtime identity:
- avocado

Exact nutrition per 100 g:
USDA FoodData Central SR Legacy FDC 171705
Avocados, raw, all commercial varieties

160 kcal
2.00 g protein
8.53 g carbohydrate
14.66 g fat
6.70 g fiber
0.66 g total sugar
7 mg sodium

Existing PureFyul serving metadata retained:
- 150 g

PureFyul V1 culinary/product Tune guardrail:
- avocado: 20-160 g

The Tune range is a product optimization guardrail,
not a medical or serving recommendation.

Existing builder identities are verified and not duplicated.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROW = (
    "avocado",
    160.0,
    2.00,
    8.53,
    14.66,
    6.70,
    0.66,
    7.0,
    150.0,
)

RULE = (
    "avocado",
    20.0,
    160.0,
)

SOURCE_TYPE = "purefyul_product_policy"
REVIEW_STATUS = "approved"
RATIONALE = (
    "Reviewed PureFyul V1 avocado culinary/product Tune "
    "guardrail; 20-160 g; not a serving recommendation."
)


def _update_nutrition(cur):
    ingredient = NUTRITION_ROW[0]

    cur.execute(
        """
        SELECT ingredient
        FROM public.nutrition_facts
        WHERE LOWER(BTRIM(ingredient)) = %s
        ORDER BY ingredient
        """,
        (ingredient,),
    )
    matches = cur.fetchall()

    if len(matches) != 1:
        raise RuntimeError(
            f"{ingredient}: expected exactly one existing nutrition row, "
            f"got {matches!r}"
        )

    stored_name = matches[0][0]

    cur.execute(
        """
        UPDATE public.nutrition_facts
        SET
            calories = %s,
            protein_g = %s,
            carbs_g = %s,
            fat_g = %s,
            fiber_g = %s,
            sugar_g = %s,
            sodium_g = %s,
            serving_size_g = %s
        WHERE ingredient = %s
        """,
        (*NUTRITION_ROW[1:], stored_name),
    )


def _upsert_rule(cur):
    lookup_name, minimum, maximum = RULE

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
        VALUES (%s, %s, %s, %s, NULL, %s, %s, TRUE)
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
            minimum,
            maximum,
            SOURCE_TYPE,
            RATIONALE,
            REVIEW_STATUS,
        ),
    )


def _verify_nutrition(cur):
    ingredient = NUTRITION_ROW[0]

    cur.execute(
        """
        SELECT
            ingredient,
            calories,
            protein_g,
            carbs_g,
            fat_g,
            fiber_g,
            sugar_g,
            sodium_g,
            serving_size_g
        FROM public.nutrition_facts
        WHERE LOWER(BTRIM(ingredient)) = %s
        ORDER BY ingredient
        """,
        (ingredient,),
    )
    rows = cur.fetchall()

    if len(rows) != 1:
        raise RuntimeError(
            f"{ingredient}: expected one nutrition row, got {rows!r}"
        )

    actual = rows[0]

    if actual[0].strip().lower() != ingredient:
        raise RuntimeError(
            f"{ingredient}: unexpected stored identity {actual[0]!r}"
        )

    for actual_value, expected_value in zip(
        actual[1:],
        NUTRITION_ROW[1:],
    ):
        if not math.isclose(
            float(actual_value),
            float(expected_value),
            rel_tol=0.0,
            abs_tol=1e-5,
        ):
            raise RuntimeError(
                f"{ingredient}: nutrition verification failed; "
                f"actual={actual!r}, expected={NUTRITION_ROW!r}"
            )


def _verify_rule(cur):
    lookup_name, minimum, maximum = RULE

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
        minimum,
        maximum,
        SOURCE_TYPE,
        None,
        REVIEW_STATUS,
        True,
    )

    if row != expected:
        raise RuntimeError(
            f"{lookup_name}: Tune rule verification failed: {row!r}"
        )


def _verify_builder(cur):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM public.ingredient_categories
        WHERE LOWER(BTRIM(ingredient)) = 'avocado'
        """
    )
    count = cur.fetchone()[0]

    if count < 1:
        raise RuntimeError(
            "avocado: canonical builder identity is missing"
        )


def _verify_no_avocado_oil_rule(cur):
    cur.execute(
        """
        SELECT nutrition_lookup_name
        FROM public.ingredient_tuning_rules
        WHERE LOWER(BTRIM(nutrition_lookup_name)) = 'avocado oil'
          AND enabled = TRUE
        """
    )
    rows = cur.fetchall()

    if rows:
        raise RuntimeError(
            f"avocado oil must remain outside Avocado V1 Tune: {rows!r}"
        )


def main():
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
            _update_nutrition(cur)
            _upsert_rule(cur)

            _verify_nutrition(cur)
            _verify_rule(cur)
            _verify_builder(cur)
            _verify_no_avocado_oil_rule(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: avocado V1 nutrition and Tune rule are ready"
    )


if __name__ == "__main__":
    main()
