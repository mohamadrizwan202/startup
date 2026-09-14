"""
Complete the reviewed PureFyul V1 nut-butter Tune family.

Canonical runtime identities:
- peanut butter
- almond butter

Exact nutrition values per 100 g:

Peanut butter
USDA FoodData Central SR Legacy FDC 172470
Peanut butter, smooth style, without salt
598 kcal, 22.21 g protein, 22.31 g carbs, 51.36 g fat,
5.00 g fiber, 10.49 g total sugar, 17 mg sodium.

Almond butter
USDA FoodData Central SR Legacy FDC 168588
Nuts, almond butter, plain, without salt added
614 kcal, 20.96 g protein, 18.82 g carbs, 55.50 g fat,
10.30 g fiber, 4.43 g total sugar, 7 mg sodium.

Existing PureFyul household metadata retained:
- peanut butter: 32 g
- almond butter: 16 g

PureFyul V1 culinary/product Tune guardrails:
- peanut butter: 8-40 g
- almond butter: 8-40 g

These Tune ranges are product optimization guardrails, not
medical or serving recommendations.

Both canonical builder identities already exist in production.
This migration verifies them rather than creating duplicates.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROWS = (
    (
        "peanut butter",
        598.0,
        22.21,
        22.31,
        51.36,
        5.00,
        10.49,
        17.0,
        32.0,
    ),
    (
        "almond butter",
        614.0,
        20.96,
        18.82,
        55.50,
        10.30,
        4.43,
        7.0,
        16.0,
    ),
)

RULES = (
    ("peanut butter", 8.0, 40.0),
    ("almond butter", 8.0, 40.0),
)

SOURCE_TYPE = "purefyul_product_policy"
REVIEW_STATUS = "approved"
RATIONALE = (
    "Reviewed PureFyul V1 nut-butter culinary/product Tune "
    "guardrail; 8-40 g; not a serving recommendation."
)


def _update_nutrition(cur, row):
    ingredient = row[0]

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
        (*row[1:], stored_name),
    )


def _upsert_rule(cur, row):
    lookup_name, minimum, maximum = row

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


def _verify_nutrition(cur, expected):
    ingredient = expected[0]

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

    for actual_value, expected_value in zip(actual[1:], expected[1:]):
        if not math.isclose(
            float(actual_value),
            float(expected_value),
            rel_tol=0.0,
            abs_tol=1e-5,
        ):
            raise RuntimeError(
                f"{ingredient}: nutrition verification failed; "
                f"actual={actual!r}, expected={expected!r}"
            )


def _verify_rule(cur, expected):
    lookup_name, minimum, maximum = expected

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

    expected_row = (
        lookup_name,
        minimum,
        maximum,
        SOURCE_TYPE,
        None,
        REVIEW_STATUS,
        True,
    )

    if row != expected_row:
        raise RuntimeError(
            f"{lookup_name}: Tune rule verification failed: {row!r}"
        )


def _verify_builder_identity(cur, ingredient):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM public.ingredient_categories
        WHERE LOWER(BTRIM(ingredient)) = %s
        """,
        (ingredient,),
    )
    count = cur.fetchone()[0]

    if count < 1:
        raise RuntimeError(
            f"{ingredient}: canonical builder identity is missing"
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
            for row in NUTRITION_ROWS:
                _update_nutrition(cur, row)

            for row in RULES:
                _upsert_rule(cur, row)

            for row in NUTRITION_ROWS:
                _verify_nutrition(cur, row)

            for row in RULES:
                _verify_rule(cur, row)

            for ingredient, _minimum, _maximum in RULES:
                _verify_builder_identity(cur, ingredient)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: nut-butter V1 nutrition and Tune rules are ready"
    )


if __name__ == "__main__":
    main()
