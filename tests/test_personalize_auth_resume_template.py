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
