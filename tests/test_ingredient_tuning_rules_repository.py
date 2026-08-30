import sqlite3

import pytest

import ingredient_tuning_rules_repository as repository
from ingredient_tuning_rules_repository import (
    IngredientTuningRuleLookupError,
    get_ingredient_tuning_rule_exact,
)


def _make_sqlite_connection(rows=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE ingredient_tuning_rules (
            nutrition_lookup_name TEXT NOT NULL,
            min_weight_g REAL,
            max_weight_g REAL,
            source_type TEXT,
            source_reference TEXT,
            rationale TEXT,
            review_status TEXT NOT NULL,
            enabled INTEGER NOT NULL
        )
        """
    )

    default_rows = [
        (
            "mango",
            80.0,
            120.0,
            "test_fixture",
            "fixture:mango",
            "Repository contract fixture only.",
            "approved",
            1,
        ),
        (
            "chia seed",
            5.0,
            20.0,
            "test_fixture",
            "fixture:chia",
            "Repository contract fixture only.",
            "draft",
            0,
        ),
    ]

    conn.executemany(
        """
        INSERT INTO ingredient_tuning_rules (
            nutrition_lookup_name,
            min_weight_g,
            max_weight_g,
            source_type,
            source_reference,
            rationale,
            review_status,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows if rows is not None else default_rows,
    )

    conn.commit()
    return conn


@pytest.fixture
def sqlite_repository(monkeypatch):
    monkeypatch.setattr(
        repository.db,
        "USE_POSTGRES",
        False,
    )

    monkeypatch.setattr(
        repository.db,
        "get_conn",
        _make_sqlite_connection,
    )


def test_exact_lookup_returns_rule_contract(
    sqlite_repository,
):
    result = get_ingredient_tuning_rule_exact("mango")

    assert result == {
        "nutrition_lookup_name": "mango",
        "min_weight_g": 80.0,
        "max_weight_g": 120.0,
        "source_type": "test_fixture",
        "source_reference": "fixture:mango",
        "rationale": "Repository contract fixture only.",
        "review_status": "approved",
        "enabled": True,
    }


def test_exact_lookup_is_case_insensitive(
    sqlite_repository,
):
    result = get_ingredient_tuning_rule_exact("MANGO")

    assert result["nutrition_lookup_name"] == "mango"


def test_exact_lookup_ignores_surrounding_whitespace(
    sqlite_repository,
):
    result = get_ingredient_tuning_rule_exact(
        "   mango   "
    )

    assert result["nutrition_lookup_name"] == "mango"


def test_missing_exact_name_returns_none(
    sqlite_repository,
):
    assert (
        get_ingredient_tuning_rule_exact("spinach")
        is None
    )


@pytest.mark.parametrize(
    "lookup_name",
    [
        "mang",
        "mango fruit",
        "chia",
        "chia seeds",
    ],
)
def test_lookup_does_not_use_fuzzy_alias_or_plural_matching(
    sqlite_repository,
    lookup_name,
):
    assert (
        get_ingredient_tuning_rule_exact(lookup_name)
        is None
    )


@pytest.mark.parametrize(
    "lookup_name",
    [
        None,
        "",
        "   ",
        123,
        True,
    ],
)
def test_invalid_lookup_names_are_rejected(
    sqlite_repository,
    lookup_name,
):
    with pytest.raises(
        IngredientTuningRuleLookupError
    ):
        get_ingredient_tuning_rule_exact(
            lookup_name
        )


def test_draft_disabled_rule_is_returned_without_policy_decision(
    sqlite_repository,
):
    result = get_ingredient_tuning_rule_exact(
        "chia seed"
    )

    assert result["review_status"] == "draft"
    assert result["enabled"] is False


def test_normalized_name_collision_is_rejected(
    monkeypatch,
):
    rows = [
        (
            "mango",
            80.0,
            120.0,
            "fixture",
            None,
            None,
            "approved",
            1,
        ),
        (
            " MANGO ",
            70.0,
            130.0,
            "fixture",
            None,
            None,
            "approved",
            1,
        ),
    ]

    monkeypatch.setattr(
        repository.db,
        "USE_POSTGRES",
        False,
    )

    monkeypatch.setattr(
        repository.db,
        "get_conn",
        lambda: _make_sqlite_connection(rows),
    )

    with pytest.raises(
        IngredientTuningRuleLookupError,
        match="multiple",
    ):
        get_ingredient_tuning_rule_exact(
            "mango"
        )
