import sqlite3

import pytest

import db
import startup_recovered as app_module


def _prepare_ledger(monkeypatch, tmp_path):
    database_path = tmp_path / "personalized_entitlement.sqlite3"

    monkeypatch.setattr(db, "USE_POSTGRES", False)
    monkeypatch.setattr(db, "DB_PATH", database_path)

    conn = sqlite3.connect(str(database_path))
    conn.execute(
        """
        CREATE TABLE personalized_smoothie_generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            person_id INTEGER,
            goal_slug TEXT NOT NULL,
            timing_slug TEXT NOT NULL,
            access_type TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    return database_path


def _insert_generation(
    database_path,
    *,
    user_id,
    access_type,
):
    conn = sqlite3.connect(str(database_path))

    try:
        conn.execute(
            """
            INSERT INTO personalized_smoothie_generations (
                user_id,
                person_id,
                goal_slug,
                timing_slug,
                access_type
            )
            VALUES (?, NULL, ?, ?, ?)
            """,
            (
                user_id,
                "skin-glow",
                "breakfast",
                access_type,
            ),
        )
        conn.commit()

    finally:
        conn.close()


def test_free_user_starts_with_three_personalized_generations(
    monkeypatch,
    tmp_path,
):
    _prepare_ledger(monkeypatch, tmp_path)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "free",
    )

    result = app_module._get_personalized_generation_access(71)

    assert result == {
        "plan": "free",
        "allowed": True,
        "access_type": "free_trial",
        "free_limit": 3,
        "free_used": 0,
        "free_remaining": 3,
    }


def test_free_user_usage_counts_only_free_trial_rows(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_ledger(monkeypatch, tmp_path)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "free",
    )

    _insert_generation(
        database_path,
        user_id=71,
        access_type="free_trial",
    )
    _insert_generation(
        database_path,
        user_id=71,
        access_type="free_trial",
    )

    # Pro history must not consume the free allowance.
    _insert_generation(
        database_path,
        user_id=71,
        access_type="pro",
    )

    result = app_module._get_personalized_generation_access(71)

    assert result["allowed"] is True
    assert result["access_type"] == "free_trial"
    assert result["free_used"] == 2
    assert result["free_remaining"] == 1


def test_free_user_is_blocked_after_three_free_generations(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_ledger(monkeypatch, tmp_path)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "free",
    )

    for _ in range(3):
        _insert_generation(
            database_path,
            user_id=71,
            access_type="free_trial",
        )

    result = app_module._get_personalized_generation_access(71)

    assert result == {
        "plan": "free",
        "allowed": False,
        "access_type": None,
        "free_limit": 3,
        "free_used": 3,
        "free_remaining": 0,
    }


def test_usage_is_account_scoped(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_ledger(monkeypatch, tmp_path)

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "free",
    )

    for _ in range(3):
        _insert_generation(
            database_path,
            user_id=99,
            access_type="free_trial",
        )

    result = app_module._get_personalized_generation_access(71)

    assert result["allowed"] is True
    assert result["free_used"] == 0
    assert result["free_remaining"] == 3


def test_pro_user_remains_allowed_after_free_trial_is_exhausted(
    monkeypatch,
    tmp_path,
):
    database_path = _prepare_ledger(monkeypatch, tmp_path)

    for _ in range(3):
        _insert_generation(
            database_path,
            user_id=71,
            access_type="free_trial",
        )

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        lambda _user_id: "pro",
    )

    result = app_module._get_personalized_generation_access(71)

    assert result == {
        "plan": "pro",
        "allowed": True,
        "access_type": "pro",
        "free_limit": 3,
        "free_used": 3,
        "free_remaining": 0,
    }


def test_entitlement_lookup_failure_propagates(
    monkeypatch,
    tmp_path,
):
    _prepare_ledger(monkeypatch, tmp_path)

    def fail_plan_lookup(_user_id):
        raise RuntimeError("subscription lookup failed")

    monkeypatch.setattr(
        app_module,
        "get_user_plan",
        fail_plan_lookup,
    )

    with pytest.raises(
        RuntimeError,
        match="subscription lookup failed",
    ):
        app_module._get_personalized_generation_access(71)
