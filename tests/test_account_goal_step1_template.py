from pathlib import Path


_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "index.html"
).read_text(encoding="utf-8")


def _saved_goal_cards_block():
    grid_start = _TEMPLATE.index(
        '<div class="pf-goal-choice-grid" id="pf-goal-choice-grid">'
    )
    saved_start = _TEMPLATE.index(
        "{% if account_health_goals_ready %}",
        grid_start,
    )
    saved_end = _TEMPLATE.index("{% else %}", saved_start)
    return _TEMPLATE[saved_start:saved_end]


def _build_flow():
    start = _TEMPLATE.index("async function buildPresetVariant(")
    end = _TEMPLATE.index("if (buildButton)", start)
    return _TEMPLATE[start:end]


def test_saved_step1_cards_are_selectable_private_goal_buttons():
    saved_cards = _saved_goal_cards_block()

    assert '<button' in saved_cards
    assert 'data-account-health-goal="{{ value }}"' in saved_cards
    assert 'aria-pressed="false"' in saved_cards
    assert "{{ account_health_goal_labels[value] }}" in saved_cards
    assert '<div\n                  class="pf-goal-choice' not in saved_cards


def test_account_goal_build_uses_private_raw_category_contract():
    flow = _build_flow()

    assert "selectedAccountGoal" in flow
    assert "/api/account-goal-preset" in flow
    assert "category_value: selectedAccountGoal" in flow
    assert "goal: selectedGoal" in flow
    assert "variant: variant" in flow
    assert "goal: selectedAccountGoal" not in flow


def test_build_another_is_hidden_and_blocked_for_personalized_results():
    render_start = _TEMPLATE.index("function renderPresetResult(")
    render_flow = _TEMPLATE[render_start:]

    assert "isPersonalizedRecipe" in render_flow
    assert "shouldHideBuildAnother" in render_flow
    assert "buildAnotherButton.hidden = shouldHideBuildAnother" in render_flow
    assert (
        render_flow.index("isPersonalizedRecipe")
        < render_flow.index(
            "buildAnotherButton.hidden = shouldHideBuildAnother"
        )
    )

    click_start = _TEMPLATE.rindex("if (buildAnotherButton) {")
    click_flow = _TEMPLATE[click_start:]

    assert "currentContract.personalized" in click_flow
