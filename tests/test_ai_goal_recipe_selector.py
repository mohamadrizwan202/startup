import json
import sys
from types import SimpleNamespace

import pytest

import ai_goal_recipe_selector
from ai_goal_recipe_selector import (
    AIGoalRecipeSelectionError,
    select_reviewed_goal_recipe,
)
from goal_preset_recipe import (
    GoalPresetRecipeInputError,
    get_reviewed_goal_recipe_candidates,
)


class FakeMessages:
    def __init__(self, text):
        self.text = text
        self.request = None

    def create(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(
            content=[SimpleNamespace(text=self.text)]
        )


class FakeClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)
        self.options = None

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


def _candidate(goal, variant):
    return next(
        candidate
        for candidate in get_reviewed_goal_recipe_candidates(goal)
        if candidate["variant"] == variant
    )


def _response_for(candidate):
    return json.dumps({
        "variant": candidate["variant"],
    })


def test_selects_one_exact_reviewed_goal_candidate():
    candidate = _candidate("skin-glow", "b")
    client = FakeClient(_response_for(candidate))

    result = select_reviewed_goal_recipe(
        client=client,
        goal="skin-glow",
        timing="breakfast",
    )

    assert result == {
        "variant": "b",
        "ingredient_ids": list(candidate["ingredient_ids"]),
        "selection_source": "haiku_reviewed_candidate",
    }
    assert client.options == {
        "timeout": 2.5,
        "max_retries": 0,
    }
    assert (
        client.messages.request["model"]
        == "claude-haiku-4-5-20251001"
    )
    assert client.messages.request["max_tokens"] == 32
    assert (
        "exactly this key: variant"
        in client.messages.request["messages"][0]["content"]
    )


def test_uses_bounded_stdlib_transport_without_anthropic_sdk(
    monkeypatch,
):
    candidate = _candidate("skin-glow", "a")
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(
            self,
            _exception_type,
            _exception_value,
            _traceback,
        ):
            return False

        def read(self):
            return json.dumps({
                "content": [{
                    "type": "text",
                    "text": _response_for(candidate),
                }],
            }).encode("utf-8")

    def fake_urlopen(request, *, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.setattr(
        ai_goal_recipe_selector.urllib.request,
        "urlopen",
        fake_urlopen,
    )

    result = select_reviewed_goal_recipe(
        client=None,
        goal="skin-glow",
        timing="breakfast",
    )

    assert result["variant"] == "a"
    assert captured["timeout"] == 2.5
    assert (
        captured["request"].full_url
        == "https://api.anthropic.com/v1/messages"
    )
    assert json.loads(
        captured["request"].data.decode("utf-8")
    )["model"] == "claude-haiku-4-5-20251001"


def test_rejects_variant_outside_allowed_goal_set():
    client = FakeClient('{"variant":"not-reviewed"}')

    with pytest.raises(
        AIGoalRecipeSelectionError,
        match="outside the allowed goal set",
    ):
        select_reviewed_goal_recipe(
            client=client,
            goal="skin-glow",
            timing="breakfast",
        )


def test_rejects_an_excluded_recent_variant():
    candidate = _candidate("skin-glow", "a")
    client = FakeClient(_response_for(candidate))

    with pytest.raises(
        AIGoalRecipeSelectionError,
        match="outside the allowed goal set",
    ):
        select_reviewed_goal_recipe(
            client=client,
            goal="skin-glow",
            timing="breakfast",
            excluded_variants=("a",),
        )


def test_rejects_extra_ai_response_fields():
    candidate = _candidate("skin-glow", "a")
    client = FakeClient(
        '{"variant":"a","ingredient_ids":'
        + repr(list(candidate["ingredient_ids"])).replace("'", '"')
        + ',"claim":"guaranteed results"}'
    )

    with pytest.raises(
        AIGoalRecipeSelectionError,
        match="unsupported fields",
    ):
        select_reviewed_goal_recipe(
            client=client,
            goal="skin-glow",
            timing="breakfast",
        )


def test_rejects_invalid_timing_before_calling_ai():
    candidate = _candidate("skin-glow", "a")
    client = FakeClient(_response_for(candidate))

    with pytest.raises(
        GoalPresetRecipeInputError,
        match="unsupported preset timing",
    ):
        select_reviewed_goal_recipe(
            client=client,
            goal="skin-glow",
            timing="midnight-feast",
        )

    assert client.messages.request is None
