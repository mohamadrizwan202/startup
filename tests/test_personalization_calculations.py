import pytest

from personalization import (
    PersonalizationInputError,
    calculate_bmi,
    calculate_eer,
)


def test_bmi_uses_canonical_metric_values():
    bmi = calculate_bmi(height_cm=175.0, weight_kg=70.0)
    assert bmi == pytest.approx(22.8571428571)


def test_nasem_worked_example_adult_female_low_active():
    # NASEM 2023, Chapter 7:
    # 22-year-old woman, 165 cm, 63 kg, low active -> 2,275 kcal/day.
    eer = calculate_eer(
        age=22,
        sex="female",
        height_cm=165.0,
        weight_kg=63.0,
        activity_level="low_active",
    )
    assert eer == pytest.approx(2275.37, abs=0.01)
    assert round(eer) == 2275


def test_nasem_worked_example_adolescent_male_active():
    # NASEM 2023, Chapter 7:
    # 15-year-old boy, 170 cm, 66 kg, active -> 3,190 kcal/day.
    eer = calculate_eer(
        age=15,
        sex="male",
        height_cm=170.0,
        weight_kg=66.0,
        activity_level="active",
    )
    assert eer == pytest.approx(3189.57, abs=0.01)
    assert round(eer) == 3190


def test_nasem_worked_example_older_adult_female_inactive():
    # NASEM 2023, Chapter 7:
    # 70-year-old woman, 157 cm, 70 kg, inactive -> 1,812 kcal/day.
    eer = calculate_eer(
        age=70,
        sex="female",
        height_cm=157.0,
        weight_kg=70.0,
        activity_level="inactive",
    )
    assert eer == pytest.approx(1811.94, abs=0.01)
    assert round(eer) == 1812


@pytest.mark.parametrize(
    ("age", "sex", "expected_growth"),
    [
        (4, "male", 15.0),
        (8, "female", 15.0),
        (9, "male", 25.0),
        (13, "male", 25.0),
        (9, "female", 30.0),
        (13, "female", 30.0),
        (14, "male", 20.0),
        (18, "female", 20.0),
    ],
)
def test_child_growth_allowance_boundaries(age, sex, expected_growth):
    # Compare the public result with the underlying equation minus growth.
    kwargs = dict(
        age=age,
        sex=sex,
        height_cm=150.0,
        weight_kg=45.0,
        activity_level="inactive",
    )

    eer = calculate_eer(**kwargs)

    if sex == "male":
        without_growth = (
            -447.51
            + (3.68 * age)
            + (13.01 * 150.0)
            + (13.15 * 45.0)
        )
    else:
        without_growth = (
            55.59
            - (22.25 * age)
            + (8.43 * 150.0)
            + (17.07 * 45.0)
        )

    assert eer - without_growth == pytest.approx(expected_growth)


def test_age_19_routes_to_adult_equation_without_growth_allowance():
    eer = calculate_eer(
        age=19,
        sex="male",
        height_cm=175.0,
        weight_kg=70.0,
        activity_level="inactive",
    )

    expected = (
        753.07
        - (10.83 * 19)
        + (6.50 * 175.0)
        + (14.10 * 70.0)
    )

    assert eer == pytest.approx(expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "age": 3,
            "sex": "male",
            "height_cm": 100.0,
            "weight_kg": 16.0,
            "activity_level": "inactive",
        },
        {
            "age": 20,
            "sex": "invalid",
            "height_cm": 170.0,
            "weight_kg": 70.0,
            "activity_level": "inactive",
        },
        {
            "age": 20,
            "sex": "male",
            "height_cm": 0.0,
            "weight_kg": 70.0,
            "activity_level": "inactive",
        },
        {
            "age": 20,
            "sex": "male",
            "height_cm": 170.0,
            "weight_kg": -1.0,
            "activity_level": "inactive",
        },
        {
            "age": 20,
            "sex": "male",
            "height_cm": 170.0,
            "weight_kg": 70.0,
            "activity_level": "moderate",
        },
    ],
)
def test_invalid_personalization_inputs_are_rejected(kwargs):
    with pytest.raises(PersonalizationInputError):
        calculate_eer(**kwargs)
