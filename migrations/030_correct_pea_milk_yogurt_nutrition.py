"""Correct two per-100g nutrition records.

Pea milk:
Ripple Unsweetened Nutritious Pea Milk, original.
Branded reference serving: 240 g.
70 kcal, 8g protein, 0g carbs, 4.5g fat,
0g fiber, 0g sugar, 130mg sodium per serving.
Converted to per 100g.

Yogurt:
USDA FoodData Central FDC 170886,
Yogurt, plain, low fat. Values per 100g.

Source references:
https://www.nutritionvalue.org/Unsweetened_nutritious_pea_milk_by_Ripple_Foods_1658667_nutritional_value.html
https://fdc.nal.usda.gov/food-details/170886/nutrients

Local PostgreSQL only. Explicit --apply-local required.
No insertions, no recipe changes, no quantity changes.
Reject unexpected existing values. Verify before commit.
"""

import math
import sys
from urllib.parse import urlsplit, parse_qsl

COLUMNS = (
    "calories", "protein_g", "carbs_g", "fat_g",
    "fiber_g", "sugar_g", "sodium_g",
)

EXPECTED_OLD = {
    "pea milk": (70, 8, 0, 4.5, 0, 0, 120),
    "yogurt": (59, 10, 3.6, 0.4, 0, 3.6, 36),
}

CORRECTED = {
    "pea milk": (29.17, 3.33, 0, 1.88, 0, 0, 54.17),
    "yogurt": (63, 5.25, 7.04, 1.55, 0, 7.04, 70),
}


def verify_values(actual, expected):
    return all(
        math.isclose(float(a), float(b), rel_tol=0, abs_tol=0.011)
        for a, b in zip(actual, expected)
    )


def main():
    if sys.argv[1:] != ["--apply-local"]:
        raise SystemExit("STOP: Explicit --apply-local required.")

    from dotenv import dotenv_values
    import psycopg

    url = dotenv_values(".env.local").get("DATABASE_URL") or ""
    target = urlsplit(url)

    if not (
        target.scheme in ("postgres", "postgresql")
        and target.hostname == "127.0.0.1"
        and target.port == 5432
        and target.path == "/purefyul"
        and all(k == "sslmode" for k, _ in parse_qsl(target.query))
    ):
        raise SystemExit("STOP: Unexpected database target.")

    with psycopg.connect(url, connect_timeout=5) as conn:
        if conn.info.host != "127.0.0.1" or conn.info.port != 5432:
            raise RuntimeError("Unexpected connection endpoint.")

        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_database(),
                       host(inet_server_addr()),
                       inet_server_port()
            """)

            if cur.fetchone() != ("purefyul", "127.0.0.1", 5432):
                raise RuntimeError("Unexpected PostgreSQL identity.")

            for name, expected in EXPECTED_OLD.items():
                cur.execute("""
                    SELECT ingredient, calories, protein_g, carbs_g,
                           fat_g, fiber_g, sugar_g, sodium_g
                    FROM public.nutrition_facts
                    WHERE LOWER(BTRIM(ingredient)) = %s
                    FOR UPDATE
                """, (name,))

                matches = cur.fetchall()

                if len(matches) != 1:
                    raise RuntimeError(
                        f"{name}: expected exactly one existing record"
                    )

                stored_name = matches[0][0]
                existing = matches[0][1:]

                if not verify_values(existing, expected):
                    raise RuntimeError(
                        f"{name}: existing values differ; no update allowed"
                    )

                assignments = ", ".join(
                    f"{column} = %s" for column in COLUMNS
                )

                cur.execute(
                    f"UPDATE public.nutrition_facts "
                    f"SET {assignments} WHERE ingredient = %s",
                    (*CORRECTED[name], stored_name),
                )

                if cur.rowcount != 1:
                    raise RuntimeError(f"{name}: update count mismatch")

            for name, expected in CORRECTED.items():
                cur.execute("""
                    SELECT calories, protein_g, carbs_g, fat_g,
                           fiber_g, sugar_g, sodium_g
                    FROM public.nutrition_facts
                    WHERE LOWER(BTRIM(ingredient)) = %s
                """, (name,))

                rows = cur.fetchall()

                if len(rows) != 1 or not verify_values(rows[0], expected):
                    raise RuntimeError(
                        f"{name}: post-update verification failed"
                    )

    print("PASS: Two nutrition records corrected locally.")


if __name__ == "__main__":
    main()
