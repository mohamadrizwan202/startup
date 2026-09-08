"""Pure deterministic personalization calculations for PureFyul.

No database, Flask, network, or AI dependencies.

Estimated Energy Requirement (EER) equations:
National Academies of Sciences, Engineering, and Medicine.
Dietary Reference Intakes for Energy (2023), Tables 5-15 and 5-16.
DOI: 10.17226/26818

Canonical units:
- age: years
- height: centimeters
- weight: kilograms
"""

from __future__ import annotations


VALID_SEXES = frozenset({"female", "male"})
VALID_ACTIVITY_LEVELS = frozenset(
    {
        "inactive",
        "low_active",
        "active",
        "very_active",
    }
)


class PersonalizationInputError(ValueError):
    """Raised when personalization inputs are outside the supported contract."""


# Coefficients are:
# intercept + age_coefficient*age
#           + height_coefficient*height_cm
#           + weight_coefficient*weight_kg
_CHILD_EER_COEFFICIENTS = {
    "male": {
        "inactive": (-447.51, 3.68, 13.01, 13.15),
        "low_active": (19.12, 3.68, 8.62, 20.28),
        "active": (-388.19, 3.68, 12.66, 20.46),
        "very_active": (-671.75, 3.68, 15.38, 23.25),
    },
    "female": {
        "inactive": (55.59, -22.25, 8.43, 17.07),
        "low_active": (-297.54, -22.25, 12.77, 14.73),
        "active": (-189.55, -22.25, 11.74, 18.34),
        "very_active": (-709.59, -22.25, 18.22, 14.25),
    },
}

_ADULT_EER_COEFFICIENTS = {
    "male": {
        "inactive": (753.07, -10.83, 6.50, 14.10),
        "low_active": (581.47, -10.83, 8.30, 14.94),
        "active": (1004.82, -10.83, 6.52, 15.91),
        "very_active": (-517.88, -10.83, 15.61, 19.11),
    },
    "female": {
        "inactive": (584.90, -7.01, 5.72, 11.71),
        "low_active": (575.77, -7.01, 6.60, 12.14),
        "active": (710.25, -7.01, 6.54, 12.34),
        "very_active": (511.83, -7.01, 9.07, 12.56),
    },
}


def _validate_profile_inputs(
    *,
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> None:
    if isinstance(age, bool) or not isinstance(age, int):
        raise PersonalizationInputError("age must be an integer number of years")

    if age < 4:
        raise PersonalizationInputError("PureFyul personalization supports age 4+")

    if sex not in VALID_SEXES:
        raise PersonalizationInputError(
            "sex must be 'female' or 'male'"
        )

    if activity_level not in VALID_ACTIVITY_LEVELS:
        raise PersonalizationInputError(
            "unsupported activity_level"
        )

    if isinstance(height_cm, bool) or not isinstance(height_cm, (int, float)):
        raise PersonalizationInputError("height_cm must be numeric")

    if isinstance(weight_kg, bool) or not isinstance(weight_kg, (int, float)):
        raise PersonalizationInputError("weight_kg must be numeric")

    if height_cm <= 0:
        raise PersonalizationInputError("height_cm must be greater than zero")

    if weight_kg <= 0:
        raise PersonalizationInputError("weight_kg must be greater than zero")


def calculate_bmi(*, height_cm: float, weight_kg: float) -> float:
    """Return numeric BMI from canonical metric measurements.

    This function calculates the number only. Interpretation/categories are
    intentionally separate because pediatric BMI is age- and sex-specific.
    """
    if isinstance(height_cm, bool) or not isinstance(height_cm, (int, float)):
        raise PersonalizationInputError("height_cm must be numeric")

    if isinstance(weight_kg, bool) or not isinstance(weight_kg, (int, float)):
        raise PersonalizationInputError("weight_kg must be numeric")

    if height_cm <= 0:
        raise PersonalizationInputError("height_cm must be greater than zero")

    if weight_kg <= 0:
        raise PersonalizationInputError("weight_kg must be greater than zero")

    height_m = float(height_cm) / 100.0
    return float(weight_kg) / (height_m * height_m)


def _child_growth_energy_kcal(*, age: int, sex: str) -> float:
    """Return the NASEM energy cost of growth for supported ages 4-18."""
    if 4 <= age <= 8:
        return 15.0

    if 9 <= age <= 13:
        return 25.0 if sex == "male" else 30.0

    if 14 <= age <= 18:
        return 20.0

    raise PersonalizationInputError(
        "child growth energy is only defined here for ages 4-18"
    )


def calculate_eer(
    *,
    age: int,
    sex: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
) -> float:
    """Calculate 2023 NASEM Estimated Energy Requirement in kcal/day."""

    _validate_profile_inputs(
        age=age,
        sex=sex,
        height_cm=height_cm,
        weight_kg=weight_kg,
        activity_level=activity_level,
    )

    if age <= 18:
        coefficients = _CHILD_EER_COEFFICIENTS[sex][activity_level]
        growth_kcal = _child_growth_energy_kcal(age=age, sex=sex)
    else:
        coefficients = _ADULT_EER_COEFFICIENTS[sex][activity_level]
        growth_kcal = 0.0

    intercept, age_coef, height_coef, weight_coef = coefficients

    return (
        intercept
        + (age_coef * age)
        + (height_coef * float(height_cm))
        + (weight_coef * float(weight_kg))
        + growth_kcal
    )
