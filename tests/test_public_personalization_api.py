import startup_recovered as app_module


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


def test_public_personalization_calculates_energy_without_login_or_database(
    monkeypatch,
):
    client = _client(monkeypatch)

    def forbidden_db_connection():
        raise AssertionError(
            "public personalization calculation must not access the database"
        )

    monkeypatch.setattr(
        app_module.db,
        "get_conn",
        forbidden_db_connection,
    )

    response = client.post(
        "/api/personalization/calculate",
        json={
            "age": 22,
            "sex": "female",
            "height": {
                "unit": "cm",
                "value": 165,
            },
            "weight": {
                "unit": "kg",
                "value": 63,
            },
            "activity_level": "low_active",
            "pregnancy_lactation_status": "neither",
        },
    )

    assert response.status_code == 200

    body = response.get_json()

    assert body["profile"] == {
        "age": 22,
        "sex": "female",
        "height_cm": 165.0,
        "weight_kg": 63.0,
        "activity_level": "low_active",
        "pregnancy_lactation_status": "neither",
        "preferred_height_unit": "cm",
        "preferred_weight_unit": "kg",
    }

    assert body["energy_estimate"] == {
        "available": True,
        "reason": None,
        "kcal_per_day": 2275,
        "method": "NASEM_2023_EER",
    }


def test_public_personalization_preserves_activity_required(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/personalization/calculate",
        json={
            "age": 31,
            "sex": "male",
            "height": {
                "unit": "cm",
                "value": 180,
            },
            "weight": {
                "unit": "kg",
                "value": 80,
            },
            "activity_level": None,
        },
    )

    assert response.status_code == 200

    assert response.get_json()["energy_estimate"] == {
        "available": False,
        "reason": "activity_level_required",
        "kcal_per_day": None,
        "method": "NASEM_2023_EER",
    }


def test_public_personalization_preserves_life_stage_unavailable_state(
    monkeypatch,
):
    client = _client(monkeypatch)

    response = client.post(
        "/api/personalization/calculate",
        json={
            "age": 31,
            "sex": "female",
            "height": {
                "unit": "cm",
                "value": 165,
            },
            "weight": {
                "unit": "kg",
                "value": 63,
            },
            "activity_level": "active",
            "pregnancy_lactation_status": "pregnant",
        },
    )

    assert response.status_code == 200

    assert response.get_json()["energy_estimate"] == {
        "available": False,
        "reason": "separate_life_stage_eer_required",
        "kcal_per_day": None,
        "method": "NASEM_2023_EER",
    }


def test_public_personalization_rejects_invalid_profile(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/personalization/calculate",
        json={
            "age": 3,
            "sex": "male",
            "height": {
                "unit": "cm",
                "value": 100,
            },
            "weight": {
                "unit": "kg",
                "value": 20,
            },
            "activity_level": "active",
        },
    )

    assert response.status_code == 400

    body = response.get_json()

    assert body["error"] == "invalid_profile"
    assert "age 4+" in body["message"]


def test_public_personalization_does_not_expose_unexpected_failure(
    monkeypatch,
):
    client = _client(monkeypatch)

    import personalization_profile

    def fail(_data):
        raise RuntimeError("internal secret")

    monkeypatch.setattr(
        personalization_profile,
        "normalize_profile_payload",
        fail,
    )

    response = client.post(
        "/api/personalization/calculate",
        json={
            "age": 31,
            "sex": "male",
        },
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "personalization_failed",
    }
    assert "internal secret" not in response.get_data(as_text=True)
