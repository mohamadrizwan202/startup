"""
Complete the reviewed PureFyul V1 smoothie booster seed family.

Already live and intentionally untouched:
- chia seed: 5-25 g

Canonical runtime identities added here:
- flax seeds
- hemp seeds
- pumpkin seeds

Canonical nutrition, all values per 100 g:

Flax seeds
USDA FoodData Central SR Legacy FDC 169414
534 kcal, 18.29 protein, 28.88 carbs, 42.16 fat,
27.30 fiber, 1.55 total sugar, 30 mg sodium

Hemp seeds
USDA FoodData Central SR Legacy FDC 170148
Seeds, hemp seed, hulled
553 kcal, 31.56 protein, 8.67 carbs, 48.75 fat,
4.00 fiber, 1.50 total sugar, 5 mg sodium

Pumpkin seeds
USDA FoodData Central SR Legacy FDC 170556
Seeds, pumpkin and squash seed kernels, dried
559 kcal, 30.23 protein, 10.71 carbs, 49.05 fat,
6.00 fiber, 1.40 total sugar, 7 mg sodium

PureFyul culinary/product Tune guardrails:
- flax seeds: 5-25 g
- hemp seeds: 5-30 g
- pumpkin seeds: 5-30 g

These are optimization guardrails, not serving or medical
recommendations.

Singular aliases and display labels intentionally do not receive
independent Tune rules.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROWS = (
    (
        "flax seeds",
        534.0,
        18.29,
        28.88,
        42.16,
        27.30,
        1.55,
        30.0,
        7.0,
    ),
    (
        "hemp seeds",
        553.0,
        31.56,
        8.67,
        48.75,
        4.00,
        1.50,
        5.0,
        30.0,
    ),
    (
        "pumpkin seeds",
        559.0,
        30.23,
        10.71,
        49.05,
        6.00,
        1.40,
        7.0,
        28.0,
    ),
)

RULES = (
    ("flax seeds", 5.0, 25.0),
    ("hemp seeds", 5.0, 30.0),
    ("pumpkin seeds", 5.0, 30.0),
)

BUILDER_ROWS = (
    (
        "flax seeds",
        "Heart Health",
        "Nuts & Seeds",
        "Ground flax smoothie add-in",
        "Omega-3, Fiber, Lignans",
        "Flax seeds are commonly added ground for better blending.",
    ),
    (
        "hemp seeds",
        "Muscle Health",
        "Plant-Based Protein Sources",
        "Plant protein smoothie add-in",
        "Protein, Omega-3, Magnesium",
        "Hemp seeds add plant protein and healthy fats to smoothies.",
    ),
    (
        "pumpkin seeds",
        "Muscle Health",
        "Plant-Based Protein Sources",
        "Mineral-rich smoothie add-in",
        "Protein, Magnesium, Zinc",
        "Pumpkin seeds add protein, zinc, and magnesium.",
    ),
)

NONCANONICAL_TUNE_IDENTITIES = (
    "flax seed",
    "flaxseed",
    "hemp seed",
    "hemp hearts",
    "pumpkin seed",
)

SOURCE_TYPE = "purefyul_product_policy"
RATIONALE = (
    "Reviewed PureFyul V1 smoothie-booster culinary/product Tune "
    "guardrail; not a serving recommendation."
)
REVIEW_STATUS = "approved"


def _upsert_nutrition(cur, row) -> None:
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

    if len(matches) > 1:
        raise RuntimeError(
            f"{ingredient}: multiple normalized nutrition rows exist"
        )

    if matches:
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
    else:
        cur.execute(
            """
            INSERT INTO public.nutrition_facts (
                ingredient,
                calories,
                protein_g,
                carbs_g,
                fat_g,
                fiber_g,
                sugar_g,
                sodium_g,
                serving_size_g
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            row,
        )


def _upsert_rule(cur, row) -> None:
    lookup_name, min_weight_g, max_weight_g = row

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
            min_weight_g,
            max_weight_g,
            SOURCE_TYPE,
            RATIONALE,
            REVIEW_STATUS,
        ),
    )


def _ensure_builder_row(cur, row) -> None:
    ingredient, category, subcategory, *_ = row

    cur.execute(
        """
        SELECT COUNT(*)
        FROM public.ingredient_categories
        WHERE LOWER(BTRIM(ingredient)) = %s
          AND category = %s
          AND subcategory = %s
        """,
        (ingredient, category, subcategory),
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
            row,
        )
    elif count > 1:
        raise RuntimeError(
            f"{ingredient}: duplicate canonical builder rows exist: {count}"
        )


def _verify_nutrition(cur, expected) -> None:
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
            f"{ingredient}: expected exactly one nutrition row, got {rows!r}"
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


def _verify_rule(cur, expected) -> None:
    lookup_name, min_weight_g, max_weight_g = expected

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
        min_weight_g,
        max_weight_g,
        SOURCE_TYPE,
        None,
        REVIEW_STATUS,
        True,
    )

    if row != expected_row:
        raise RuntimeError(
            f"{lookup_name}: Tune rule verification failed: {row!r}"
        )


def _verify_builder_row(cur, expected) -> None:
    ingredient, category, subcategory, *_ = expected

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
        WHERE LOWER(BTRIM(ingredient)) = %s
          AND category = %s
          AND subcategory = %s
        """,
        (ingredient, category, subcategory),
    )

    rows = cur.fetchall()

    if rows != [expected]:
        raise RuntimeError(
            f"{ingredient}: builder verification failed: {rows!r}"
        )


def _verify_noncanonical_fail_closed(cur) -> None:
    cur.execute(
        """
        SELECT nutrition_lookup_name
        FROM public.ingredient_tuning_rules
        WHERE LOWER(BTRIM(nutrition_lookup_name)) = ANY(%s)
          AND enabled = TRUE
        ORDER BY nutrition_lookup_name
        """,
        (list(NONCANONICAL_TUNE_IDENTITIES),),
    )

    rows = cur.fetchall()

    if rows:
        raise RuntimeError(
            "Noncanonical booster identities unexpectedly Tune-enabled: "
            f"{rows!r}"
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
            for row in NUTRITION_ROWS:
                _upsert_nutrition(cur, row)

            for row in RULES:
                _upsert_rule(cur, row)

            for row in BUILDER_ROWS:
                _ensure_builder_row(cur, row)

            for row in NUTRITION_ROWS:
                _verify_nutrition(cur, row)

            for row in RULES:
                _verify_rule(cur, row)

            for row in BUILDER_ROWS:
                _verify_builder_row(cur, row)

            _verify_noncanonical_fail_closed(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: booster-seed V1 nutrition, Tune rules, "
        "and builder identities are ready"
    )


if __name__ == "__main__":
    main()
