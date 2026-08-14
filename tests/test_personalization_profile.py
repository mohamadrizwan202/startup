import pytest

from personalization_profile import (
    KG_PER_LB,
    ProfileInputError,
    normalize_profile_payload,
)


def test_cm_and_kg_remain_canonical():
    profile = normalize_profile_payload(
        {
            "age": 31,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 63},
            "activity_level": "low_active",
        }
    )

    assert profile["age"] == 31
    assert profile["sex"] == "female"
    assert profile["height_cm"] == pytest.approx(165)
    assert profile["weight_kg"] == pytest.approx(63)
    assert profile["activity_level"] == "low_active"
    assert profile["preferred_height_unit"] == "cm"
    assert profile["preferred_weight_unit"] == "kg"


def test_feet_inches_convert_to_centimeters():
    profile = normalize_profile_payload(
        {
            "age": 25,
            "sex": "male",
            "height": {
                "unit": "ft_in",
                "feet": 5,
                "inches": 5,
            },
            "weight": {"unit": "kg", "value": 70},
            "activity_level": "active",
        }
    )

    assert profile["height_cm"] == pytest.approx(165.1)
    assert profile["preferred_height_unit"] == "ft_in"


def test_pounds_convert_to_kilograms():
    profile = normalize_profile_payload(
        {
            "age": 40,
            "sex": "female",
            "height": {"unit": "cm", "value": 170},
            "weight": {"unit": "lb", "value": 140},
            "activity_level": "inactive",
        }
    )

    assert profile["weight_kg"] == pytest.approx(140 * KG_PER_LB)
    assert profile["preferred_weight_unit"] == "lb"


def test_null_activity_means_not_sure():
    profile = normalize_profile_payload(
        {
            "age": 19,
            "sex": "female",
            "height": {"unit": "cm", "value": 160},
            "weight": {"unit": "kg", "value": 55},
            "activity_level": None,
        }
    )

    assert profile["activity_level"] is None


def test_blank_activity_means_not_sure():
    profile = normalize_profile_payload(
        {
            "age": 19,
            "sex": "male",
            "height": {"unit": "cm", "value": 175},
            "weight": {"unit": "kg", "value": 70},
            "activity_level": "",
        }
    )

    assert profile["activity_level"] is None


@pytest.mark.parametrize(
    "activity_level",
    [
        "inactive",
        "low_active",
        "active",
        "very_active",
    ],
)
def test_all_supported_activity_levels_are_accepted(activity_level):
    profile = normalize_profile_payload(
        {
            "age": 30,
            "sex": "male",
            "height": {"unit": "cm", "value": 180},
            "weight": {"unit": "kg", "value": 80},
            "activity_level": activity_level,
        }
    )

    assert profile["activity_level"] == activity_level


@pytest.mark.parametrize(
    "payload",
    [
        {
            "age": 3,
            "sex": "female",
            "height": {"unit": "cm", "value": 100},
            "weight": {"unit": "kg", "value": 20},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "other",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 60},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 60},
            "activity_level": "sometimes_active",
        },
        {
            "age": 20,
            "sex": "female",
            "height": {
                "unit": "ft_in",
                "feet": 5,
                "inches": 12,
            },
            "weight": {"unit": "kg", "value": 60},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "female",
            "height": {"unit": "meters", "value": 1.65},
            "weight": {"unit": "kg", "value": 60},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "stone", "value": 9},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "female",
            "height": {"unit": "cm", "value": 0},
            "weight": {"unit": "kg", "value": 60},
            "activity_level": None,
        },
        {
            "age": 20,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 0},
            "activity_level": None,
        },
    ],
)
def test_invalid_profile_inputs_are_rejected(payload):
    with pytest.raises(ProfileInputError):
        normalize_profile_payload(payload)


def test_female_profile_can_store_neither_status():
    profile = normalize_profile_payload(
        {
            "age": 31,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 63},
            "activity_level": "low_active",
            "pregnancy_lactation_status": "neither",
        }
    )

    assert profile["pregnancy_lactation_status"] == "neither"


@pytest.mark.parametrize(
    "status",
    [
        "pregnant",
        "lactating",
        "prefer_not_to_say",
    ],
)
def test_special_life_stage_statuses_are_accepted(status):
    profile = normalize_profile_payload(
        {
            "age": 31,
            "sex": "female",
            "height": {"unit": "cm", "value": 165},
            "weight": {"unit": "kg", "value": 63},
            "activity_level": "active",
            "pregnancy_lactation_status": status,
        }
    )

    assert profile["pregnancy_lactation_status"] == status


def test_male_profile_rejects_life_stage_status():
    with pytest.raises(ProfileInputError):
        normalize_profile_payload(
            {
                "age": 31,
                "sex": "male",
                "height": {"unit": "cm", "value": 180},
                "weight": {"unit": "kg", "value": 80},
                "activity_level": "active",
                "pregnancy_lactation_status": "pregnant",
            }
        )


def test_female_under_14_rejects_life_stage_status():
    with pytest.raises(ProfileInputError):
        normalize_profile_payload(
            {
                "age": 13,
                "sex": "female",
                "height": {"unit": "cm", "value": 150},
                "weight": {"unit": "kg", "value": 45},
                "activity_level": "active",
                "pregnancy_lactation_status": "pregnant",
            }
        )


def test_invalid_life_stage_status_is_rejected():
    with pytest.raises(ProfileInputError):
        normalize_profile_payload(
            {
                "age": 31,
                "sex": "female",
                "height": {"unit": "cm", "value": 165},
                "weight": {"unit": "kg", "value": 63},
                "activity_level": "active",
                "pregnancy_lactation_status": "unknown",
            }
        )


def test_standard_eer_requires_activity():
    from personalization_profile import (
        get_standard_eer_eligibility,
    )

    result = get_standard_eer_eligibility(
        {
            "age": 31,
            "sex": "male",
            "activity_level": None,
            "pregnancy_lactation_status": None,
        }
    )

    assert result == {
        "eligible": False,
        "reason": "activity_level_required",
    }


def test_female_14_plus_requires_life_stage_answer():
    from personalization_profile import (
        get_standard_eer_eligibility,
    )

    result = get_standard_eer_eligibility(
        {
            "age": 31,
            "sex": "female",
            "activity_level": "active",
            "pregnancy_lactation_status": None,
        }
    )

    assert result == {
        "eligible": False,
        "reason": "pregnancy_lactation_status_required",
    }


def test_neither_allows_standard_eer():
    from personalization_profile import (
        get_standard_eer_eligibility,
    )

    result = get_standard_eer_eligibility(
        {
            "age": 31,
            "sex": "female",
            "activity_level": "active",
            "pregnancy_lactation_status": "neither",
        }
    )

    assert result == {
        "eligible": True,
        "reason": None,
    }


@pytest.mark.parametrize(
    "status",
    [
        "pregnant",
        "lactating",
        "prefer_not_to_say",
    ],
)
def test_special_life_stage_blocks_standard_eer(status):
    from personalization_profile import (
        get_standard_eer_eligibility,
    )

    result = get_standard_eer_eligibility(
        {
            "age": 31,
            "sex": "female",
            "activity_level": "active",
            "pregnancy_lactation_status": status,
        }
    )

    assert result == {
        "eligible": False,
        "reason": "separate_life_stage_eer_required",
    }


def test_male_profile_can_use_standard_eer_without_life_stage():
    from personalization_profile import (
        get_standard_eer_eligibility,
    )

    result = get_standard_eer_eligibility(
        {
            "age": 31,
            "sex": "male",
            "activity_level": "active",
            "pregnancy_lactation_status": None,
        }
    )

    assert result == {
        "eligible": True,
        "reason": None,
    }
