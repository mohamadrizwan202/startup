from pathlib import Path


def _index_template() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "templates"
        / "index.html"
    ).read_text(encoding="utf-8")


def test_personalize_auth_resume_is_a_web_only_flow():
    template = _index_template()

    required_markers = (
        'id="pf-result-personalize"',
        'id="pf-personalize-auth-overlay"',
        'id="pf-personalize-auth-register"',
        'id="pf-personalize-auth-login"',
        "const PF_PENDING_PERSONALIZE_KEY =",
        "'purefyul.pending-personalize.v1'",
        "function pfStorePendingPersonalizeSnapshot()",
        "function pfReadPendingPersonalizeSnapshot()",
        "function pfClearPendingPersonalizeSnapshot()",
        "function pfOpenPersonalizeAuthPrompt(",
        "function pfRestorePendingPersonalizeAfterAuth()",
        "/app?resume_personalize=1",
    )

    for marker in required_markers:
        assert marker in template

    assert template.count(
        "pfStorePendingPersonalizeSnapshot("
    ) >= 2
    assert template.count(
        "pfOpenPersonalizeAuthPrompt("
    ) >= 2
    assert template.count(
        "pfRestorePendingPersonalizeAfterAuth("
    ) >= 2

    assert "/api/personalization/calculate" not in template
    assert "/api/personalization-profile" not in template


def test_logged_in_personalize_editor_updates_explicit_ingredients():
    template = _index_template()

    start = template.index(
        "async function pfSavePersonalizeSetup("
    )
    end = template.index(
        "function pfRestorePendingPersonalizeAfterAuth()",
        start,
    )
    update_flow = template[start:end]

    required_markers = (
        "/api/personalized-goal-preset",
        "ingredient_ids: preferredIds",
        "const requestUpdate = async function(personId)",
        "requestPayload.person_id = personId",
        "await requestUpdate(null)",
        "response.status === 409",
        "setup_required",
        "body.setup.person_required",
        "await pfEnsurePersonalizeSetupPerson()",
        "await requestUpdate(person.id)",
        "body.recipe",
        "window.pfRestoreGoalPresetResult(",
        "Update Smoothie",
        "Updating your smoothie...",
    )

    for marker in required_markers:
        assert marker in update_flow

    assert update_flow.count("await fetch(") == 1

    assert update_flow.index(
        "await requestUpdate(null)"
    ) < update_flow.index(
        "await pfEnsurePersonalizeSetupPerson()"
    ) < update_flow.index(
        "await requestUpdate(person.id)"
    )

    obsolete_markers = (
        "/preferences",
        "/ingredient-preferences",
        "await Promise.all([",
        "avoid: removedIds",
        "const removedIds =",
        "person_id: person.id",
    )

    for marker in obsolete_markers:
        assert marker not in update_flow

    assert "window.pfRestoreGoalPresetResult(recipe)" not in update_flow
    assert "Keep ingredient choices" not in template

def test_personalize_editor_uses_catalog_additions_and_keeps_minimum_three():
    template = _index_template()

    required_template_markers = (
        'id="pf-personalize-setup-add-select"',
        'id="pf-personalize-setup-add-button"',
        "/api/personalization/ingredient-options",
        "function pfLoadPersonalizeIngredientOptions(",
        "function pfRefreshPersonalizeSetupControls(",
        "function pfAddPersonalizeSetupIngredient(",
    )

    for marker in required_template_markers:
        assert marker in template

    save_start = template.index(
        "async function pfSavePersonalizeSetup("
    )
    save_end = template.index(
        "function pfRestorePendingPersonalizeAfterAuth()",
        save_start,
    )
    save_flow = template[save_start:save_end]

    assert "preferredIds.length < 3" in save_flow
    assert "at least 3 ingredients are required" in save_flow

    controls_start = template.index(
        "function pfRefreshPersonalizeSetupControls("
    )
    controls_end = template.index(
        "function pfAddPersonalizeSetupIngredient(",
        controls_start,
    )
    controls_flow = template[controls_start:controls_end]

    assert "selectedCount <= 3" in controls_flow
    assert "button.disabled" in controls_flow

    open_start = template.index(
        "function pfOpenPersonalizeSetupPrompt("
    )
    open_end = template.index(
        "function pfClosePersonalizeSetupPrompt(",
        open_start,
    )
    open_flow = template[open_start:open_end]

    assert "pfLoadPersonalizeIngredientOptions()" in open_flow
    assert "/api/personalized-goal-preset" not in open_flow
    assert "async function pfGeneratePersonalizedGoalPreset(" not in template

def test_personalize_editor_defaults_to_goal_aligned_options_and_exposes_custom_catalog():
    template = _index_template()

    required_markers = (
        'id="pf-personalize-setup-show-all"',
        "Show all supported ingredients",
        "goal_aligned_ingredient_ids",
        "pfPersonalizeGoalAlignedIngredientIds",
        "pfPersonalizeCatalogMode",
        "goal_alignment",
        "Custom Smoothie",
        "URLSearchParams({ goal: recipe.goal })",
    )

    for marker in required_markers:
        assert marker in template
