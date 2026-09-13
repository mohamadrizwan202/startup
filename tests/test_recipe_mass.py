import pytest

from recipe_mass import (
    RecipeMassResolutionError,
    normalize_recipe_ingredient_mass,
    normalize_recipe_mass,
)


def test_gram_input_is_preserved():
    result = normalize_recipe_ingredient_mass(
        ingredient="banana",
        nutrition_lookup_name="banana",
        amount=118,
        unit="g",
    )

    assert result == {
        "ingredient": "banana",
        "nutrition_lookup_name": "banana",
        "weight_g": 118.0,
        "mass_source": "gram_input",
    }


def test_gram_input_is_not_rounded():
    result = normalize_recipe_ingredient_mass(
        ingredient="flax seeds",
        nutrition_lookup_name="flax seeds",
        amount=6.125,
        unit="g",
    )

    assert result["weight_g"] == 6.125


def test_lemon_juice_ml_uses_explicit_household_weight_conversion():
    result = normalize_recipe_ingredient_mass(
        ingredient="Lemon Juice",
        nutrition_lookup_name="lemon juice",
        amount=5,
        unit="ml",
    )

    assert result["weight_g"] == pytest.approx(
        5 * (244 / 240)
    )

    assert (
        result["mass_source"]
        == "explicit_household_weight_conversion"
    )


def test_lime_juice_ml_uses_explicit_household_weight_conversion():
    result = normalize_recipe_ingredient_mass(
        ingredient="Lime Juice",
        nutrition_lookup_name="lime juice",
        amount=5,
        unit="ml",
    )

    assert result["weight_g"] == pytest.approx(
        5 * (242 / 240)
    )


def test_citrus_lookup_matching_is_case_insensitive():
    result = normalize_recipe_ingredient_mass(
        ingredient="Lemon Juice",
        nutrition_lookup_name="  LEMON JUICE  ",
        amount=5,
        unit="ML",
    )

    assert result["weight_g"] == pytest.approx(
        5 * (244 / 240)
    )


@pytest.mark.parametrize(
    "lookup_name",
    [
        "pea milk",
        "flax milk",
        "coconut milk",
        "water",
    ],
)
def test_unresolved_volume_inputs_fail_closed(
    lookup_name,
):
    with pytest.raises(
        RecipeMassResolutionError,
        match="mass conversion is unresolved",
    ):
        normalize_recipe_ingredient_mass(
            ingredient=lookup_name,
            nutrition_lookup_name=lookup_name,
            amount=150,
            unit="ml",
        )


@pytest.mark.parametrize(
    "unit",
    [
        "cup",
        "oz",
        "l",
        "",
        None,
    ],
)
def test_unsupported_units_are_rejected(unit):
    with pytest.raises(RecipeMassResolutionError):
        normalize_recipe_ingredient_mass(
            ingredient="banana",
            nutrition_lookup_name="banana",
            amount=118,
            unit=unit,
        )


@pytest.mark.parametrize(
    "amount",
    [
        None,
        True,
        "100",
        0,
        -1,
        float("nan"),
        float("inf"),
    ],
)
def test_invalid_amounts_are_rejected(amount):
    with pytest.raises(RecipeMassResolutionError):
        normalize_recipe_ingredient_mass(
            ingredient="banana",
            nutrition_lookup_name="banana",
            amount=amount,
            unit="g",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("ingredient", None),
        ("ingredient", ""),
        ("ingredient", "   "),
        ("nutrition_lookup_name", None),
        ("nutrition_lookup_name", ""),
        ("nutrition_lookup_name", "   "),
    ],
)
def test_required_identity_fields_are_rejected(
    field,
    value,
):
    kwargs = {
        "ingredient": "banana",
        "nutrition_lookup_name": "banana",
        "amount": 118,
        "unit": "g",
    }

    kwargs[field] = value

    with pytest.raises(RecipeMassResolutionError):
        normalize_recipe_ingredient_mass(**kwargs)


def test_recipe_normalization_resolves_mixed_safe_inputs():
    result = normalize_recipe_mass(
        [
            {
                "ingredient": "banana",
                "nutrition_lookup_name": "banana",
                "amount": 118,
                "unit": "g",
            },
            {
                "ingredient": "Lemon Juice",
                "nutrition_lookup_name": "lemon juice",
                "amount": 5,
                "unit": "ml",
            },
        ]
    )

    assert len(result) == 2
    assert result[0]["weight_g"] == 118.0

    assert result[1]["weight_g"] == pytest.approx(
        5 * (244 / 240)
    )


def test_recipe_normalization_rejects_one_unresolved_liquid():
    with pytest.raises(
        RecipeMassResolutionError,
        match="index 1",
    ):
        normalize_recipe_mass(
            [
                {
                    "ingredient": "banana",
                    "nutrition_lookup_name": "banana",
                    "amount": 118,
                    "unit": "g",
                },
                {
                    "ingredient": "coconut milk",
                    "nutrition_lookup_name": "coconut milk",
                    "amount": 150,
                    "unit": "ml",
                },
            ]
        )


@pytest.mark.parametrize(
    "ingredients",
    [
        None,
        {},
        "banana",
        [],
        (),
    ],
)
def test_invalid_recipe_collections_are_rejected(
    ingredients,
):
    with pytest.raises(RecipeMassResolutionError):
        normalize_recipe_mass(ingredients)



def test_oat_milk_uses_explicit_density_conversion():
    import math

    result = normalize_recipe_ingredient_mass(
        ingredient="Oat Milk",
        nutrition_lookup_name="oat milk",
        amount=240.0,
        unit="ml",
    )

    assert math.isclose(
        result["weight_g"],
        246.096,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert result["mass_source"] == "explicit_density_conversion"


def test_oat_milk_volume_mass_round_trip():
    import math

    from recipe_mass import convert_liquid_grams_to_ml

    cases = (
        (70.0, 71.778),
        (240.0, 246.096),
        (260.0, 266.604),
    )

    for volume_ml, expected_weight_g in cases:
        result = normalize_recipe_ingredient_mass(
            ingredient="Oat Milk",
            nutrition_lookup_name="oat milk",
            amount=volume_ml,
            unit="ml",
        )

        assert math.isclose(
            result["weight_g"],
            expected_weight_g,
            rel_tol=0.0,
            abs_tol=1e-9,
        )

        restored_ml = convert_liquid_grams_to_ml(
            nutrition_lookup_name="oat milk",
            weight_g=result["weight_g"],
        )

        assert math.isclose(
            restored_ml,
            volume_ml,
            rel_tol=0.0,
            abs_tol=1e-9,
        )



@pytest.mark.parametrize(
    "lookup_name,grams_per_ml,mass_source",
    [
        ("soy milk", 1.0133, "explicit_density_conversion"),
        ("almond milk", 1.0002, "explicit_density_conversion"),
        ("rice milk", 1.0496, "explicit_density_conversion"),
        (
            "hemp milk",
            1.0286,
            "explicit_specific_gravity_conversion",
        ),
        (
            "macadamia milk",
            0.9910,
            "explicit_density_conversion",
        ),
        ("cashew milk", 1.0300, "explicit_density_conversion"),
    ],
)
def test_v1_plant_milk_mass_conversions(
    lookup_name,
    grams_per_ml,
    mass_source,
):
    from recipe_mass import convert_liquid_grams_to_ml

    for volume_ml in (70.0, 260.0):
        result = normalize_recipe_ingredient_mass(
            ingredient=lookup_name.title(),
            nutrition_lookup_name=lookup_name,
            amount=volume_ml,
            unit="ml",
        )

        expected_weight = volume_ml * grams_per_ml

        assert result["weight_g"] == pytest.approx(
            expected_weight
        )
        assert result["mass_source"] == mass_source

        restored_ml = convert_liquid_grams_to_ml(
            nutrition_lookup_name=lookup_name,
            weight_g=result["weight_g"],
        )

        assert restored_ml == pytest.approx(volume_ml)


def test_coconut_milk_does_not_alias_coconut_beverage():
    with pytest.raises(
        RecipeMassResolutionError,
        match="mass conversion is unresolved",
    ):
        normalize_recipe_ingredient_mass(
            ingredient="Coconut Milk",
            nutrition_lookup_name="coconut milk",
            amount=240.0,
            unit="ml",
        )



def test_coconut_water_specific_gravity_conversion():
    from recipe_mass import convert_liquid_grams_to_ml

    cases = (
        (100.0, 102.0),
        (240.0, 244.8),
    )

    for volume_ml, expected_weight_g in cases:
        result = normalize_recipe_ingredient_mass(
            ingredient="Coconut Water",
            nutrition_lookup_name="coconut water",
            amount=volume_ml,
            unit="ml",
        )

        assert result["weight_g"] == pytest.approx(
            expected_weight_g
        )
        assert (
            result["mass_source"]
            == "explicit_specific_gravity_conversion"
        )

        restored_ml = convert_liquid_grams_to_ml(
            nutrition_lookup_name="coconut water",
            weight_g=result["weight_g"],
        )

        assert restored_ml == pytest.approx(volume_ml)



def test_coconut_beverage_is_not_in_v1():
    with pytest.raises(
        RecipeMassResolutionError,
        match="mass conversion is unresolved",
    ):
        normalize_recipe_ingredient_mass(
            ingredient="Coconut Beverage",
            nutrition_lookup_name="coconut beverage",
            amount=240.0,
            unit="ml",
        )


def test_kefir_uses_explicit_density_conversion():
    result = normalize_recipe_ingredient_mass(
        ingredient="Kefir",
        nutrition_lookup_name="kefir",
        amount=90.0,
        unit="ml",
    )

    assert result["weight_g"] == pytest.approx(92.700)
    assert result["mass_source"] == "explicit_density_conversion"


def test_kefir_volume_mass_round_trip():
    from recipe_mass import convert_liquid_grams_to_ml

    cases = (
        (90.0, 92.700),
        (250.0, 257.500),
    )

    for volume_ml, expected_weight_g in cases:
        result = normalize_recipe_ingredient_mass(
            ingredient="Kefir",
            nutrition_lookup_name="kefir",
            amount=volume_ml,
            unit="ml",
        )

        assert result["weight_g"] == pytest.approx(
            expected_weight_g
        )

        restored_ml = convert_liquid_grams_to_ml(
            nutrition_lookup_name="kefir",
            weight_g=result["weight_g"],
        )

        assert restored_ml == pytest.approx(volume_ml)


def test_other_kefir_identity_does_not_inherit_kefir_conversion():
    with pytest.raises(
        RecipeMassResolutionError,
        match="mass conversion is unresolved",
    ):
        normalize_recipe_ingredient_mass(
            ingredient="Water Kefir",
            nutrition_lookup_name="water kefir",
            amount=100.0,
            unit="ml",
        )
