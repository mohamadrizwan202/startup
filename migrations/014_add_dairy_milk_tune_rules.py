"""
Complete the reviewed PureFyul V1 dairy-milk Tune family.

Canonical user-facing identities:
- whole milk
- 2% milk
- 1% milk
- skim milk
- lactose-free milk

"Lactose-Free Milk" maps internally to reviewed lactose-free reduced-fat
2% dairy milk.

Canonical nutrition values are per 100 g:

- whole milk
  USDA FoodData Central FDC 171265
  61 kcal, 3.15 protein, 4.80 carbs, 3.25 fat,
  0 fiber, 5.05 total sugar, 43 mg sodium

- 2% milk
  USDA FoodData Central FDC 171267
  50 kcal, 3.30 protein, 4.80 carbs, 1.98 fat,
  0 fiber, 5.06 total sugar, 47 mg sodium

- 1% milk
  USDA FoodData Central FDC 170872
  42 kcal, 3.37 protein, 4.99 carbs, 0.97 fat,
  0 fiber, 5.20 total sugar, 44 mg sodium

- skim milk
  USDA FoodData Central FDC 171269
  34 kcal, 3.37 protein, 4.96 carbs, 0.08 fat,
  0 fiber, 5.09 total sugar, 42 mg sodium

- lactose-free milk
  USDA FoodData Central FNDDS FDC 2705391
  Milk, lactose free, reduced fat (2%)
  50 kcal, 3.36 protein, 4.90 carbs, 1.90 fat,
  0 fiber, 4.89 total sugar, 39 mg sodium

PureFyul V1 user-facing Tune range for every dairy milk:
120-300 mL.

Solver gram bounds use the reviewed ingredient-specific conversions in
recipe_mass.py:

- whole milk:        1.0305 g/mL -> 123.660-309.150 g
- 2% milk:           1.0329 g/mL -> 123.948-309.870 g
- 1% milk:           1.0329 g/mL -> 123.948-309.870 g
- skim milk:         1.0341 g/mL -> 124.092-310.230 g
- lactose-free milk: 1.0313 g/mL -> 123.756-309.390 g

The 120-300 mL limits are PureFyul culinary/product optimization
guardrails, not serving or medical recommendations.

Generic/legacy identities intentionally remain outside Tune:
- milk
- reduced fat milk
- low fat milk
- fat free milk
- lactose free milk
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROWS = (
    ("whole milk", 61.0, 3.15, 4.80, 3.25, 0.0, 5.05, 43.0),
    ("2% milk", 50.0, 3.30, 4.80, 1.98, 0.0, 5.06, 47.0),
    ("1% milk", 42.0, 3.37, 4.99, 0.97, 0.0, 5.20, 44.0),
    ("skim milk", 34.0, 3.37, 4.96, 0.08, 0.0, 5.09, 42.0),
    (
        "lactose-free milk",
        50.0,
        3.36,
        4.90,
        1.90,
        0.0,
        4.89,
        39.0,
    ),
)

RULES = (
    ("whole milk", 123.660, 309.150),
    ("2% milk", 123.948, 309.870),
    ("1% milk", 123.948, 309.870),
    ("skim milk", 124.092, 310.230),
    ("lactose-free milk", 123.756, 309.390),
)

BUILDER_ROWS = (
    (
        "whole milk",
        "Muscle Health",
        "Protein-Rich Foods",
        "Whole dairy milk option",
        "Protein, Calcium",
        "Reviewed V1 whole dairy milk identity.",
    ),
    (
        "2% milk",
        "Muscle Health",
        "Protein-Rich Foods",
        "Reduced-fat dairy milk option",
        "Protein, Calcium",
        "Reviewed V1 2% reduced-fat dairy milk identity.",
    ),
    (
        "1% milk",
        "Muscle Health",
        "Protein-Rich Foods",
        "Low-fat dairy milk option",
        "Protein, Calcium",
        "Reviewed V1 1% low-fat dairy milk identity.",
    ),
    (
        "skim milk",
        "Muscle Health",
        "Protein-Rich Foods",
        "Fat-free dairy milk option",
        "Protein, Calcium",
        "Reviewed V1 skim/fat-free dairy milk identity.",
    ),
    (
        "lactose-free milk",
        "Muscle Health",
        "Protein-Rich Foods",
        "Lactose-free reduced-fat dairy milk option",
        "Protein, Calcium",
        "Reviewed V1 lactose-free 2% dairy milk identity.",
    ),
)

NONCANONICAL_TUNE_IDENTITIES = (
    "milk",
    "reduced fat milk",
    "low fat milk",
    "fat free milk",
    "lactose free milk",
)

SOURCE_TYPE = "purefyul_product_policy"
RATIONALE = (
    "Reviewed PureFyul V1 dairy-milk culinary/product Tune guardrail; "
    "120-300 mL user-facing range; not a serving recommendation."
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


def _verify_noncanonical_identities_fail_closed(cur) -> None:
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
            "Noncanonical dairy-milk identities unexpectedly have enabled "
            f"Tune rules: {rows!r}"
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

            for lookup_name, min_weight_g, max_weight_g in RULES:
                _upsert_rule(
                    cur,
                    lookup_name,
                    min_weight_g,
                    max_weight_g,
                )

            for row in BUILDER_ROWS:
                _ensure_builder_row(cur, row)

            for row in NUTRITION_ROWS:
                _verify_nutrition(cur, row)

            for row in RULES:
                _verify_rule(cur, row)

            for row in BUILDER_ROWS:
                _verify_builder_row(cur, row)

            _verify_noncanonical_identities_fail_closed(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: dairy-milk V1 nutrition, Tune rules, "
        "and builder identities are ready"
    )


if __name__ == "__main__":
    main()
