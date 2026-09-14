import importlib.util
from pathlib import Path

import pytest

from recipe_mass import normalize_recipe_ingredient_mass


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "016_add_nut_butter_tune_rules.py"
    )

    spec = importlib.util.spec_from_file_location(
        "migration_016_nut_butter",
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


EXPECTED_NUTRITION = (
    (
        "peanut butter",
        598.0,
        22.21,
        22.31,
        51.36,
        5.00,
        10.49,
        17.0,
        32.0,
    ),
    (
        "almond butter",
        614.0,
        20.96,
        18.82,
        55.50,
        10.30,
        4.43,
        7.0,
        16.0,
    ),
)

EXPECTED_RULES = (
    ("peanut butter", 8.0, 40.0),
    ("almond butter", 8.0, 40.0),
)


def test_nut_butter_v1_exact_nutrition_contract():
    assert migration.NUTRITION_ROWS == EXPECTED_NUTRITION


def test_nut_butter_v1_exact_tune_ranges():
    assert migration.RULES == EXPECTED_RULES


@pytest.mark.parametrize(
    "lookup_name,amount_g",
    [
        ("peanut butter", 8.0),
        ("peanut butter", 40.0),
        ("almond butter", 8.0),
        ("almond butter", 40.0),
    ],
)
def test_nut_butter_v1_exact_gram_mass(
    lookup_name,
    amount_g,
):
    result = normalize_recipe_ingredient_mass(
        ingredient=lookup_name.title(),
        nutrition_lookup_name=lookup_name,
        amount=amount_g,
        unit="g",
    )

    assert result["ingredient"] == lookup_name.title()
    assert result["nutrition_lookup_name"] == lookup_name
    assert result["weight_g"] == pytest.approx(amount_g)
    assert result["mass_source"] == "gram_input"
