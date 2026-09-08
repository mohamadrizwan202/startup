"""Exact nutrition_facts lookup for deterministic smoothie nutrition.

This repository performs database retrieval only.

Lookup behavior is deliberately strict:
- case-insensitive exact ingredient-name match;
- surrounding whitespace is ignored;
- no LIKE/substring/fuzzy search;
- no implicit plural/singular conversion;
- no alias-table lookup;
- no fallback nutrition values;
- no serving-size scaling.

Ingredient identity normalization belongs upstream. Returned database rows are
normalized through nutrition_facts_adapter before reaching calculation code.
"""

from __future__ import annotations

import db

from nutrition_facts_adapter import adapt_nutrition_facts_row


class NutritionFactsLookupError(ValueError):
    """Raised when an exact nutrition lookup cannot satisfy its contract."""


def _validate_lookup_name(value) -> str:
    if not isinstance(value, str):
        raise NutritionFactsLookupError(
            "ingredient must be a string"
        )

    ingredient = value.strip()

    if not ingredient:
        raise NutritionFactsLookupError(
            "ingredient must be a non-empty string"
        )

    return ingredient


def get_nutrition_facts_exact(ingredient) -> dict | None:
    """Return strict per-100g nutrition for one exact ingredient name.

    Matching is case-insensitive and ignores surrounding whitespace only.

    Returns ``None`` when no exact nutrition_facts row exists.

    More than one normalized database match is treated as a data-integrity
    error rather than silently choosing one row.
    """

    lookup_name = _validate_lookup_name(ingredient)

    if db.USE_POSTGRES:
        backend = "postgres"

        sql = """
            SELECT
                ingredient,
                calories,
                protein_g,
                carbs_g,
                fat_g,
                fiber_g,
                sugar_g,
                sodium_g
            FROM nutrition_facts
            WHERE LOWER(TRIM(ingredient)) = LOWER(TRIM(?))
            ORDER BY ingredient
            LIMIT 2
        """
    else:
        backend = "sqlite"

        sql = """
            SELECT
                ingredient,
                calories_per_100g,
                protein,
                carbs,
                fat,
                fiber,
                sugar,
                sodium
            FROM nutrition_facts
            WHERE LOWER(TRIM(ingredient)) = LOWER(TRIM(?))
            ORDER BY ingredient
            LIMIT 2
        """

    conn = db.get_conn()
    cursor = None

    try:
        cursor = conn.cursor()
        cursor.execute(
            db.prepare_query(sql),
            (lookup_name,),
        )

        rows = cursor.fetchall()

        if not rows:
            return None

        if len(rows) > 1:
            raise NutritionFactsLookupError(
                "multiple nutrition_facts rows match the exact ingredient name"
            )

        return adapt_nutrition_facts_row(
            rows[0],
            backend=backend,
        )

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
