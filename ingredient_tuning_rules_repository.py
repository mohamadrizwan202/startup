"""Exact reviewed Tune-rule lookup.

This repository performs database retrieval only.

Lookup behavior is deliberately strict:
- case-insensitive exact nutrition_lookup_name match;
- surrounding whitespace is ignored;
- no LIKE/substring/fuzzy search;
- no implicit plural/singular conversion;
- no alias lookup;
- no inferred or fallback gram limits.

The repository does not decide whether a rule is usable. Approval,
enablement, current-weight checks, and fail-closed locking belong to
ingredient_tuning_policy.
"""

from __future__ import annotations

import db


class IngredientTuningRuleLookupError(ValueError):
    """Raised when an exact Tune-rule lookup violates its contract."""


def _validate_lookup_name(value) -> str:
    if not isinstance(value, str):
        raise IngredientTuningRuleLookupError(
            "nutrition_lookup_name must be a string"
        )

    lookup_name = value.strip()

    if not lookup_name:
        raise IngredientTuningRuleLookupError(
            "nutrition_lookup_name must be a non-empty string"
        )

    return lookup_name


def get_ingredient_tuning_rule_exact(
    nutrition_lookup_name,
) -> dict | None:
    """Return one exact ingredient Tune rule, or None when absent."""

    lookup_name = _validate_lookup_name(
        nutrition_lookup_name
    )

    sql = """
        SELECT
            nutrition_lookup_name,
            min_weight_g,
            max_weight_g,
            source_type,
            source_reference,
            rationale,
            review_status,
            enabled
        FROM ingredient_tuning_rules
        WHERE LOWER(TRIM(nutrition_lookup_name))
            = LOWER(TRIM(?))
        ORDER BY nutrition_lookup_name
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
            raise IngredientTuningRuleLookupError(
                "multiple ingredient_tuning_rules rows match "
                "the exact nutrition_lookup_name"
            )

        row = db.row_to_dict(rows[0], cursor)

        return {
            "nutrition_lookup_name": row[
                "nutrition_lookup_name"
            ],
            "min_weight_g": (
                None
                if row["min_weight_g"] is None
                else float(row["min_weight_g"])
            ),
            "max_weight_g": (
                None
                if row["max_weight_g"] is None
                else float(row["max_weight_g"])
            ),
            "source_type": row["source_type"],
            "source_reference": row["source_reference"],
            "rationale": row["rationale"],
            "review_status": row["review_status"],
            "enabled": bool(row["enabled"]),
        }

    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
