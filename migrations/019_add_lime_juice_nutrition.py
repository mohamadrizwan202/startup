"""
Add the reviewed canonical lime-juice nutrition identity.

Source:
USDA FoodData Central SR Legacy
Lime juice, raw — FDC 168156

Canonical nutrition per 100 g:
- 25 kcal
- 0.42 g protein
- 8.42 g carbohydrate
- 0.07 g fat
- 0.40 g fiber
- 1.69 g total sugar
- 2 mg sodium

This migration adds nutrition data only.
It does not add Tune rules, serving recommendations,
builder identities, or preset recipe logic.
"""

from __future__ import annotations

import math
import os

import psycopg
from dotenv import load_dotenv


NUTRITION_ROW = (
    "lime juice",
    25.0,
    0.42,
    8.42,
    0.07,
    0.40,
    1.69,
    2.0,
    100.0,
)


def _upsert_nutrition(cur) -> None:
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
            (*NUTRITION_ROW[1:], stored_name),
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
            NUTRITION_ROW,
        )


def _verify_nutrition(cur) -> None:
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
            f"{ingredient}: expected exactly one nutrition row, got {rows!r}"
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
            _upsert_nutrition(cur)
            _verify_nutrition(cur)

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(
        "SUCCESS: canonical lime juice nutrition is ready"
    )


if __name__ == "__main__":
    main()
