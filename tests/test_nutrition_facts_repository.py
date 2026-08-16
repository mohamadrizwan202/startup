import sqlite3

import pytest

import nutrition_facts_repository as repository
from nutrition_facts_repository import (
    NutritionFactsLookupError,
    get_nutrition_facts_exact,
)


def _make_sqlite_connection(rows=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    conn.execute(
        """
        CREATE TABLE nutrition_facts (
            ingredient TEXT NOT NULL,
            calories_per_100g REAL,
            protein REAL,
            carbs REAL,
            fat REAL,
            fiber REAL,
            sugar REAL,
            sodium REAL,
            serving_size REAL
        )
        """
    )

    default_rows = [
        (
            "banana",
            89,
            1.1,
            23,
            0.3,
            2.6,
            12,
            1,
            118,
        ),
        (
            "strawberry",
            32,
            0.7,
            7.7,
            0.3,
            2.0,
            4.9,
            1,
            152,
        ),
    ]

    conn.executemany(
        """
        INSERT INTO nutrition_facts (
            ingredient,
            calories_per_100g,
            protein,
            carbs,
            fat,
            fiber,
            sugar,
            sodium,
            serving_size
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows if rows is not None else default_rows,
    )

    conn.commit()
    return conn


@pytest.fixture
def sqlite_repository(monkeypatch):
    monkeypatch.setattr(repository.db, "USE_POSTGRES", False)

    monkeypatch.setattr(
        repository.db,
        "get_conn",
        _make_sqlite_connection,
    )


def test_exact_lookup_returns_strict_per_100g_contract(
    sqlite_repository,
):
    result = get_nutrition_facts_exact("banana")

    assert result == {
        "ingredient": "banana",
        "nutrition_per_100g": {
            "calories": 89.0,
            "protein": 1.1,
            "carbs": 23.0,
            "fat": 0.3,
            "fiber": 2.6,
            "sugar": 12.0,
            "sodium": 1.0,
        },
    }


def test_exact_lookup_is_case_insensitive(
    sqlite_repository,
):
    result = get_nutrition_facts_exact("BANANA")

    assert result["ingredient"] == "banana"


def test_exact_lookup_ignores_surrounding_whitespace(
    sqlite_repository,
):
    result = get_nutrition_facts_exact("   banana   ")

    assert result["ingredient"] == "banana"


def test_missing_exact_name_returns_none(
    sqlite_repository,
):
    assert get_nutrition_facts_exact("mango") is None


@pytest.mark.parametrize(
    "ingredient",
    [
        "banan",
        "yellow banana",
        "banana fruit",
        "ban",
    ],
)
def test_lookup_does_not_use_fuzzy_or_partial_matching(
    sqlite_repository,
    ingredient,
):
    assert get_nutrition_facts_exact(ingredient) is None


def test_repository_does_not_implicitly_pluralize_or_alias(
    sqlite_repository,
):
    assert get_nutrition_facts_exact("strawberries") is None

    exact = get_nutrition_facts_exact("strawberry")

    assert exact["ingredient"] == "strawberry"


@pytest.mark.parametrize(
    "ingredient",
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
    ingredient,
):
    with pytest.raises(NutritionFactsLookupError):
        get_nutrition_facts_exact(ingredient)


def test_normalized_name_collision_is_rejected(
    monkeypatch,
):
    rows = [
        (
            "banana",
            89,
            1.1,
            23,
            0.3,
            2.6,
            12,
            1,
            118,
        ),
        (
            " BANANA ",
            90,
            1.2,
            24,
            0.4,
            2.7,
            13,
            2,
            120,
        ),
    ]

    monkeypatch.setattr(repository.db, "USE_POSTGRES", False)

    monkeypatch.setattr(
        repository.db,
        "get_conn",
        lambda: _make_sqlite_connection(rows),
    )

    with pytest.raises(
        NutritionFactsLookupError,
        match="multiple",
    ):
        get_nutrition_facts_exact("banana")
