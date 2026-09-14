"""
Complete PureFyul V1 Whole Nuts Tune support.

Canonical runtime identities:
- almonds
- walnuts
- cashews
- pecans
- pistachios

USDA FoodData Central SR Legacy identities:
- almonds: FDC 170567
- walnuts, English: FDC 170187
- cashew nuts, raw: FDC 170162
- pecans: FDC 170182
- pistachio nuts, raw: FDC 170184

Existing PureFyul serving metadata retained:
- 28 g for all five

PureFyul V1 product Tune guardrails:
- almonds: 5-35 g
- walnuts: 5-30 g
- cashews: 5-35 g
- pecans: 5-30 g
- pistachios: 5-35 g

These are culinary/product optimization guardrails,
not serving or medical recommendations.

Singular aliases remain outside Tune.
Nut milks, butters, and oils are separate identities.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROWS = (
    ("almonds", 579.0, 21.15, 21.55, 49.93, 12.50, 4.35, 1.0, 28.0),
    ("walnuts", 654.0, 15.23, 13.71, 65.21, 6.70, 2.61, 2.0, 28.0),
    ("cashews", 553.0, 18.22, 30.19, 43.85, 3.30, 5.91, 12.0, 28.0),
    ("pecans", 691.0, 9.17, 13.86, 71.97, 9.60, 3.97, 0.0, 28.0),
    ("pistachios", 560.0, 20.16, 27.17, 45.32, 10.60, 7.66, 1.0, 28.0),
)

RULES = (
    ("almonds", 5.0, 35.0),
    ("walnuts", 5.0, 30.0),
    ("cashews", 5.0, 35.0),
    ("pecans", 5.0, 30.0),
    ("pistachios", 5.0, 35.0),
)

NONCANONICAL_ALIASES = (
    "almond",
    "walnut",
    "cashew",
    "pecan",
    "pistachio",
)

SOURCE_TYPE = "purefyul_product_policy"
REVIEW_STATUS = "approved"
RATIONALE = (
    "Reviewed PureFyul V1 whole-nut culinary/product Tune "
    "guardrails; not serving or medical recommendations."
)


def _update_nutrition(cur, expected):
    ingredient = expected[0]

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
            f"{ingredient}: expected exactly one canonical "
            f"nutrition row, got {matches!r}"
        )

    cur.execute(
        """
        UPDATE public.nutrition_facts
        SET calories = %s,
            protein_g = %s,
            carbs_g = %s,
            fat_g = %s,
            fiber_g = %s,
            sugar_g = %s,
            sodium_g = %s,
            serving_size_g = %s
        WHERE ingredient = %s
        """,
        (*expected[1:], matches[0][0]),
    )


def _upsert_rule(cur, rule):
    name, minimum, maximum = rule

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
            name,
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
        SELECT ingredient, calories, protein_g, carbs_g,
               fat_g, fiber_g, sugar_g, sodium_g,
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
            f"{ingredient}: nutrition verification row count "
            f"failed: {rows!r}"
        )

    actual = rows[0]

    if actual[0].strip().lower() != ingredient:
        raise RuntimeError(
            f"{ingredient}: unexpected identity {actual[0]!r}"
        )

    for actual_value, expected_value in zip(
        actual[1:], expected[1:]
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


def _verify_rule(cur, expected):
    name, minimum, maximum = expected

    cur.execute(
        """
        SELECT nutrition_lookup_name,
               min_weight_g,
               max_weight_g,
               source_type,
               source_reference,
               review_status,
               enabled
        FROM public.ingredient_tuning_rules
        WHERE LOWER(BTRIM(nutrition_lookup_name)) = %s
        """,
        (name,),
    )
    rows = cur.fetchall()

    if len(rows) != 1:
        raise RuntimeError(
            f"{name}: expected exactly one Tune rule, "
            f"got {rows!r}"
        )

    row = rows[0]

    if row[0].strip().lower() != name:
        raise RuntimeError(
            f"{name}: unexpected Tune identity {row[0]!r}"
        )

    if not math.isclose(float(row[1]), minimum, abs_tol=1e-6):
        raise RuntimeError(f"{name}: wrong minimum Tune bound")

    if not math.isclose(float(row[2]), maximum, abs_tol=1e-6):
        raise RuntimeError(f"{name}: wrong maximum Tune bound")

    if row[3:] != (
        SOURCE_TYPE,
        None,
        REVIEW_STATUS,
        True,
    ):
        raise RuntimeError(
            f"{name}: Tune metadata verification failed: {row!r}"
        )


def _verify_builder(cur, ingredient):
    cur.execute(
        """
        SELECT COUNT(*)
        FROM public.ingredient_categories
        WHERE LOWER(BTRIM(ingredient)) = %s
        """,
        (ingredient,),
    )

    if cur.fetchone()[0] < 1:
        raise RuntimeError(
            f"{ingredient}: canonical builder identity missing"
        )


def _verify_aliases_fail_closed(cur):
    cur.execute(
        """
        SELECT nutrition_lookup_name
        FROM public.ingredient_tuning_rules
        WHERE LOWER(BTRIM(nutrition_lookup_name)) = ANY(%s)
          AND enabled = TRUE
        ORDER BY nutrition_lookup_name
        """,
        (list(NONCANONICAL_ALIASES),),
    )
    rows = cur.fetchall()

    if rows:
        raise RuntimeError(
            "Noncanonical whole-nut aliases must remain "
            f"outside Tune: {rows!r}"
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

            for rule in RULES:
                _upsert_rule(cur, rule)

            for row in NUTRITION_ROWS:
                _verify_nutrition(cur, row)

            for rule in RULES:
                _verify_rule(cur, rule)

            for ingredient, *_ in NUTRITION_ROWS:
                _verify_builder(cur, ingredient)

            _verify_aliases_fail_closed(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: whole-nuts V1 nutrition and Tune rules are ready"
    )


if __name__ == "__main__":
    main()
