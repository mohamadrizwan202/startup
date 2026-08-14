"""Validation and unit normalization for PureFyul personalization profiles.

This module contains no Flask, database, network, or AI dependencies.

Canonical storage:
- height_cm
- weight_kg

Display/input preferences:
- height: cm | ft_in
- weight: kg | lb
"""

from __future__ import annotations

from personalization import VALID_ACTIVITY_LEVELS, VALID_SEXES


VALID_HEIGHT_UNITS = frozenset({"cm", "ft_in"})
VALID_WEIGHT_UNITS = frozenset({"kg", "lb"})

CM_PER_INCH = 2.54
KG_PER_LB = 0.45359237


class ProfileInputError(ValueError):
    """Raised when personalization profile input is invalid."""


def _require_number(value, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileInputError(f"{field_name} must be numeric")

    number = float(value)

    if number <= 0:
        raise ProfileInputError(f"{field_name} must be greater than zero")

    return number


def _normalize_age(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileInputError("age must be an integer number of years")

    if value < 4:
        raise ProfileInputError("PureFyul personalization supports age 4+")

    return value


def _normalize_height(height) -> tuple[float, str]:
    if not isinstance(height, dict):
        raise ProfileInputError("height must be an object")

    unit = height.get("unit")

    if unit not in VALID_HEIGHT_UNITS:
        raise ProfileInputError("height unit must be 'cm' or 'ft_in'")

    if unit == "cm":
        height_cm = _require_number(height.get("value"), "height.value")
        return height_cm, "cm"

    feet = height.get("feet")
    inches = height.get("inches")

    if isinstance(feet, bool) or not isinstance(feet, int):
        raise ProfileInputError("height.feet must be an integer")

    if feet < 0:
        raise ProfileInputError("height.feet cannot be negative")

    if isinstance(inches, bool) or not isinstance(inches, (int, float)):
        raise ProfileInputError("height.inches must be numeric")

    inches = float(inches)

    if inches < 0 or inches >= 12:
        raise ProfileInputError(
            "height.inches must be greater than or equal to 0 and less than 12"
        )

    total_inches = (feet * 12) + inches

    if total_inches <= 0:
        raise ProfileInputError("height must be greater than zero")

    return total_inches * CM_PER_INCH, "ft_in"


def _normalize_weight(weight) -> tuple[float, str]:
    if not isinstance(weight, dict):
        raise ProfileInputError("weight must be an object")

    unit = weight.get("unit")

    if unit not in VALID_WEIGHT_UNITS:
        raise ProfileInputError("weight unit must be 'kg' or 'lb'")

    value = _require_number(weight.get("value"), "weight.value")

    if unit == "kg":
        return value, "kg"

    return value * KG_PER_LB, "lb"


def normalize_profile_payload(data) -> dict:
    """Validate profile JSON and convert measurements to canonical units.

    Expected height forms:

        {"unit": "cm", "value": 165}

        {"unit": "ft_in", "feet": 5, "inches": 5}

    Expected weight forms:

        {"unit": "kg", "value": 63}

        {"unit": "lb", "value": 139}

    activity_level may be null when the user selects "Not sure".
    """

    if not isinstance(data, dict):
        raise ProfileInputError("profile must be a JSON object")

    age = _normalize_age(data.get("age"))

    sex = data.get("sex")
    if sex not in VALID_SEXES:
        raise ProfileInputError("sex must be 'female' or 'male'")

    activity_level = data.get("activity_level")

    # Product meaning: blank/null = "Not sure".
    if activity_level == "":
        activity_level = None

    if (
        activity_level is not None
        and activity_level not in VALID_ACTIVITY_LEVELS
    ):
        raise ProfileInputError("unsupported activity_level")

    height_cm, preferred_height_unit = _normalize_height(
        data.get("height")
    )

    weight_kg, preferred_weight_unit = _normalize_weight(
        data.get("weight")
    )

    return {
        "age": age,
        "sex": sex,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "activity_level": activity_level,
        "preferred_height_unit": preferred_height_unit,
        "preferred_weight_unit": preferred_weight_unit,
    }
