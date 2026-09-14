import importlib.util
from pathlib import Path

import pytest

from recipe_mass import normalize_recipe_ingredient_mass


def _load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "015_add_booster_seed_tune_rules.py"
    )

    spec = importlib.util.spec_from_file_location(
        "migration_015_booster_seeds",
        migration_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


EXPECTED_NUTRITION = (
    (
        "flax seeds",
        534.0,
        18.29,
        28.88,
        42.16,
        27.30,
        1.55,
        30.0,
        7.0,
    ),
    (
        "hemp seeds",
        553.0,
        31.56,
        8.67,
        48.75,
        4.00,
        1.50,
        5.0,
        30.0,
    ),
    (
        "pumpkin seeds",
        559.0,
        30.23,
        10.71,
        49.05,
        6.00,
        1.40,
        7.0,
        28.0,
    ),
)

EXPECTED_RULES = (
    ("flax seeds", 5.0, 25.0),
    ("hemp seeds", 5.0, 30.0),
    ("pumpkin seeds", 5.0, 30.0),
)

EXPECTED_NONCANONICAL = {
    "flax seed",
    "flaxseed",
    "hemp seed",
    "hemp hearts",
    "pumpkin seed",
}


def test_booster_seed_v1_exact_nutrition_contract():
    assert migration.NUTRITION_ROWS == EXPECTED_NUTRITION


def test_booster_seed_v1_exact_tune_ranges():
    assert migration.RULES == EXPECTED_RULES


def test_booster_seed_v1_keeps_aliases_fail_closed():
    enabled_names = {
        lookup_name
        for lookup_name, _minimum, _maximum in migration.RULES
    }

    assert EXPECTED_NONCANONICAL.issubset(
        set(migration.NONCANONICAL_TUNE_IDENTITIES)
    )
    assert enabled_names.isdisjoint(EXPECTED_NONCANONICAL)


def test_booster_seed_migration_does_not_modify_chia():
    assert all(
        nutrition_row[0] != "chia seed"
        and nutrition_row[0] != "chia seeds"
        for nutrition_row in migration.NUTRITION_ROWS
    )
    assert all(
        rule[0] != "chia seed"
        and rule[0] != "chia seeds"
        for rule in migration.RULES
    )


@pytest.mark.parametrize(
    "lookup_name,amount_g",
    [
        ("flax seeds", 5.0),
        ("flax seeds", 25.0),
        ("hemp seeds", 5.0),
        ("hemp seeds", 30.0),
        ("pumpkin seeds", 5.0),
        ("pumpkin seeds", 30.0),
    ],
)
def test_booster_seed_canonical_gram_mass_is_preserved(
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
