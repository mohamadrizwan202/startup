import importlib.util
from pathlib import Path

import pytest

from recipe_mass import normalize_recipe_ingredient_mass


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "018_add_whole_nuts_tune_rules.py"
    )

    spec = importlib.util.spec_from_file_location(
        "migration_018_whole_nuts",
        path,
    )
    module = importlib.util.module_from_spec(spec)

    assert spec.loader is not None
    spec.loader.exec_module(module)

    return module


migration = _load_migration()


EXPECTED_NUTRITION = (
    ("almonds", 579.0, 21.15, 21.55, 49.93, 12.50, 4.35, 1.0, 28.0),
    ("walnuts", 654.0, 15.23, 13.71, 65.21, 6.70, 2.61, 2.0, 28.0),
    ("cashews", 553.0, 18.22, 30.19, 43.85, 3.30, 5.91, 12.0, 28.0),
    ("pecans", 691.0, 9.17, 13.86, 71.97, 9.60, 3.97, 0.0, 28.0),
    ("pistachios", 560.0, 20.16, 27.17, 45.32, 10.60, 7.66, 1.0, 28.0),
)

EXPECTED_RULES = (
    ("almonds", 5.0, 35.0),
    ("walnuts", 5.0, 30.0),
    ("cashews", 5.0, 35.0),
    ("pecans", 5.0, 30.0),
    ("pistachios", 5.0, 35.0),
)

EXPECTED_ALIASES = (
    "almond",
    "walnut",
    "cashew",
    "pecan",
    "pistachio",
)


def test_whole_nuts_v1_exact_nutrition():
    assert migration.NUTRITION_ROWS == EXPECTED_NUTRITION


def test_whole_nuts_v1_exact_ranges():
    assert migration.RULES == EXPECTED_RULES


def test_whole_nuts_v1_singular_aliases_are_not_rules():
    assert migration.NONCANONICAL_ALIASES == EXPECTED_ALIASES

    canonical = {row[0] for row in migration.RULES}

    assert canonical.isdisjoint(
        migration.NONCANONICAL_ALIASES
    )


@pytest.mark.parametrize(
    "lookup_name,display_name,amount_g",
    [
        ("almonds", "Almonds", 5.0),
        ("almonds", "Almonds", 35.0),
        ("walnuts", "Walnuts", 5.0),
        ("walnuts", "Walnuts", 30.0),
        ("cashews", "Cashews", 5.0),
        ("cashews", "Cashews", 35.0),
        ("pecans", "Pecans", 5.0),
        ("pecans", "Pecans", 30.0),
        ("pistachios", "Pistachios", 5.0),
        ("pistachios", "Pistachios", 35.0),
    ],
)
def test_whole_nuts_v1_exact_gram_mass(
    lookup_name,
    display_name,
    amount_g,
):
    result = normalize_recipe_ingredient_mass(
        ingredient=display_name,
        nutrition_lookup_name=lookup_name,
        amount=amount_g,
        unit="g",
    )

    assert result["ingredient"] == display_name
    assert result["nutrition_lookup_name"] == lookup_name
    assert result["weight_g"] == pytest.approx(amount_g)
    assert result["mass_source"] == "gram_input"
