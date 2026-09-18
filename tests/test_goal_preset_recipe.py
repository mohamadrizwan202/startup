import pytest

import recipe_calculator
from goal_preset_recipe import (
    GoalPresetRecipeInputError,
    build_goal_preset_recipe,
)


SUPPORTED_LOOKUPS = {
    "guava",
    "pea milk",
    "cucumber",
    "cauliflower",
    "hemp seeds",
    "flax seeds",
    "lime juice",
}


def _fake_lookup(name):
    normalized = name.strip().lower()

    if normalized not in SUPPORTED_LOOKUPS:
        return None

    return {
        "ingredient": normalized,
        "nutrition_per_100g": {
            "calories": 100.0,
            "protein": 2.0,
            "carbs": 10.0,
            "fat": 1.0,
            "fiber": 3.0,
            "sugar": 4.0,
            "sodium": 5.0,
        },
    }


@pytest.fixture(autouse=True)
def _stub_nutrition_lookup(monkeypatch):
    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        _fake_lookup,
    )


def test_skin_glow_a_breakfast_builds_exact_400g_recipe():
    result = build_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="a",
    )

    assert result["goal"] == "skin-glow"
    assert result["timing"] == "breakfast"
    assert result["variant"] == "a"
    assert result["target_weight_g"] == pytest.approx(400.0)
    assert result["batch"]["weight_g"] == pytest.approx(400.0)

    assert [
        ingredient["nutrition_lookup_name"]
        for ingredient in result["ingredients"]
    ] == [
        "guava",
        "pea milk",
        "cucumber",
        "cauliflower",
        "hemp seeds",
        "flax seeds",
        "lime juice",
    ]

    assert [
        ingredient["weight_g"]
        for ingredient in result["ingredients"]
    ] == pytest.approx(
        [
            134.168,
            134.168,
            54.068,
            54.068,
            13.016,
            6.008,
            4.504,
        ]
    )

    assert sum(
        ingredient["weight_g"]
        for ingredient in result["ingredients"]
    ) == pytest.approx(400.0)


def test_preset_contract_is_not_personalized():
    result = build_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
    )

    contract = result["preset_contract"]

    assert contract["personalized"] is False
    assert contract["uses_age"] is False
    assert contract["uses_sex"] is False
    assert contract["uses_eer"] is False
    assert contract["weight_source"] == "timing"


def test_unsupported_timing_fails_closed():
    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unsupported preset timing",
    ):
        build_goal_preset_recipe(
            goal="skin-glow",
            timing="brunch",
        )


def test_unsupported_goal_fails_closed():
    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unsupported preset recipe",
    ):
        build_goal_preset_recipe(
            goal="gut-health",
            timing="breakfast",
        )


def test_skin_glow_a_uses_locked_timing_targets():
    expected = {
        "breakfast": 400.0,
        "morning-snack": 220.0,
        "lunch": 450.0,
        "afternoon-snack": 220.0,
        "dinner": 300.0,
        "bedtime": 180.0,
    }

    for timing, target_weight_g in expected.items():
        result = build_goal_preset_recipe(
            goal="skin-glow",
            timing=timing,
        )

        assert result["target_weight_g"] == target_weight_g
        assert result["batch"]["weight_g"] == target_weight_g
        assert round(
            sum(item["amount"] for item in result["ingredients"]),
            3,
        ) == target_weight_g
