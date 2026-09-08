import startup_recovered as app_module


TEST_USER_ID = 123
TEST_EMAIL = "user@example.com"
TEST_TOKEN = "mobile-auth-test-token"


def _user():
    return {
        "id": TEST_USER_ID,
        "email": TEST_EMAIL,
        "password_hash": "stored-password-hash",
        "created_at": "",
    }


def _client(monkeypatch):
    monkeypatch.setitem(
        app_module.app.config,
        "TESTING",
        True,
    )
    monkeypatch.setitem(
        app_module.app.config,
        "WTF_CSRF_ENABLED",
        False,
    )
    return app_module.app.test_client()


def test_mobile_login_establishes_existing_single_session(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(
        app_module,
        "get_user_by_email",
        lambda email: _user() if email == TEST_EMAIL else None,
    )
    monkeypatch.setattr(
        app_module,
        "check_password_hash",
        lambda stored_hash, password: (
            stored_hash == "stored-password-hash"
            and password == "correct-password"
        ),
    )
    monkeypatch.setattr(
        app_module,
        "set_user_session_token",
        lambda user_id: (
            TEST_TOKEN
            if user_id == TEST_USER_ID
            else None
        ),
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": f"  {TEST_EMAIL}  ",
            "password": "correct-password",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "authenticated": True,
        "user": {
            "id": TEST_USER_ID,
            "email": TEST_EMAIL,
        },
    }

    set_cookie = response.headers.get("Set-Cookie", "")
    assert set_cookie.startswith("session=")
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie

    with client.session_transaction() as sess:
        assert sess["user_id"] == TEST_USER_ID
        assert sess["active_session_token"] == TEST_TOKEN


def test_mobile_login_rejects_unknown_user(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(
        app_module,
        "get_user_by_email",
        lambda _email: None,
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "invalid_credentials",
    }


def test_mobile_login_rejects_wrong_password(monkeypatch):
    client = _client(monkeypatch)

    monkeypatch.setattr(
        app_module,
        "get_user_by_email",
        lambda _email: _user(),
    )
    monkeypatch.setattr(
        app_module,
        "check_password_hash",
        lambda _stored_hash, _password: False,
    )

    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "invalid_credentials",
    }


def test_mobile_login_rejects_invalid_request(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/auth/login",
        data="{not-json",
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "invalid_request",
    }
