import pytest

import tune_smoothie_api_service
from tune_smoothie_api_service import (
    TuneSmoothieRequestError,
    build_tune_ranges_response,
    build_tune_response,
)


def _calculated_recipe():
    return {
        "ingredients": [
            {
                "ingredient": "Greek Yogurt",
                "nutrition_lookup_name": "greek yogurt",
                "weight_g": 100.0,
                "mass_source": "gram_input",
                "nutrition_per_100g": {
                    "calories": 100.0,
                    "protein": 10.0,
                    "carbs": 5.0,
                    "fat": 2.0,
                    "fiber": 0.0,
                    "sugar": 4.0,
                    "sodium": 50.0,
                },
            },
            {
                "ingredient": "Apple",
                "nutrition_lookup_name": "apple",
                "weight_g": 100.0,
                "mass_source": "gram_input",
                "nutrition_per_100g": {
                    "calories": 50.0,
                    "protein": 0.0,
                    "carbs": 14.0,
                    "fat": 0.0,
                    "fiber": 2.0,
                    "sugar": 10.0,
                    "sodium": 1.0,
                },
            },
        ],
        "batch": {
            "weight_g": 200.0,
            "nutrition": {
                "calories": 150.0,
                "protein": 10.0,
                "carbs": 19.0,
                "fat": 2.0,
                "fiber": 2.0,
                "sugar": 14.0,
                "sodium": 51.0,
            },
            "energy_density_kcal_per_g": 0.75,
        },
        "portion": None,
    }


def _api_ingredients():
    return [
        {
            "ingredient": "Greek Yogurt",
            "nutrition_lookup_name": "greek yogurt",
            "amount": 100,
            "unit": "g",
        },
        {
            "ingredient": "Apple",
            "nutrition_lookup_name": "apple",
            "amount": 100,
            "unit": "g",
        },
    ]


@pytest.fixture(autouse=True)
def fake_recipe_calculation(monkeypatch):
    monkeypatch.setattr(
        tune_smoothie_api_service,
        "calculate_recipe",
        lambda _ingredients: _calculated_recipe(),
    )


def test_ranges_response_returns_real_feasible_ranges():
    result = build_tune_ranges_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0, 1],
            "nutrients": [
                "protein",
                "sugar",
            ],
        }
    )

    assert result["batch"]["weight_g"] == pytest.approx(200.0)

    assert result["ranges"]["protein"]["current"] == pytest.approx(
        10.0
    )
    assert result["ranges"]["protein"]["minimum"] == pytest.approx(
        0.1
    )
    assert result["ranges"]["protein"]["maximum"] == pytest.approx(
        19.9
    )

    assert result["constraints"] == {
        "preserve_total_weight": True,
    }

    assert result["ingredients"][0]["adjustable"] is True
    assert result["ingredients"][1]["adjustable"] is True


def test_ranges_default_to_verified_seven_nutrients():
    result = build_tune_ranges_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0, 1],
        }
    )

    assert set(result["ranges"]) == {
        "calories",
        "protein",
        "carbs",
        "fat",
        "fiber",
        "sugar",
        "sodium",
    }


def test_ranges_can_lock_an_ingredient():
    result = build_tune_ranges_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0],
            "nutrients": ["protein"],
        }
    )

    assert result["ingredients"][0]["adjustable"] is True
    assert result["ingredients"][1]["adjustable"] is False

    assert result["ranges"]["protein"]["minimum"] == pytest.approx(
        10.0
    )
    assert result["ranges"]["protein"]["maximum"] == pytest.approx(
        10.0
    )


def test_tune_response_returns_before_after_ingredient_grams():
    result = build_tune_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0, 1],
            "targets": {
                "protein": 15.0,
            },
        }
    )

    assert result["before"]["weight_g"] == pytest.approx(200.0)
    assert result["after"]["weight_g"] == pytest.approx(200.0)

    assert result["ingredients"][0]["before_weight_g"] == pytest.approx(
        100.0
    )
    assert result["ingredients"][0]["after_weight_g"] == pytest.approx(
        150.0
    )

    assert result["ingredients"][1]["before_weight_g"] == pytest.approx(
        100.0
    )
    assert result["ingredients"][1]["after_weight_g"] == pytest.approx(
        50.0
    )

    assert result["after"]["nutrition"]["protein"] == pytest.approx(
        15.0
    )


def test_request_requires_ingredients():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="ingredients",
    ):
        build_tune_ranges_response(
            {
                "adjustable_indices": [0],
            }
        )


def test_request_requires_adjustable_indices():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="adjustable_indices",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
            }
        )


def test_request_rejects_duplicate_adjustable_indices():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="duplicates",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 0],
            }
        )


def test_tune_requires_exact_targets():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="targets",
    ):
        build_tune_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 1],
                "targets": {},
            }
        )


def test_ranges_reject_unverified_nutrient():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="unsupported nutrient",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 1],
                "nutrients": ["potassium"],
            }
        )


def test_preserve_total_weight_must_be_boolean():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="must be a boolean",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 1],
                "preserve_total_weight": "yes",
            }
        )


def test_ranges_condition_each_nutrient_on_other_selected_targets():
    result = build_tune_ranges_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0, 1],
            "nutrients": [
                "protein",
                "sugar",
            ],
            "targets": {
                "protein": 15.0,
                "sugar": 11.0,
            },
        }
    )

    # Protein remains free while Sugar=11 is held exact.
    assert result["ranges"]["protein"]["minimum"] == pytest.approx(
        15.0
    )
    assert result["ranges"]["protein"]["maximum"] == pytest.approx(
        15.0
    )

    # Sugar remains free while Protein=15 is held exact.
    assert result["ranges"]["sugar"]["minimum"] == pytest.approx(
        11.0
    )
    assert result["ranges"]["sugar"]["maximum"] == pytest.approx(
        11.0
    )


def test_ranges_do_not_pin_nutrient_to_its_own_selected_target():
    result = build_tune_ranges_response(
        {
            "ingredients": _api_ingredients(),
            "adjustable_indices": [0, 1],
            "nutrients": ["protein"],
            "targets": {
                "protein": 15.0,
            },
        }
    )

    # With no OTHER selected targets, Protein keeps its ordinary
    # feasible range rather than collapsing to its selected value.
    assert result["ranges"]["protein"]["minimum"] == pytest.approx(
        0.1
    )
    assert result["ranges"]["protein"]["maximum"] == pytest.approx(
        19.9
    )


def test_ranges_reject_non_dictionary_targets():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="targets must be a dictionary",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 1],
                "nutrients": ["protein"],
                "targets": [],
            }
        )


def test_ranges_reject_unsupported_target_nutrient():
    with pytest.raises(
        TuneSmoothieRequestError,
        match="unsupported nutrient",
    ):
        build_tune_ranges_response(
            {
                "ingredients": _api_ingredients(),
                "adjustable_indices": [0, 1],
                "nutrients": ["protein"],
                "targets": {
                    "potassium": 1000.0,
                },
            }
        )
