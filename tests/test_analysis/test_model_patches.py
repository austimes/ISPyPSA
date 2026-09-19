"""Tests for the fork-specific model patches applied between templater and translator."""

from types import SimpleNamespace

import pandas as pd

from analysis.model import apply_model_patches
from analysis.model.biomass_cap import apply as biomass_cap_apply
from analysis.model.maintenance_overlay import apply as maintenance_overlay_apply
from analysis.model.pumped_storage_fix import apply as pumped_storage_fix_apply
from analysis.model.repowering import apply as repowering_apply

_EMPTY_CC_LHS = pd.DataFrame(
    columns=["constraint_id", "term_type", "term_id", "coefficient"]
)
_EMPTY_CC_RHS = pd.DataFrame(columns=["constraint_id", "constraint_type", "rhs"])


def _config(investment_periods: list[int]) -> SimpleNamespace:
    """Minimal stand-in for ModelConfig, carrying only what the patches read.

    Without a ``paths.parsed_workbook_cache`` the PHES menu stands down, so a patch run
    against this config needs no cached workbook tables.
    """
    return SimpleNamespace(
        temporal=SimpleNamespace(
            capacity_expansion=SimpleNamespace(investment_periods=investment_periods)
        )
    )


def test_maintenance_overlay_adds_the_ageing_premium_inside_the_eol_window(
    csv_str_to_df,
):
    # Coal closing five years after the first period: premium = (10 - 5) / 10 * 50.
    ecaa = csv_str_to_df("""
        generator,  fuel_type,    closure_year,  fom_$/kw/annum
        CoalEOL,    Black__Coal,  2035,          60.0
        CoalFar,    Black__Coal,  2050,          60.0
    """)

    result = maintenance_overlay_apply({"ecaa_generators": ecaa}, _config([2030]))

    expected = csv_str_to_df("""
        generator,  fuel_type,    closure_year,  fom_$/kw/annum
        CoalEOL,    Black__Coal,  2035,          85.0
        CoalFar,    Black__Coal,  2050,          60.0
    """)
    pd.testing.assert_frame_equal(result["ecaa_generators"], expected)


def test_repowering_extends_vre_life_and_charges_annualised_repowering_capex(
    csv_str_to_df,
):
    # Wind closing 15 years out: closure_year + 20, premium = 1,000 / (15 + 20).
    ecaa = csv_str_to_df("""
        generator,  fuel_type,     closure_year,  fom_$/kw/annum
        WindA,      Wind,          2045,          25.0
        Coal1,      Black__Coal,   2040,          60.0
    """)

    result = repowering_apply({"ecaa_generators": ecaa}, _config([2030]))

    expected = csv_str_to_df("""
        generator,  fuel_type,     closure_year,  fom_$/kw/annum
        WindA,      Wind,          2065,          53.571428571
        Coal1,      Black__Coal,   2040,          60.0
    """)
    pd.testing.assert_frame_equal(
        result["ecaa_generators"], expected, check_exact=False, rtol=1e-8
    )


def test_biomass_cap_nets_existing_biomass_off_the_new_entrant_ceiling(csv_str_to_df):
    # The 2030 cap is 1,500 MW and 32 MW of existing biomass survives 2030.
    new_entrants = csv_str_to_df("""
        generator,    fuel_type,  lifetime
        biomass_sq,   Biomass,    30
        wind_sq,      Wind,       25
    """)
    ecaa = csv_str_to_df("""
        generator,   fuel_type,  closure_year,  maximum_capacity_mw
        TullyMill,   Biomass,    2035,          32.0
    """)
    tables = {
        "new_entrant_generators": new_entrants,
        "ecaa_generators": ecaa,
        "custom_constraints_lhs": _EMPTY_CC_LHS.copy(),
        "custom_constraints_rhs": _EMPTY_CC_RHS.copy(),
    }

    result = biomass_cap_apply(tables, _config([2030]))

    expected_lhs = csv_str_to_df("""
        constraint_id,     term_type,           term_id,          coefficient
        biomass_cap_2030,  generator_capacity,  biomass_sq_2030,  1.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_lhs"], expected_lhs)

    expected_rhs = csv_str_to_df("""
        constraint_id,     constraint_type,  rhs
        biomass_cap_2030,  <=,               1468.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_rhs"], expected_rhs)


def test_pumped_storage_fix_removes_pumped_hydro_from_the_generator_roster(
    csv_str_to_df,
):
    ecaa = csv_str_to_df("""
        generator,     sub_region_id,  fuel_type
        Wivenhoe,      SQ,             Water
        Kogan__Creek,  SQ,             Black__Coal
    """)

    result = pumped_storage_fix_apply({"ecaa_generators": ecaa}, _config([2030]))

    expected = csv_str_to_df("""
        generator,     sub_region_id,  fuel_type
        Kogan__Creek,  SQ,             Black__Coal
    """)
    pd.testing.assert_frame_equal(result["ecaa_generators"], expected)


def test_apply_model_patches_returns_every_table_the_patches_touch(csv_str_to_df):
    ecaa = csv_str_to_df("""
        generator,   sub_region_id,  fuel_type,  closure_year,  maximum_capacity_mw,  fom_$/kw/annum
        Wivenhoe,    SQ,             Water,      2084,          570.0,                0.0
        CoalEOL,     SQ,             Black__Coal, 2035,         700.0,                60.0
    """)
    new_entrants = csv_str_to_df("""
        generator,    fuel_type,  lifetime
        biomass_sq,   Biomass,    30
    """)
    tables = {
        "ecaa_generators": ecaa,
        "new_entrant_generators": new_entrants,
        "custom_constraints_lhs": _EMPTY_CC_LHS.copy(),
        "custom_constraints_rhs": _EMPTY_CC_RHS.copy(),
    }

    result = apply_model_patches(tables, _config([2030]))

    assert sorted(result) == [
        "custom_constraints_lhs",
        "custom_constraints_rhs",
        "ecaa_batteries",
        "ecaa_generators",
        "new_entrant_generators",
    ]
