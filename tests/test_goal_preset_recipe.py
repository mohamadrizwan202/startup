import pytest

import goal_preset_recipe
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
    "kiwi",
    "strawberry",
    "spinach",
    "greek yogurt",
    "oat milk",
    "chia seed",
    "papaya",
    "mango",
    "carrots",
    "kefir",
    "coconut water",
    "pumpkin seeds",
    "oats",
    "banana",
    "yogurt",
    "prune",
    "raspberry",
    "apple",
    "blueberry",
    "blackberry",
    "walnuts",
    "almond milk",    "beets",
    "date",
    "pineapple",
    "orange",
    "soy milk",
    "skyr",
    "2% milk",

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
            goal="not-a-real-goal",
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


def test_skin_glow_b_breakfast_uses_mixed_display_units():
    result = build_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
    )

    assert result["display_name"] == "Skin Glow B"
    assert result["target_weight_g"] == 400.0
    assert result["batch"]["weight_g"] == 400.0

    by_id = {
        item["id"]: item
        for item in result["ingredients"]
    }

    assert by_id["kiwi"]["unit"] == "g"
    assert by_id["strawberry"]["unit"] == "g"
    assert by_id["spinach"]["unit"] == "g"
    assert by_id["greek-yogurt"]["unit"] == "g"
    assert by_id["chia-seeds"]["unit"] == "g"

    oat_milk = by_id["oat-milk"]

    assert oat_milk["unit"] == "ml"
    assert round(oat_milk["amount"]) == 120
    assert round(oat_milk["weight_g"], 3) == 123.033


def test_skin_glow_b_scales_across_locked_timings():
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
            variant="b",
        )

        assert result["target_weight_g"] == target_weight_g
        assert result["batch"]["weight_g"] == target_weight_g

        internal_mass = round(
            sum(
                item["weight_g"]
                for item in result["ingredients"]
            ),
            3,
        )

        assert internal_mass == target_weight_g


def test_skin_glow_c_breakfast_uses_mixed_display_units():
    result = build_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="c",
    )

    assert result["display_name"] == "Skin Glow C"
    assert result["target_weight_g"] == 400.0
    assert result["batch"]["weight_g"] == 400.0

    by_id = {
        item["id"]: item
        for item in result["ingredients"]
    }

    assert by_id["papaya"]["unit"] == "g"
    assert by_id["mango"]["unit"] == "g"
    assert by_id["carrot"]["unit"] == "g"
    assert by_id["pumpkin-seeds"]["unit"] == "g"

    kefir = by_id["kefir"]
    coconut_water = by_id["coconut-water"]

    assert kefir["unit"] == "ml"
    assert round(kefir["amount"]) == 100
    assert round(kefir["weight_g"], 3) == 103.0

    assert coconut_water["unit"] == "ml"
    assert round(coconut_water["amount"]) == 100
    assert round(coconut_water["weight_g"], 3) == 102.0


def test_skin_glow_c_scales_across_locked_timings():
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
            variant="c",
        )

        assert result["target_weight_g"] == target_weight_g
        assert result["batch"]["weight_g"] == target_weight_g

        internal_mass = round(
            sum(
                item["weight_g"]
                for item in result["ingredients"]
            ),
            3,
        )

        assert internal_mass == target_weight_g


def test_gut_health_variants_use_locked_ingredient_combinations():

    expected = {
        "a": [
            "kefir",
            "kiwi",
            "oats",
            "banana",
            "flax seeds",
        ],
        "b": [
            "yogurt",
            "prune",
            "kiwi",
            "oats",
            "raspberry",
        ],
        "c": [
            "kefir",
            "prune",
            "apple",
            "oats",
            "chia seed",
        ],
    }

    for variant, expected_lookups in expected.items():

        result = build_goal_preset_recipe(
            goal="gut-health",
            timing="breakfast",
            variant=variant,
        )

        assert result["goal"] == "gut-health"
        assert result["variant"] == variant

        assert [
            item["nutrition_lookup_name"]
            for item in result["ingredients"]
        ] == expected_lookups


def test_gut_health_variants_scale_across_all_locked_timings():

    expected_timings = {
        "breakfast": 400.0,
        "morning-snack": 220.0,
        "lunch": 450.0,
        "afternoon-snack": 220.0,
        "dinner": 300.0,
        "bedtime": 180.0,
    }

    for variant in ("a", "b", "c"):

        for timing, target_weight_g in expected_timings.items():

            result = build_goal_preset_recipe(
                goal="gut-health",
                timing=timing,
                variant=variant,
            )

            assert result["target_weight_g"] == target_weight_g
            assert result["batch"]["weight_g"] == target_weight_g

            internal_mass = round(
                sum(
                    item["weight_g"]
                    for item in result["ingredients"]
                ),
                3,
            )

            assert internal_mass == target_weight_g


def test_gut_health_kefir_variants_use_ml_display_units():

    for variant, expected_ml in (
        ("a", 150),
        ("c", 190),
    ):

        result = build_goal_preset_recipe(
            goal="gut-health",
            timing="breakfast",
            variant=variant,
        )

        kefir = next(
            item
            for item in result["ingredients"]
            if item["id"] == "kefir"
        )

        assert kefir["unit"] == "ml"
        assert round(kefir["amount"]) == expected_ml


def test_brain_focus_variants_use_locked_ingredient_combinations():

    expected = {
        "a": [
            "blueberry",
            "raspberry",
            "blackberry",
            "walnuts",
            "greek yogurt",
            "oats",
        ],
        "b": [
            "blueberry",
            "strawberry",
            "banana",
            "walnuts",
            "oat milk",
            "chia seed",
        ],
        "c": [
            "blueberry",
            "spinach",
            "raspberry",
            "walnuts",
            "almond milk",
            "flax seeds",
        ],
    }

    for variant, expected_lookups in expected.items():

        result = build_goal_preset_recipe(
            goal="brain-focus",
            timing="breakfast",
            variant=variant,
        )

        assert result["goal"] == "brain-focus"
        assert result["variant"] == variant

        assert [
            item["nutrition_lookup_name"]
            for item in result["ingredients"]
        ] == expected_lookups


def test_brain_focus_variants_scale_across_all_locked_timings():

    expected_timings = {
        "breakfast": 400.0,
        "morning-snack": 220.0,
        "lunch": 450.0,
        "afternoon-snack": 220.0,
        "dinner": 300.0,
        "bedtime": 180.0,
    }

    for variant in ("a", "b", "c"):

        for timing, target_weight_g in expected_timings.items():

            result = build_goal_preset_recipe(
                goal="brain-focus",
                timing=timing,
                variant=variant,
            )

            assert result["target_weight_g"] == target_weight_g
            assert result["batch"]["weight_g"] == target_weight_g

            internal_mass = round(
                sum(
                    item["weight_g"]
                    for item in result["ingredients"]
                ),
                3,
            )

            assert internal_mass == target_weight_g


def test_brain_focus_liquid_variants_use_ml_display_units():

    cases = (
        ("b", "oat-milk", 105),
        ("c", "almond-milk", 180),
    )

    for variant, ingredient_id, expected_ml in cases:

        result = build_goal_preset_recipe(
            goal="brain-focus",
            timing="breakfast",
            variant=variant,
        )

        liquid = next(
            item
            for item in result["ingredients"]
            if item["id"] == ingredient_id
        )

        assert liquid["unit"] == "ml"
        assert round(liquid["amount"]) == expected_ml


def test_heart_support_variants_use_locked_ingredient_combinations():

    expected = {
        "a": [
            "oats",
            "blueberry",
            "apple",
            "walnuts",
            "flax seeds",
            "almond milk",
        ],
        "b": [
            "oats",
            "strawberry",
            "raspberry",
            "walnuts",
            "chia seed",
            "oat milk",
        ],
        "c": [
            "blackberry",
            "apple",
            "spinach",
            "walnuts",
            "flax seeds",
            "almond milk",
        ],
    }

    for variant, expected_lookups in expected.items():

        result = build_goal_preset_recipe(
            goal="heart-support",
            timing="breakfast",
            variant=variant,
        )

        assert result["goal"] == "heart-support"
        assert result["variant"] == variant

        assert [
            item["nutrition_lookup_name"]
            for item in result["ingredients"]
        ] == expected_lookups


def test_heart_support_variants_scale_across_all_locked_timings():

    expected_timings = {
        "breakfast": 400.0,
        "morning-snack": 220.0,
        "lunch": 450.0,
        "afternoon-snack": 220.0,
        "dinner": 300.0,
        "bedtime": 180.0,
    }

    for variant in ("a", "b", "c"):

        for timing, target_weight_g in expected_timings.items():

            result = build_goal_preset_recipe(
                goal="heart-support",
                timing=timing,
                variant=variant,
            )

            assert result["target_weight_g"] == target_weight_g
            assert result["batch"]["weight_g"] == target_weight_g

            internal_mass = round(
                sum(
                    item["weight_g"]
                    for item in result["ingredients"]
                ),
                3,
            )

            assert internal_mass == target_weight_g


def test_heart_support_liquid_variants_use_ml_display_units():

    cases = (
        ("a", "almond-milk", 140),
        ("b", "oat-milk", 156),
        ("c", "almond-milk", 140),
    )

    for variant, ingredient_id, expected_ml in cases:

        result = build_goal_preset_recipe(
            goal="heart-support",
            timing="breakfast",
            variant=variant,
        )

        liquid = next(
            item
            for item in result["ingredients"]
            if item["id"] == ingredient_id
        )

        assert liquid["unit"] == "ml"
        assert round(liquid["amount"]) == expected_ml


def test_final_goals_use_locked_ingredient_combinations():

    expected = {
        ("energy-stamina", "a"): [
            "banana",
            "oats",
            "beets",
            "mango",
            "coconut water",
        ],
        ("energy-stamina", "b"): [
            "banana",
            "date",
            "pineapple",
            "greek yogurt",
            "oat milk",
        ],
        ("energy-stamina", "c"): [
            "beets",
            "orange",
            "mango",
            "banana",
            "coconut water",
            "oats",
        ],
        ("muscle-health", "a"): [
            "greek yogurt",
            "banana",
            "oats",
            "soy milk",
            "hemp seeds",
        ],
        ("muscle-health", "b"): [
            "skyr",
            "strawberry",
            "oats",
            "2% milk",
            "chia seed",
        ],
        ("muscle-health", "c"): [
            "kefir",
            "blueberry",
            "greek yogurt",
            "oat milk",
            "hemp seeds",
        ],
    }

    for (goal, variant), expected_lookups in expected.items():

        result = build_goal_preset_recipe(
            goal=goal,
            timing="breakfast",
            variant=variant,
        )

        assert result["goal"] == goal
        assert result["variant"] == variant

        assert [
            item["nutrition_lookup_name"]
            for item in result["ingredients"]
        ] == expected_lookups


def test_final_goals_scale_across_all_locked_timings():

    expected_timings = {
        "breakfast": 400.0,
        "morning-snack": 220.0,
        "lunch": 450.0,
        "afternoon-snack": 220.0,
        "dinner": 300.0,
        "bedtime": 180.0,
    }

    for goal in ("energy-stamina", "muscle-health"):

        for variant in ("a", "b", "c"):

            for timing, target_weight_g in expected_timings.items():

                result = build_goal_preset_recipe(
                    goal=goal,
                    timing=timing,
                    variant=variant,
                )

                assert result["target_weight_g"] == target_weight_g
                assert result["batch"]["weight_g"] == target_weight_g

                internal_mass = round(
                    sum(
                        item["weight_g"]
                        for item in result["ingredients"]
                    ),
                    3,
                )

                assert internal_mass == target_weight_g


def test_final_goals_use_expected_liquid_display_units():

    cases = (
        ("energy-stamina", "a", "coconut-water", 124.224),
        ("energy-stamina", "b", "oat-milk", 105.616),
        ("energy-stamina", "c", "coconut-water", 90.045),
        ("muscle-health", "a", "soy-milk", 136.090),
        ("muscle-health", "b", "2-percent-milk", 135.188),
    )

    for goal, variant, ingredient_id, expected_ml in cases:

        result = build_goal_preset_recipe(
            goal=goal,
            timing="breakfast",
            variant=variant,
        )

        liquid = next(
            item
            for item in result["ingredients"]
            if item["id"] == ingredient_id
        )

        assert liquid["unit"] == "ml"
        assert liquid["amount"] == pytest.approx(expected_ml, abs=0.001)


def test_muscle_health_c_uses_two_liquid_display_units():

    result = build_goal_preset_recipe(
        goal="muscle-health",
        timing="breakfast",
        variant="c",
    )

    by_id = {
        item["id"]: item
        for item in result["ingredients"]
    }

    assert by_id["kefir"]["unit"] == "ml"
    assert round(by_id["kefir"]["amount"]) == 100

    assert by_id["oat-milk"]["unit"] == "ml"
    assert round(by_id["oat-milk"]["amount"]) == 95



def test_supported_ingredient_ids_match_reviewed_presets():
    from goal_preset_recipe import (
        _PRESET_RECIPES,
        get_supported_ingredient_ids,
    )

    expected = tuple(
        sorted(
            {
                ingredient["id"]
                for preset in _PRESET_RECIPES.values()
                for ingredient in preset["ingredients"]
            }
        )
    )

    actual = get_supported_ingredient_ids()

    assert actual == expected
    assert len(actual) == len(set(actual))
    assert all(
        isinstance(ingredient_id, str)
        and ingredient_id.strip()
        for ingredient_id in actual
    )


def test_supported_ingredient_options_are_canonical():
    options = goal_preset_recipe.get_supported_ingredient_options()

    assert len(options) == 36
    assert all(
        set(option) == {"id", "display_name"}
        for option in options
    )

    option_ids = [option["id"] for option in options]

    assert len(option_ids) == len(set(option_ids))
    assert set(option_ids) == set(
        goal_preset_recipe.get_supported_ingredient_ids()
    )

    by_id = {
        option["id"]: option["display_name"]
        for option in options
    }

    assert by_id["oat-milk"] == "Oat Milk"


def test_personalized_recipe_removal_rescales_to_timing_target():
    base = build_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
    )
    retained_ids = [
        "oat-milk",
        "greek-yogurt",
        "spinach",
        "strawberry",
        "kiwi",
    ]

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_ids=retained_ids,
    )

    expected_ids = [
        "kiwi",
        "strawberry",
        "spinach",
        "greek-yogurt",
        "oat-milk",
    ]
    assert [
        item["id"]
        for item in result["ingredients"]
    ] == expected_ids

    retained_definitions = [
        definition
        for definition in goal_preset_recipe._PRESET_RECIPES[
            ("skin-glow", "b")
        ]["ingredients"]
        if definition["id"] in set(retained_ids)
    ]
    expected_weights = goal_preset_recipe._build_scaled_weights(
        retained_definitions,
        target_weight_g=400.0,
    )

    for result_item, expected_weight in zip(
        result["ingredients"],
        expected_weights,
        strict=True,
    ):
        assert result_item["weight_g"] == pytest.approx(
            expected_weight
        )

    assert result["variant"] == "b"
    assert result["target_weight_g"] == pytest.approx(400.0)
    assert result["batch"]["weight_g"] == pytest.approx(400.0)
    assert sum(
        item["weight_g"]
        for item in result["ingredients"]
    ) == pytest.approx(400.0)

    expected = recipe_calculator.calculate_recipe(
        [
            {
                "ingredient": item["display_name"],
                "nutrition_lookup_name": item[
                    "nutrition_lookup_name"
                ],
                "amount": item["weight_g"],
                "unit": "g",
            }
            for item in result["ingredients"]
        ]
    )
    assert result["batch"]["nutrition"] == pytest.approx(
        expected["batch"]["nutrition"]
    )

    contract = result["preset_contract"]
    assert contract["personalized"] is True
    assert contract["uses_age"] is False
    assert contract["uses_sex"] is False
    assert contract["uses_eer"] is False
    assert contract["weight_source"] == (
        "normalized_retained_preset_amounts"
    )


def test_personalized_recipe_accepts_catalog_additions_and_normalizes_to_target():
    selected_ids = [
        "kiwi",
        "banana",
        "blueberry",
    ]

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_ids=selected_ids,
    )

    assert [
        item["id"]
        for item in result["ingredients"]
    ] == selected_ids
    assert result["target_weight_g"] == pytest.approx(400.0)
    assert result["batch"]["weight_g"] == pytest.approx(400.0)
    assert sum(
        item["weight_g"]
        for item in result["ingredients"]
    ) == pytest.approx(400.0)

    expected = recipe_calculator.calculate_recipe(
        [
            {
                "ingredient": item["display_name"],
                "nutrition_lookup_name": item[
                    "nutrition_lookup_name"
                ],
                "amount": item["weight_g"],
                "unit": "g",
            }
            for item in result["ingredients"]
        ]
    )

    assert result["batch"]["nutrition"] == pytest.approx(
        expected["batch"]["nutrition"]
    )
    assert result["preset_contract"]["weight_source"] == (
        "normalized_selected_reference_amounts"
    )
    assert result["preset_contract"]["composition_source"] == (
        "user_selected_preset_and_catalog_composition"
    )


@pytest.mark.parametrize(
    "ingredient_ids",
    (
        [],
        ["banana"],
        ["kiwi", "banana"],
    ),
)
def test_personalized_recipe_requires_at_least_three_ingredients(
    ingredient_ids,
):
    with pytest.raises(
        goal_preset_recipe.GoalPresetRecipeInputError,
        match="at least 3 ingredients are required",
    ):
        goal_preset_recipe.build_personalized_goal_preset_recipe(
            goal="skin-glow",
            timing="breakfast",
            variant="b",
            ingredient_ids=ingredient_ids,
        )


@pytest.mark.parametrize(
    ("ingredient_ids", "message"),
    (
        ([], "at least 3 ingredients"),
        (["kiwi", "kiwi"], "duplicate ingredient"),
        (
            ["kiwi", "not-supported"],
            "not supported for personalization",
        ),
    ),
)
def test_personalized_recipe_rejects_invalid_ingredient_selections(
    ingredient_ids,
    message,
):
    with pytest.raises(
        GoalPresetRecipeInputError,
        match=message,
    ):
        goal_preset_recipe.build_personalized_goal_preset_recipe(
            goal="skin-glow",
            timing="breakfast",
            variant="b",
            ingredient_ids=ingredient_ids,
        )
