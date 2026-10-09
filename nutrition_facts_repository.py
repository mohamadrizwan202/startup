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

from copy import deepcopy
from time import monotonic

import db

from nutrition_facts_adapter import adapt_nutrition_facts_row


_POSTGRES_EXACT_CACHE_TTL_SECONDS = 300.0
_POSTGRES_EXACT_CACHE_MAX_SIZE = 256
_postgres_exact_cache = {}


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
    cache_key = lookup_name.casefold()

    if db.USE_POSTGRES:
        cached = _postgres_exact_cache.get(cache_key)

        if cached is not None:
            cached_at, cached_result = cached

            if (
                monotonic() - cached_at
                <= _POSTGRES_EXACT_CACHE_TTL_SECONDS
            ):
                return deepcopy(cached_result)

            _postgres_exact_cache.pop(cache_key, None)

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

        result = adapt_nutrition_facts_row(
            rows[0],
            backend=backend,
        )

        if db.USE_POSTGRES:
            if (
                len(_postgres_exact_cache)
                >= _POSTGRES_EXACT_CACHE_MAX_SIZE
            ):
                _postgres_exact_cache.clear()

            _postgres_exact_cache[cache_key] = (
                monotonic(),
                deepcopy(result),
            )

        return result

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
