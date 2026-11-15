"""Read-only ingredient quantity contract; no SQLite or database access."""

from copy import deepcopy
import math

import pytest
import goal_preset_recipe as recipes


def _by_id(payload):
    return {item["id"]: item for item in payload["ingredients"]}


def test_uncontextualized_catalog_shape_is_backwards_compatible():
    response = recipes.get_personalization_ingredient_options(goal="brain-focus")
    assert response["goal"] == "brain-focus"
    assert all(
        set(item) == {"id", "display_name", "unit"}
        for item in response["ingredients"]
    )


def test_context_provides_explicit_reviewed_amounts_and_units():
    response = recipes.get_personalization_ingredient_options(
        goal="brain-focus", timing="breakfast", variant="b"
    )
    options = _by_id(response)
    raspberry = options["raspberry"]  # variant b lacks raspberry
    almond_milk = options["almond-milk"]  # variant c includes almond milk
    assert raspberry["amount"] > 0
    assert raspberry["unit"] == "g"
    assert almond_milk["amount"] > 0
    assert almond_milk["unit"] == "ml"
    assert raspberry["amount_source"] == "same_goal_reviewed_recipe_component"
    assert almond_milk["amount_source"] == "same_goal_reviewed_recipe_component"
    assert response["timing"] == "breakfast"
    assert response["variant"] == "b"


def test_suggestions_follow_timing_without_changing_any_preset():
    original = deepcopy(recipes._PRESET_RECIPES)
    breakfast = _by_id(recipes.get_personalization_ingredient_options(
        goal="brain-focus", timing="breakfast", variant="b"
    ))
    snack = _by_id(recipes.get_personalization_ingredient_options(
        goal="brain-focus", timing="morning-snack", variant="b"
    ))
    assert breakfast["raspberry"]["amount"] > snack["raspberry"]["amount"]
    assert original == recipes._PRESET_RECIPES


def test_suggestions_are_never_invented_from_unreviewed_placeholder(monkeypatch):
    original_options = recipes.get_supported_ingredient_options

    def with_unreviewed():
        return original_options() + ({
            "id": "unreviewed-test-item",
            "display_name": "Unreviewed Test Item",
            "unit": "g",
        },)

    monkeypatch.setattr(recipes, "get_supported_ingredient_options", with_unreviewed)
    result = _by_id(recipes.get_personalization_ingredient_options(
        goal="brain-focus", timing="breakfast", variant="a"
    ))
    assert result["unreviewed-test-item"]["amount"] is None
    assert result["unreviewed-test-item"]["amount_source"] == "manual_amount_required"
    for item in result.values():
        if item["amount"] is not None:
            assert math.isfinite(item["amount"]) and item["amount"] > 0
            assert item["amount_source"] != "manual_amount_required"


@pytest.mark.parametrize("timing,variant", [
    ("brunch", "b"),
    ("breakfast", "unknown"),
])
def test_invalid_context_rejected(timing, variant):
    with pytest.raises(recipes.GoalPresetRecipeInputError):
        recipes.get_personalization_ingredient_options(
            goal="brain-focus", timing=timing, variant=variant
        )


def test_frontend_sends_context_and_never_adds_blank_amount():
    from pathlib import Path
    template = (Path(__file__).resolve().parents[1] / "templates/index.html").read_text()
    backend = (Path(__file__).resolve().parents[1] / "startup_recovered.py").read_text()
    assert "query.set('timing', recipe.timing)" in template
    assert "query.set('variant', recipe.variant || 'a')" in template
    assert "const amountText = amountInput ? amountInput.value.trim() : '';" in template
    assert "if (!Number.isFinite(amount) || amount <= 0)" in template
    assert "pfAppendPersonalizeSetupIngredient({" in template
    assert "...option," in template
    assert "amount: amount" in template
    assert 'id="pf-personalize-setup-add-amount"' in template
    assert "result = get_options(goal=goal, timing=timing, variant=variant)" in backend
