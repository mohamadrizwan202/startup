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

    assert set(expected).issubset(set(actual))
    assert actual == tuple(sorted(
        goal_preset_recipe._get_personalization_catalog_definitions()
    ))
    assert len(actual) == len(set(actual))
    assert all(
        isinstance(ingredient_id, str)
        and ingredient_id.strip()
        for ingredient_id in actual
    )


def test_supported_ingredient_options_are_canonical():
    options = goal_preset_recipe.get_supported_ingredient_options()

    assert len(options) > 36
    assert len(options) < len(
        goal_preset_recipe.get_supported_ingredient_ids()
    )
    assert all(
        set(option) == {"id", "display_name", "unit"}
        for option in options
    )

    option_ids = [option["id"] for option in options]

    assert len(option_ids) == len(set(option_ids))
    definitions = (
        goal_preset_recipe._get_personalization_catalog_definitions()
    )
    expected_selectable = {
        ingredient_id
        for ingredient_id, definition in definitions.items()
        if goal_preset_recipe._is_new_personalization_selection_allowed(
            definition
        )
    }
    assert set(option_ids) == expected_selectable
    assert set(option_ids).issubset(
        set(goal_preset_recipe.get_supported_ingredient_ids())
    )

    by_id = {
        option["id"]: option
        for option in options
    }

    assert by_id["oat-milk"]["display_name"] == "Oat Milk"
    assert by_id["oat-milk"]["unit"] == "ml"


def test_personalized_recipe_uses_explicit_amounts_without_timing_rescale():
    ingredient_selections = [
        {"id": "oat-milk", "amount": 113.0},
        {"id": "greek-yogurt", "amount": 89.0},
        {"id": "spinach", "amount": 17.0},
        {"id": "strawberry", "amount": 53.0},
        {"id": "kiwi", "amount": 41.0},
    ]

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_selections=ingredient_selections,
    )

    assert [
        item["id"]
        for item in result["ingredients"]
    ] == [
        "kiwi",
        "strawberry",
        "spinach",
        "greek-yogurt",
        "oat-milk",
    ]

    amounts_by_id = {
        selection["id"]: selection["amount"]
        for selection in ingredient_selections
    }
    result_by_id = {
        item["id"]: item
        for item in result["ingredients"]
    }

    for ingredient_id, amount in amounts_by_id.items():
        assert result_by_id[ingredient_id]["amount"] == pytest.approx(
            amount
        )

    for item in result["ingredients"]:
        if item["unit"] == "g":
            assert item["weight_g"] == pytest.approx(item["amount"])

    assert result_by_id["oat-milk"]["unit"] == "ml"
    assert result["target_weight_g"] == pytest.approx(400.0)
    assert result["batch"]["weight_g"] == pytest.approx(
        sum(
            item["weight_g"]
            for item in result["ingredients"]
        ),
        abs=0.001,
    )
    assert result["batch"]["weight_g"] != pytest.approx(400.0)

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
    assert contract["weight_source"] == "explicit_user_amounts"
    assert (
        contract["composition_source"]
        == "explicit_user_ingredient_amounts"
    )
    assert contract["timing_target_applied"] is False


def test_personalized_recipe_accepts_catalog_additions_with_explicit_amounts():
    ingredient_selections = [
        {"id": "kiwi", "amount": 91.0},
        {"id": "banana", "amount": 83.0},
        {"id": "blueberry", "amount": 67.0},
    ]

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_selections=ingredient_selections,
    )

    assert [
        item["id"]
        for item in result["ingredients"]
    ] == [
        "kiwi",
        "banana",
        "blueberry",
    ]
    assert [
        item["amount"]
        for item in result["ingredients"]
    ] == pytest.approx([91.0, 83.0, 67.0])
    assert result["target_weight_g"] == pytest.approx(400.0)
    assert result["batch"]["weight_g"] == pytest.approx(241.0)
    assert result["batch"]["weight_g"] != pytest.approx(400.0)

    contract = result["preset_contract"]
    assert contract["weight_source"] == "explicit_user_amounts"
    assert (
        contract["composition_source"]
        == "explicit_user_ingredient_amounts"
    )
    assert contract["timing_target_applied"] is False
    assert contract["goal_alignment"] == "custom"
    assert contract["outside_goal_ingredient_ids"] == [
        "banana",
        "blueberry",
    ]


@pytest.mark.parametrize(
    "ingredient_selections",
    (
        [],
        [{"id": "banana", "amount": 60.0}],
        [
            {"id": "kiwi", "amount": 60.0},
            {"id": "banana", "amount": 60.0},
        ],
    ),
)
def test_personalized_recipe_requires_at_least_three_ingredients(
    ingredient_selections,
):
    with pytest.raises(
        GoalPresetRecipeInputError,
        match="at least 3 ingredients are required",
    ):
        goal_preset_recipe.build_personalized_goal_preset_recipe(
            goal="skin-glow",
            timing="breakfast",
            variant="b",
            ingredient_selections=ingredient_selections,
        )


@pytest.mark.parametrize(
    ("ingredient_selections", "message"),
    (
        (None, "ingredient selections must be a list"),
        (
            [{"id": "kiwi", "amount": 40.0, "extra": True}],
            "each ingredient selection must contain id and amount",
        ),
        (
            [{"id": "kiwi", "amount": "40"}],
            "ingredient amount must be a positive number",
        ),
        (
            [{"id": "kiwi", "amount": True}],
            "ingredient amount must be a positive number",
        ),
        (
            [{"id": "kiwi", "amount": 0.0}],
            "ingredient amount must be a positive finite number",
        ),
        (
            [{"id": "kiwi", "amount": float("nan")}],
            "ingredient amount must be a positive finite number",
        ),
        (
            [{"id": "kiwi", "amount": float("inf")}],
            "ingredient amount must be a positive finite number",
        ),
        (
            [
                {"id": "kiwi", "amount": 40.0},
                {"id": "kiwi", "amount": 50.0},
                {"id": "strawberry", "amount": 60.0},
            ],
            "duplicate ingredient selections are not allowed",
        ),
        (
            [
                {"id": "kiwi", "amount": 40.0},
                {"id": "strawberry", "amount": 50.0},
                {"id": "not-supported", "amount": 60.0},
            ],
            "not supported for personalization",
        ),
    ),
)
def test_personalized_recipe_rejects_invalid_ingredient_selections(
    ingredient_selections,
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
            ingredient_selections=ingredient_selections,
        )


def test_personalized_recipe_reports_goal_alignment_and_custom_status():
    aligned = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_selections=[
            {"id": "kiwi", "amount": 75.0},
            {"id": "strawberry", "amount": 65.0},
            {"id": "guava", "amount": 80.0},
        ],
    )

    assert aligned["display_name"] == "Skin Glow Smoothie"
    assert aligned["preset_contract"]["goal_alignment"] == (
        "goal_aligned"
    )
    assert aligned["preset_contract"][
        "outside_goal_ingredient_ids"
    ] == []

    custom = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_selections=[
            {"id": "kiwi", "amount": 75.0},
            {"id": "banana", "amount": 65.0},
            {"id": "blueberry", "amount": 80.0},
        ],
    )

    assert custom["display_name"] == "Custom Smoothie"
    assert custom["preset_contract"]["goal_alignment"] == "custom"
    assert custom["preset_contract"][
        "outside_goal_ingredient_ids"
    ] == [
        "banana",
        "blueberry",
    ]


def test_new_personalization_catalog_excludes_unsuitable_ingredients():
    definitions = (
        goal_preset_recipe._get_personalization_catalog_definitions()
    )
    options = goal_preset_recipe.get_supported_ingredient_options()
    selectable = {item["id"] for item in options}

    assert len(selectable) == len(options)
    for ingredient_id, definition in definitions.items():
        excluded = (
            definition["nutrition_lookup_name"].strip().casefold()
            in goal_preset_recipe._NEW_PERSONALIZATION_EXCLUDED_LOOKUP_NAMES
        )
        assert (ingredient_id in selectable) is not excluded

    for ingredient_id in (
        "honeydew", "tofu", "apple", "kale", "coconut-water"
    ):
        assert ingredient_id in selectable

    # Kept in the catalog so earlier saved recipes still load,
    # but no longer offered for new smoothies.
    for ingredient_id in (
        "quinoa", "grapefruit", "chickpeas",
        "matcha", "barley", "broccoli", "kidney-beans",
    ):
        assert ingredient_id not in selectable
        assert ingredient_id in definitions


def test_new_personalization_rejects_excluded_ingredient():
    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unavailable for new personalization",
    ):
        goal_preset_recipe.build_personalized_goal_preset_recipe(
            goal="skin-glow",
            timing="breakfast",
            variant="b",
            ingredient_selections=[
                {"id": "kiwi", "amount": 90.0},
                {"id": "banana", "amount": 100.0},
                {"id": "quinoa", "amount": 30.0},
            ],
        )


def test_legacy_authorized_ingredient_preserves_explicit_amounts(
    monkeypatch,
):
    original_lookup = _fake_lookup

    def lookup_with_legacy(name):
        if name.strip().lower() == "quinoa":
            return original_lookup("banana")
        return original_lookup(name)

    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        lookup_with_legacy,
    )

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="b",
        ingredient_selections=[
            {"id": "kiwi", "amount": 90.0},
            {"id": "banana", "amount": 100.0},
            {"id": "quinoa", "amount": 30.0},
        ],
        legacy_allowed_ingredient_ids=("quinoa",),
    )

    amounts = {
        ingredient["id"]: ingredient["amount"]
        for ingredient in result["ingredients"]
    }
    assert amounts == {
        "kiwi": 90.0,
        "banana": 100.0,
        "quinoa": 30.0,
    }


def test_plant_milks_with_sourced_density_use_ml_and_convert_to_grams(
    monkeypatch,
):
    import recipe_mass

    monkeypatch.setattr(
        recipe_calculator.nutrition_facts_repository,
        "get_nutrition_facts_exact",
        lambda name: _fake_lookup(name) or (
            _fake_lookup("oats") | {"ingredient": name.strip().lower()}
            if name.strip().lower() in {"rice milk", "mango"}
            else None
        ),
    )

    options = {
        option["id"]: option
        for option in goal_preset_recipe.get_supported_ingredient_options()
    }
    for ingredient_id in ("rice-milk", "hemp-milk", "cashew-milk"):
        assert options[ingredient_id]["unit"] == "ml"
    # No sourced density: not offered for new smoothies at all.
    for ingredient_id in (
        "barley-milk", "flax-milk", "hazelnut-milk", "milk",
        "pecan-milk", "pistachio-milk", "quinoa-milk", "walnut-milk",
    ):
        assert ingredient_id not in options

    result = goal_preset_recipe.build_personalized_goal_preset_recipe(
        goal="skin-glow",
        timing="breakfast",
        variant="a",
        ingredient_selections=[
            {"id": "rice-milk", "amount": 120.0},
            {"id": "mango", "amount": 100.0},
            {"id": "spinach", "amount": 30.0},
        ],
    )
    rice = next(
        item for item in result["ingredients"] if item["id"] == "rice-milk"
    )
    assert rice["unit"] == "ml"
    assert rice["amount"] == pytest.approx(120.0)
    assert rice["weight_g"] == pytest.approx(
        recipe_mass.convert_liquid_ml_to_grams(
            nutrition_lookup_name="rice milk", volume_ml=120.0
        )
    )


def test_half_cup_liquid_portion_starts_at_120_ml():
    response = goal_preset_recipe.get_personalization_ingredient_options(
        goal="skin-glow", timing="lunch", variant="a"
    )
    by_id = {item["id"]: item for item in response["ingredients"]}
    assert by_id["rice-milk"]["amount"] == 120.0
    assert by_id["rice-milk"]["unit"] == "ml"
    assert by_id["rice-milk"]["amount_label"] == "1/2 cup"
