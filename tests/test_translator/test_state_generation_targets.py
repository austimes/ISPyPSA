import pandas as pd

from ispypsa.translator.state_generation_targets import (
    _calculate_distributed_pv_energy,
    _combine_state_generation_targets,
    _translate_state_generation_targets,
)

_BUS_REGIONS = {
    "CNSW": "NSW",
    "N1": "NSW",
    "SEV": "VIC",
    "WNV": "VIC",
    "TAS": "TAS",
    "CSA": "SA",
    "SESA": "SA",
    "S1": "SA",
}
_NO_LINKS = pd.DataFrame(columns=["name", "bus0", "bus1"])
_NO_DISTRIBUTED_PV = pd.DataFrame(
    columns=["region_id", "investment_period", "distributed_pv_mwh"]
).astype({"investment_period": int})


def _sorted(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return df.sort_values(by).reset_index(drop=True)


def test_nsw_roadmap_counts_eligible_capacity_weighted_by_available_energy(
    csv_str_to_df,
):
    targets = csv_str_to_df("""
        FY,       region_id,  policy_id,    target
        2027_28,  NSW,        nsw_iio_gen,  1000.0
        2029_30,  NSW,        nsw_iio_gen,  3000.0
    """)
    generators = csv_str_to_df("""
        name,           bus,   carrier,  build_year,  lifetime
        old_wind,       CNSW,  Wind,     2015,        30
        new_solar,      N1,    Solar,    2029,        30
        new_biomass,    CNSW,  Biomass,  2027,        30
        snowy_hydro,    CNSW,  Water,    2015,        50
        new_gas,        CNSW,  Gas,      2027,        30
        vic_wind,       SEV,   Wind,     2027,        30
    """)

    lhs, rhs = _translate_state_generation_targets(
        targets,
        generators,
        _NO_LINKS,
        _BUS_REGIONS,
        [2028, 2030],
        _NO_DISTRIBUTED_PV,
        ["old_wind"],
    )

    expected_rhs = csv_str_to_df("""
        constraint_name,   rhs,     constraint_type,  investment_period
        nsw_iio_gen_2028,  1000.0,  >=,               2028
        nsw_iio_gen_2030,  3000.0,  >=,               2030
    """)
    pd.testing.assert_frame_equal(_sorted(rhs, ["constraint_name"]), expected_rhs)
    expected_lhs = csv_str_to_df("""
        constraint_name,   variable_name,  coefficient,  component,  attribute
        nsw_iio_gen_2028,  new_biomass,    1.0,          Generator,  available_energy
        nsw_iio_gen_2030,  new_biomass,    1.0,          Generator,  available_energy
        nsw_iio_gen_2030,  new_solar,      1.0,          Generator,  available_energy
    """)
    pd.testing.assert_frame_equal(
        _sorted(lhs, ["constraint_name", "variable_name"]), expected_lhs
    )


def test_vret_share_is_linear_in_generation_with_distributed_pv_constant(
    csv_str_to_df,
):
    targets = csv_str_to_df("""
        FY,       region_id,  policy_id,  target
        2024_25,  VIC,        vret,       0.4
        2029_30,  VIC,        vret,       0.65
    """)
    generators = csv_str_to_df("""
        name,        bus,   carrier,     build_year,  lifetime
        vic_wind,    WNV,   Wind,        2020,        30
        vic_coal,    SEV,   Brown__Coal, 2000,        40
        vic_bess,    SEV,   Battery,     2020,        20
        tas_hydro,   TAS,   Water,       1950,        100
    """)
    distributed_pv = csv_str_to_df("""
        region_id,  investment_period,  distributed_pv_mwh
        VIC,        2026,               1000.0
        VIC,        2030,               2000.0
    """)

    lhs, rhs = _translate_state_generation_targets(
        targets, generators, _NO_LINKS, _BUS_REGIONS, [2026, 2030], distributed_pv, []
    )

    expected_rhs = csv_str_to_df("""
        constraint_name,  rhs,     constraint_type,  investment_period
        vret_2026,        -600.0,  >=,               2026
        vret_2030,        -700.0,  >=,               2030
    """)
    pd.testing.assert_frame_equal(_sorted(rhs, ["constraint_name"]), expected_rhs)
    expected_lhs = csv_str_to_df("""
        constraint_name,  variable_name,  coefficient,  component,  attribute
        vret_2026,        vic_coal,       -0.4,         Generator,  energy
        vret_2026,        vic_wind,       0.6,          Generator,  energy
        vret_2030,        vic_coal,       -0.65,        Generator,  energy
        vret_2030,        vic_wind,       0.35,         Generator,  energy
    """)
    pd.testing.assert_frame_equal(
        _sorted(lhs, ["constraint_name", "variable_name"]), expected_lhs
    )


def test_tret_subtracts_distributed_pv_and_holds_after_last_target(csv_str_to_df):
    targets = csv_str_to_df("""
        FY,       region_id,  policy_id,  target
        2029_30,  TAS,        tret,       15750000.0
    """)
    generators = csv_str_to_df("""
        name,        bus,   carrier,  build_year,  lifetime
        tas_hydro,   TAS,   Water,    1950,        100
        tas_wind,    TAS,   Wind,     2031,        30
        tas_gas,     TAS,   Gas,      2009,        40
        tas_biomass, TAS,   Biomass,  2020,        30
    """)
    distributed_pv = csv_str_to_df("""
        region_id,  investment_period,  distributed_pv_mwh
        TAS,        2028,               500000.0
        TAS,        2030,               600000.0
        TAS,        2035,               700000.0
    """)

    lhs, rhs = _translate_state_generation_targets(
        targets,
        generators,
        _NO_LINKS,
        _BUS_REGIONS,
        [2028, 2030, 2035],
        distributed_pv,
        [],
    )

    expected_rhs = csv_str_to_df("""
        constraint_name,  rhs,         constraint_type,  investment_period
        tret_2030,        15150000.0,  >=,               2030
        tret_2035,        15050000.0,  >=,               2035
    """)
    pd.testing.assert_frame_equal(_sorted(rhs, ["constraint_name"]), expected_rhs)
    expected_lhs = csv_str_to_df("""
        constraint_name,  variable_name,  coefficient,  component,  attribute
        tret_2030,        tas_hydro,      1.0,          Generator,  energy
        tret_2035,        tas_hydro,      1.0,          Generator,  energy
        tret_2035,        tas_wind,       1.0,          Generator,  energy
    """)
    pd.testing.assert_frame_equal(
        _sorted(lhs, ["constraint_name", "variable_name"]), expected_lhs
    )


def test_sa_net_exports_must_cover_fossil_generation(csv_str_to_df):
    targets = csv_str_to_df("""
        FY,       region_id,  policy_id,         target
        2026_27,  SA,         sa_net_renewable,  1.0
    """)
    generators = csv_str_to_df("""
        name,       bus,   carrier,      build_year,  lifetime
        sa_gas,     CSA,   Gas,          2000,        40
        sa_diesel,  SESA,  Liquid__Fuel, 2000,        40
        sa_wind,    S1,    Wind,         2020,        30
        vic_gas,    SEV,   Gas,          2000,        40
    """)
    links = csv_str_to_df("""
        name,           bus0,  bus1
        SESA-WNV,       SESA,  WNV
        SEV-CSA,        SEV,   CSA
        S1-CSA,         S1,    CSA
        CNSW-SEV,       CNSW,  SEV
    """)

    lhs, rhs = _translate_state_generation_targets(
        targets, generators, links, _BUS_REGIONS, [2030], _NO_DISTRIBUTED_PV, []
    )

    expected_rhs = csv_str_to_df("""
        constraint_name,        rhs,  constraint_type,  investment_period
        sa_net_renewable_2030,  0.0,  >=,               2030
    """)
    pd.testing.assert_frame_equal(rhs, expected_rhs)
    expected_lhs = csv_str_to_df("""
        constraint_name,        variable_name,  coefficient,  component,  attribute
        sa_net_renewable_2030,  SESA-WNV,       1.0,          Link,       energy
        sa_net_renewable_2030,  SEV-CSA,        -1.0,         Link,       energy
        sa_net_renewable_2030,  sa_diesel,      -1.0,         Generator,  energy
        sa_net_renewable_2030,  sa_gas,         -1.0,         Generator,  energy
    """)
    pd.testing.assert_frame_equal(_sorted(lhs, ["variable_name"]), expected_lhs)


def test_combine_state_generation_targets_converts_shares_to_fractions(
    csv_str_to_df,
):
    generation = csv_str_to_df("""
        FY,       region_id,  policy_id,  capacity_mwh
        2029_30,  TAS,        tret,       15750000.0
    """)
    shares = csv_str_to_df("""
        FY,       region_id,  policy_id,  pct
        2024_25,  VIC,        vret,       40.0
    """)

    result = _combine_state_generation_targets(generation, shares)

    expected = csv_str_to_df("""
        FY,       region_id,  policy_id,  target
        2029_30,  TAS,        tret,       15750000.0
        2024_25,  VIC,        vret,       0.4
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_calculate_distributed_pv_energy(csv_str_to_df):
    demand_traces = csv_str_to_df("""
        subregion,  demand_type,            value,  investment_period
        MEL,        OPSO_MODELLING_PVLITE,  110.0,  2030
        MEL,        OPSO_MODELLING_PVLITE,  130.0,  2030
        MEL,        OPSO_MODELLING,         100.0,  2030
        MEL,        OPSO_MODELLING,         100.0,  2030
        SEV,        OPSO_MODELLING_PVLITE,  50.0,   2030
        SEV,        OPSO_MODELLING,         40.0,   2030
        TAS,        OPSO_MODELLING_PVLITE,  20.0,   2030
        TAS,        OPSO_MODELLING,         19.0,   2030
    """)
    sub_regions = csv_str_to_df("""
        isp_sub_region_id,  nem_region_id
        MEL,                VIC
        SEV,                VIC
        TAS,                TAS
    """)

    result = _calculate_distributed_pv_energy(demand_traces, sub_regions)

    expected = csv_str_to_df("""
        region_id,  investment_period,  distributed_pv_mwh
        TAS,        2030,               8760.0
        VIC,        2030,               262800.0
    """)
    pd.testing.assert_frame_equal(result, expected)
