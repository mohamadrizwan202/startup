import importlib.util
from pathlib import Path

import pytest

from recipe_mass import normalize_recipe_ingredient_mass


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "017_add_avocado_tune_rule.py"
    )

    spec = importlib.util.spec_from_file_location(
        "migration_017_avocado",
        path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


EXPECTED_NUTRITION = (
    "avocado",
    160.0,
    2.00,
    8.53,
    14.66,
    6.70,
    0.66,
    7.0,
    150.0,
)

EXPECTED_RULE = (
    "avocado",
    20.0,
    160.0,
)


def test_avocado_v1_exact_nutrition_contract():
    assert migration.NUTRITION_ROW == EXPECTED_NUTRITION


def test_avocado_v1_exact_tune_range():
    assert migration.RULE == EXPECTED_RULE


@pytest.mark.parametrize("amount_g", [20.0, 160.0])
def test_avocado_v1_exact_gram_mass(amount_g):
    result = normalize_recipe_ingredient_mass(
        ingredient="Avocado",
        nutrition_lookup_name="avocado",
        amount=amount_g,
        unit="g",
    )

    assert result["ingredient"] == "Avocado"
    assert result["nutrition_lookup_name"] == "avocado"
    assert result["weight_g"] == pytest.approx(amount_g)
    assert result["mass_source"] == "gram_input"
