"""Add missing nutrition for reviewed smoothie presets.

Reference nutrition per 100 g:
- Kefir, lowfat, plain, LIFEWAY: FDC 170904
- Seeds, flaxseed: FDC 169414
- Seeds, hemp seed, hulled: USDA FDC 170148
- Lime juice, raw: USDA FDC 168156
- Pumpkin/squash seed kernels, dried: USDA FDC 170556
- Plain nonfat skyr: Siggi's official 150 g nutrition label

Kefir uses plain unsweetened low-fat dairy kefir as its
reference form. Flaxseed can be ground for smoothie preparation.
Hemp seeds refer to hulled seeds, not hemp milk.

Skyr uses rounded per-100g values derived from a branded nutrition label;
these are estimates, not universal skyr values.

The legacy sodium_g column stores milligrams.

Safety:
- Local PostgreSQL only.
- Requires explicit --apply-local.
- Inserts only; never updates existing records.
- Rejects existing or duplicate nutrition identities.
- Verifies inserted values before commit.
"""

from __future__ import annotations

import math
import sys
from urllib.parse import parse_qsl, urlsplit

ROWS = (
    ('kefir', 43.0, 3.79, 4.77, 1.02, 0.0, 4.61, 40.0, 100.0),
    ('flax seeds', 534.0, 18.29, 28.88, 42.16, 27.3, 1.55, 30.0, 100.0),
    ('hemp seeds', 553.0, 31.56, 8.67, 48.75, 4.0, 1.5, 5.0, 100.0),
    ('lime juice', 25.0, 0.42, 8.42, 0.07, 0.4, 1.69, 2.0, 100.0),
    ('pumpkin seeds', 559.0, 30.23, 10.71, 49.05, 6.0, 1.4, 7.0, 100.0),
    ('skyr', 60.0, 10.67, 4.0, 0.0, 0.0, 2.67, 36.67, 100.0),
)

COLUMNS = (
    "ingredient", "calories", "protein_g", "carbs_g",
    "fat_g", "fiber_g", "sugar_g", "sodium_g",
    "serving_size_g",
)


def main():
    if sys.argv[1:] != ["--apply-local"]:
        raise SystemExit("No changes made. Explicit --apply-local required.")

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
        raise SystemExit("STOP: Only local purefyul PostgreSQL permitted.")

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT current_database(),
                       host(inet_server_addr()),
                       inet_server_port()
            """)
            identity = cur.fetchone()

            if identity != ("purefyul", "127.0.0.1", 5432):
                raise RuntimeError("Unexpected PostgreSQL server identity.")

            for row in ROWS:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM public.nutrition_facts
                    WHERE LOWER(BTRIM(ingredient)) = %s
                """, (row[0],))

                if cur.fetchone()[0] != 0:
                    raise RuntimeError(
                        f"{row[0]}: nutrition record already exists"
                    )

            column_sql = ", ".join(COLUMNS)
            placeholders = ", ".join(["%s"] * len(COLUMNS))

            for row in ROWS:
                cur.execute(
                    f"INSERT INTO public.nutrition_facts "
                    f"({column_sql}) VALUES ({placeholders})",
                    row,
                )

            for expected in ROWS:
                cur.execute(f"""
                    SELECT {column_sql}
                    FROM public.nutrition_facts
                    WHERE LOWER(BTRIM(ingredient)) = %s
                """, (expected[0],))

                actual = cur.fetchall()

                if len(actual) != 1:
                    raise RuntimeError(
                        f"{expected[0]}: expected one nutrition record"
                    )

                for value, reference in zip(actual[0], expected):
                    if isinstance(reference, str):
                        if value != reference:
                            raise RuntimeError("Ingredient identity mismatch")
                    elif not math.isclose(
                        float(value), reference,
                        rel_tol=0, abs_tol=0.00001
                    ):
                        raise RuntimeError(
                            f"{expected[0]}: nutrition verification failed"
                        )

    print("PASS: Six nutrition records committed locally.")


if __name__ == "__main__":
    main()
