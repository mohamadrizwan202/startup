import pytest

import recipe_calculator
from account_goal_recipe_profiles import ACCOUNT_GOAL_RECIPE_PROFILES
from goal_preset_recipe import (
    GoalPresetRecipeInputError,
    build_account_goal_preset_recipe,
    build_goal_preset_recipe,
    build_personalized_goal_preset_recipe,
    get_personalization_goal_base_ingredient_ids,
    get_supported_goal_slugs,
)


def _fake_lookup(name):
    return {
        "ingredient": str(name).strip().lower(),
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


def test_every_account_goal_profile_builds_a_deterministic_base_recipe():
    for category_value, profile in ACCOUNT_GOAL_RECIPE_PROFILES.items():
        recipe = build_account_goal_preset_recipe(
            category_value=category_value,
            timing="breakfast",
        )

        assert recipe["goal"] == profile["goal_slug"]
        assert recipe["timing"] == "breakfast"
        assert recipe["variant"] == "a"
        assert recipe["batch"]["weight_g"] == pytest.approx(400.0)
        assert recipe["preset_contract"][
            "account_goal_category_value"
        ] == category_value
        assert recipe["preset_contract"][
            "account_goal_label"
        ] == profile["label"]


def test_account_only_goal_is_not_publicly_buildable():
    assert "iron-support" not in get_supported_goal_slugs()

    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unsupported preset recipe",
    ):
        build_goal_preset_recipe(
            goal="iron-support",
            timing="breakfast",
        )


def test_account_profile_keeps_existing_liquid_unit_and_explicit_amounts():
    base_recipe = build_account_goal_preset_recipe(
        category_value="Bone Health",
        timing="breakfast",
    )
    base_by_id = {
        item["id"]: item
        for item in base_recipe["ingredients"]
    }
    assert base_by_id["almond-milk"]["unit"] == "ml"

    personalized_recipe = build_personalized_goal_preset_recipe(
        goal="bone-strength",
        timing="breakfast",
        variant="a",
        ingredient_selections=[
            {"id": "almond-milk", "amount": 135},
            {"id": "yogurt", "amount": 85},
            {"id": "banana", "amount": 45},
        ],
    )
    personalized_by_id = {
        item["id"]: item
        for item in personalized_recipe["ingredients"]
    }

    assert personalized_by_id["almond-milk"]["unit"] == "ml"
    assert personalized_by_id["almond-milk"]["amount"] == 135
    assert personalized_by_id["yogurt"]["amount"] == 85
    assert personalized_by_id["banana"]["amount"] == 45
    assert personalized_recipe["preset_contract"][
        "timing_target_applied"
    ] is False
    assert personalized_recipe["preset_contract"][
        "account_goal_profile"
    ] is True
    assert personalized_recipe["preset_contract"][
        "account_goal_category_value"
    ] == "Bone Health"
    assert personalized_recipe["preset_contract"][
        "account_goal_label"
    ] == "Bone Strength"
    assert personalized_recipe["batch"]["weight_g"] == pytest.approx(
        sum(
            item["weight_g"]
            for item in personalized_recipe["ingredients"]
        )
    )

def test_personalization_base_ids_resolve_every_account_goal_profile():
    for category_value, profile in ACCOUNT_GOAL_RECIPE_PROFILES.items():
        base_recipe = build_account_goal_preset_recipe(
            category_value=category_value,
            timing="breakfast",
        )

        assert get_personalization_goal_base_ingredient_ids(
            goal=profile["goal_slug"],
            variant="a",
        ) == tuple(
            ingredient["id"]
            for ingredient in base_recipe["ingredients"]
        )

    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unsupported preset recipe",
    ):
        get_personalization_goal_base_ingredient_ids(
            goal="iron-support",
            variant="b",
        )
