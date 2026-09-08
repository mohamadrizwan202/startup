"""
Initial Tune My Smoothie ingredient-policy migration.

Purpose:
- Apply the existing ingredient_tuning_rules schema.
- Seed only the currently buildable, reviewed V1 Tune ingredients.
- Keep ingredient bounds as PureFyul culinary/product guardrails.
- Do not represent these ranges as serving recommendations.

Run once on production PostgreSQL via Render Shell:

    cd /opt/render/project/src
    python migrations/005_tune_ingredient_policy.py
"""

from pathlib import Path
import os
import sys

import psycopg


SCHEMA_FILE = (
    Path(__file__).resolve().parent
    / "2026_08_30_create_ingredient_tuning_rules.sql"
)


RULES = [
    ("blueberries", 30.0, 180.0),
    ("mango", 60.0, 125.0),
    ("spinach", 10.0, 75.0),
    ("chia seed", 5.0, 25.0),
    ("greek yogurt", 50.0, 250.0),
]


def normalize_pg_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def run_migration():
    db_url = os.environ.get("DATABASE_URL", "").strip()

    if not db_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    if not SCHEMA_FILE.exists():
        print(f"ERROR: schema migration not found: {SCHEMA_FILE}")
        sys.exit(1)

    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    conn = psycopg.connect(normalize_pg_url(db_url))

    try:
        cur = conn.cursor()

        # Existing reviewed schema is authoritative.
        cur.execute(schema_sql)

        for lookup_name, minimum, maximum in RULES:
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
                    'purefyul_product_policy',
                    NULL,
                    'Reviewed PureFyul V1 culinary/product Tune guardrail; '
                    'not a serving recommendation.',
                    'approved',
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
                (lookup_name, minimum, maximum),
            )

        cur.execute(
            """
            SELECT
                nutrition_lookup_name,
                min_weight_g,
                max_weight_g,
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
            row[0]: (
                float(row[1]),
                float(row[2]),
                row[3],
                bool(row[4]),
            )
            for row in rows
        }

        expected = {
            name: (minimum, maximum, "approved", True)
            for name, minimum, maximum in RULES
        }

        if actual != expected:
            raise RuntimeError(
                "Tune ingredient-policy verification failed: "
                f"expected={expected!r} actual={actual!r}"
            )

        conn.commit()

        print(
            "SUCCESS: ingredient_tuning_rules schema and "
            "5 reviewed Tune rules are ready"
        )

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
