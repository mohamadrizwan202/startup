"""
Complete the reviewed PureFyul V1 cultured-dairy Tune family.

This migration intentionally leaves the existing Greek-yogurt identity
and its existing 50-250 g Tune rule untouched.

Canonical nutrition identities, all values per 100 g:

- yogurt
  USDA FoodData Central FDC 171284, Yogurt, plain, whole milk
  61 kcal, 3.47 protein, 4.66 carbs, 3.25 fat,
  0 fiber, 4.66 total sugar, 46 mg sodium

- skyr
  Danish Frida Food ID 1693, Skyr, 0.2 % fat
  70 kcal, 11.0 protein, 6.05 carbohydrate by difference,
  0.20 fat, 0 fiber, 4.00 total sugars, 45 mg sodium

- kefir
  Danish Frida Food ID 1153,
  Milk, 1.5 % fat, cultured, kefir
  48 kcal, 3.5 protein, 4.8 carbs, 1.6 fat,
  0 fiber, 3.78 total sugars, 43 mg sodium

PureFyul Tune product guardrails:

- yogurt: 50-220 g
- skyr:   50-250 g
- kefir:  92.700-257.500 g

Kefir's user-facing volume range is 90-250 mL and is converted by
recipe_mass.py using the separately reviewed fixed V1 density
1.0300 g/mL.

These are culinary/product optimization guardrails, not serving or
medical recommendations.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROWS = (
    (
        "yogurt",
        61.0,
        3.47,
        4.66,
        3.25,
        0.0,
        4.66,
        46.0,
    ),
    (
        "skyr",
        70.0,
        11.0,
        6.05,
        0.20,
        0.0,
        4.00,
        45.0,
    ),
    (
        "kefir",
        48.0,
        3.5,
        4.8,
        1.6,
        0.0,
        3.78,
        43.0,
    ),
)

RULES = (
    ("yogurt", 50.0, 220.0),
    ("skyr", 50.0, 250.0),
    ("kefir", 92.700, 257.500),
)

SOURCE_TYPE = "purefyul_product_policy"
RATIONALE = (
    "Reviewed PureFyul V1 culinary/product Tune guardrail; "
    "not a serving recommendation."
)
REVIEW_STATUS = "approved"


SKYR_BUILDER_ROW = (
    "skyr",
    "Muscle Health",
    "Protein-Rich Foods",
    "High-protein cultured dairy option",
    "Protein",
    "Reviewed V1 Skyr nutrition provides 11 g protein per 100 g.",
)



def _ensure_skyr_builder_identity(cur) -> None:
    (
        ingredient,
        category,
        subcategory,
        health_benefits,
        key_nutrients,
        description,
    ) = SKYR_BUILDER_ROW

    cur.execute(
        """
        SELECT 1
        FROM public.ingredient_categories
        WHERE LOWER(BTRIM(ingredient)) = %s
          AND category = %s
          AND subcategory = %s
        LIMIT 1
        """,
        (ingredient, category, subcategory),
    )

    if cur.fetchone() is None:
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
            SKYR_BUILDER_ROW,
        )


def _upsert_nutrition(cur, row) -> None:
    (
        ingredient,
        calories,
        protein,
        carbs,
        fat,
        fiber,
        sugar,
        sodium,
    ) = row

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
            f"{ingredient}: multiple normalized nutrition_facts rows exist"
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
                sodium_g = %s
            WHERE ingredient = %s
            """,
            (
                calories,
                protein,
                carbs,
                fat,
                fiber,
                sugar,
                sodium,
                stored_name,
            ),
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
                sodium_g
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            row,
        )


def _upsert_rule(
    cur,
    lookup_name: str,
    min_weight_g: float,
    max_weight_g: float,
) -> None:
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
            sodium_g
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

    for actual_value, expected_value in zip(
        actual[1:],
        expected[1:],
    ):
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

    if row is None:
        raise RuntimeError(
            f"{lookup_name}: Tune rule is missing after migration"
        )

    if row[0].strip().lower() != lookup_name:
        raise RuntimeError(
            f"{lookup_name}: wrong stored Tune identity {row[0]!r}"
        )

    if not math.isclose(
        float(row[1]),
        min_weight_g,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise RuntimeError(
            f"{lookup_name}: minimum Tune bound verification failed"
        )

    if not math.isclose(
        float(row[2]),
        max_weight_g,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise RuntimeError(
            f"{lookup_name}: maximum Tune bound verification failed"
        )

    if row[3:] != (
        SOURCE_TYPE,
        None,
        REVIEW_STATUS,
        True,
    ):
        raise RuntimeError(
            f"{lookup_name}: Tune metadata verification failed: {row!r}"
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

            for rule in RULES:
                _upsert_rule(cur, *rule)

            for row in NUTRITION_ROWS:
                _verify_nutrition(cur, row)

            for rule in RULES:
                _verify_rule(cur, rule)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: cultured dairy V1 nutrition and Tune rules are ready "
        "(yogurt, skyr, kefir)"
    )


if __name__ == "__main__":
    main()
