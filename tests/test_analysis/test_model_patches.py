"""Tests for the fork-specific model patches applied between templater and translator."""

from types import SimpleNamespace

import pandas as pd

from analysis.model import apply_model_patches
from analysis.model.biomass_cap import apply as biomass_cap_apply
from analysis.model.flow_path_limits import apply as flow_path_limits_apply
from analysis.model.maintenance_overlay import apply as maintenance_overlay_apply
from analysis.model.pumped_storage_fix import apply as pumped_storage_fix_apply
from analysis.model.repowering import apply as repowering_apply
from analysis.model.rez_limits import apply as rez_limits_apply

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


def _rez_tables(csv_str_to_df) -> dict[str, pd.DataFrame]:
    """Two REZs, one REZ expansion option and one REZ group constraint beside a fork capacity cap."""
    return {
        "renewable_energy_zones": csv_str_to_df("""
            rez_id,  isp_sub_region_id,  carrier,  wind_generation_total_limits_mw_high,  wind_generation_total_limits_mw_medium,  wind_generation_total_limits_mw_offshore_floating,  wind_generation_total_limits_mw_offshore_fixed,  solar_pv_plus_solar_thermal_limits_mw_solar,  rez_resource_limit_violation_penalty_factor_$/mw,  rez_transmission_network_limit_summer_typical,  land_use_limits_mw_wind,  land_use_limits_mw_solar
            Q1,      NQ,                 AC,       570.0,                                 1710.0,                                 0.0,                                                0.0,                                             1100.0,                                       300000.0,                                          750.0,                                         6764.0,                  16234.0
            Q2,      NQ,                 AC,       4700.0,                                13900.0,                                0.0,                                                0.0,                                             8000.0,                                       300000.0,                                          700.0,                                         27529.0,                 66071.0
        """),
        "rez_transmission_expansion_costs": csv_str_to_df("""
            rez_constraint_id,  option,     additional_network_capacity_mw,  2024_25_$/mw
            CQ1,                Option__2,  1600.0,                          328962.0
            NQ1,                Option__2,  3000.0,                          1585005.0
        """),
        "custom_constraints_lhs": csv_str_to_df("""
            constraint_id,     term_type,           term_id,          coefficient
            NQ1,               link_flow,           Q1-NQ,            1.0
            biomass_cap_2030,  generator_capacity,  biomass_sq_2030,  1.0
        """),
        "custom_constraints_rhs": csv_str_to_df("""
            constraint_id,     constraint_type,  rhs
            NQ1,               <=,               2420.0
            biomass_cap_2030,  <=,               1468.0
        """),
    }


def test_rez_limits_doubles_every_rez_limit_and_leaves_prices_and_fork_caps_alone(
    csv_str_to_df, caplog
):
    tables = _rez_tables(csv_str_to_df)

    with caplog.at_level("WARNING"):
        result = rez_limits_apply(tables, _config([2030]), 2.0)

    expected_rez = csv_str_to_df("""
        rez_id,  isp_sub_region_id,  carrier,  wind_generation_total_limits_mw_high,  wind_generation_total_limits_mw_medium,  wind_generation_total_limits_mw_offshore_floating,  wind_generation_total_limits_mw_offshore_fixed,  solar_pv_plus_solar_thermal_limits_mw_solar,  rez_resource_limit_violation_penalty_factor_$/mw,  rez_transmission_network_limit_summer_typical,  land_use_limits_mw_wind,  land_use_limits_mw_solar
        Q1,      NQ,                 AC,       1140.0,                                3420.0,                                 0.0,                                                0.0,                                             2200.0,                                       300000.0,                                          1500.0,                                        13528.0,                 32468.0
        Q2,      NQ,                 AC,       9400.0,                                27800.0,                                0.0,                                                0.0,                                             16000.0,                                      300000.0,                                          1400.0,                                        55058.0,                 132142.0
    """)
    pd.testing.assert_frame_equal(result["renewable_energy_zones"], expected_rez)

    expected_expansion = csv_str_to_df("""
        rez_constraint_id,  option,     additional_network_capacity_mw,  2024_25_$/mw
        CQ1,                Option__2,  3200.0,                          328962.0
        NQ1,                Option__2,  6000.0,                          1585005.0
    """)
    pd.testing.assert_frame_equal(
        result["rez_transmission_expansion_costs"], expected_expansion
    )

    expected_rhs = csv_str_to_df("""
        constraint_id,     constraint_type,  rhs
        NQ1,               <=,               4840.0
        biomass_cap_2030,  <=,               1468.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_rhs"], expected_rhs)
    assert (
        "rez_limits: scaled ['custom_constraints_rhs', 'renewable_energy_zones', "
        "'rez_transmission_expansion_costs'] REZ limits by 2.0"
    ) in caplog.text


def test_rez_limits_leaves_the_iasr_limits_in_place_without_a_factor(
    csv_str_to_df, caplog
):
    tables = _rez_tables(csv_str_to_df)
    untouched = tables["renewable_energy_zones"].copy()

    with caplog.at_level("WARNING"):
        result = rez_limits_apply(tables, _config([2030]))

    pd.testing.assert_frame_equal(result["renewable_energy_zones"], untouched)
    assert "rez_limits" not in caplog.text


def _corridor_tables(csv_str_to_df) -> dict[str, pd.DataFrame]:
    """Two flow paths, and two REZ expansion options of which only ``Q1`` names a REZ connection."""
    return {
        "flow_path_expansion_costs": csv_str_to_df("""
            flow_path,   option,     additional_network_capacity_mw,  2024_25_$/mw
            CQ-NQ,       Option__3,  500.0,                           413868.0
            CNSW-NNSW,   Option__6,  1500.0,                          295713.0
        """),
        "rez_transmission_expansion_costs": csv_str_to_df("""
            rez_constraint_id,  option,     additional_network_capacity_mw,  2024_25_$/mw
            Q1,                 Option__1,  2580.0,                          328962.0
            NQ1,                Option__2,  3000.0,                          1585005.0
        """),
        "renewable_energy_zones": csv_str_to_df("""
            rez_id,  isp_sub_region_id
            Q1,      NQ
            Q2,      NQ
        """),
    }


def test_flow_path_limits_doubles_flow_path_headroom_and_leaves_prices_and_rez_tables_alone(
    csv_str_to_df, caplog
):
    tables = _corridor_tables(csv_str_to_df)

    with caplog.at_level("WARNING"):
        result = flow_path_limits_apply(tables, _config([2030]), 2.0)

    expected_flow_paths = csv_str_to_df("""
        flow_path,   option,     additional_network_capacity_mw,  2024_25_$/mw
        CQ-NQ,       Option__3,  1000.0,                          413868.0
        CNSW-NNSW,   Option__6,  3000.0,                          295713.0
    """)
    pd.testing.assert_frame_equal(
        result["flow_path_expansion_costs"], expected_flow_paths
    )

    pd.testing.assert_frame_equal(
        result["rez_transmission_expansion_costs"],
        tables["rez_transmission_expansion_costs"],
    )
    assert (
        "flow_path_limits: scaled ['flow_path_expansion_costs'] corridor expansion "
        "limits by 2.0"
    ) in caplog.text


def test_flow_path_limits_leaves_the_iasr_limits_in_place_without_a_factor(
    csv_str_to_df, caplog
):
    tables = _corridor_tables(csv_str_to_df)
    untouched = tables["flow_path_expansion_costs"].copy()

    with caplog.at_level("WARNING"):
        result = flow_path_limits_apply(tables, _config([2030]))

    pd.testing.assert_frame_equal(result["flow_path_expansion_costs"], untouched)
    assert "flow_path_limits" not in caplog.text


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
