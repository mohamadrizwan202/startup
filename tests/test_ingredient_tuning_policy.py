import pytest

from ingredient_tuning_policy import (
    IngredientTuningPolicyError,
    build_policy_tuning_bounds,
)


def _recipe():
    return {
        "ingredients": [
            {
                "ingredient": "Mango",
                "nutrition_lookup_name": "mango",
                "weight_g": 100.0,
            },
            {
                "ingredient": "Spinach",
                "nutrition_lookup_name": "spinach",
                "weight_g": 30.0,
            },
            {
                "ingredient": "Chia Seeds",
                "nutrition_lookup_name": "chia seed",
                "weight_g": 12.0,
            },
        ]
    }


def _approved_rule(minimum, maximum):
    return {
        "min_weight_g": minimum,
        "max_weight_g": maximum,
        "review_status": "approved",
        "enabled": True,
    }


def test_approved_rule_allows_only_its_reviewed_range():
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[0],
        tuning_rules={
            "mango": _approved_rule(80.0, 120.0),
        },
    )

    assert bounds == [
        {
            "min_weight_g": 80.0,
            "max_weight_g": 120.0,
        },
        {
            "min_weight_g": 30.0,
            "max_weight_g": 30.0,
        },
        {
            "min_weight_g": 12.0,
            "max_weight_g": 12.0,
        },
    ]


@pytest.mark.parametrize(
    "rules",
    [
        {},
        {
            "mango": {
                "min_weight_g": 80.0,
                "max_weight_g": 120.0,
                "review_status": "approved",
                "enabled": False,
            }
        },
        {
            "mango": {
                "min_weight_g": 80.0,
                "max_weight_g": 120.0,
                "review_status": "draft",
                "enabled": True,
            }
        },
    ],
)
def test_missing_disabled_or_unapproved_rule_locks_ingredient(rules):
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[0],
        tuning_rules=rules,
    )

    assert bounds[0] == {
        "min_weight_g": 100.0,
        "max_weight_g": 100.0,
    }


def test_current_amount_outside_approved_range_locks_ingredient():
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[0],
        tuning_rules={
            "mango": _approved_rule(20.0, 80.0),
        },
    )

    assert bounds[0] == {
        "min_weight_g": 100.0,
        "max_weight_g": 100.0,
    }


def test_nonadjustable_ingredient_stays_locked_even_with_approved_rule():
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[0],
        tuning_rules={
            "mango": _approved_rule(80.0, 120.0),
            "spinach": _approved_rule(20.0, 50.0),
        },
    )

    assert bounds[1] == {
        "min_weight_g": 30.0,
        "max_weight_g": 30.0,
    }


def test_rules_match_exact_nutrition_lookup_name():
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[2],
        tuning_rules={
            "chia-seeds": _approved_rule(5.0, 25.0),
        },
    )

    assert bounds[2] == {
        "min_weight_g": 12.0,
        "max_weight_g": 12.0,
    }


def test_malformed_approved_range_fails_closed():
    bounds = build_policy_tuning_bounds(
        recipe_result=_recipe(),
        adjustable_indices=[0],
        tuning_rules={
            "mango": _approved_rule(120.0, 80.0),
        },
    )

    assert bounds[0] == {
        "min_weight_g": 100.0,
        "max_weight_g": 100.0,
    }


def test_rejects_duplicate_adjustable_indices():
    with pytest.raises(
        IngredientTuningPolicyError,
        match="cannot contain duplicates",
    ):
        build_policy_tuning_bounds(
            recipe_result=_recipe(),
            adjustable_indices=[0, 0],
            tuning_rules={},
        )
