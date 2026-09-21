import pandas as pd

from analysis.env import OutputLayout
from analysis.hpc.campaign_grid import order_pressures
from analysis.sharp.deliverables import (
    _add_load_shedding,
    _add_unpriced_fuel,
    _cost_monotone_rows,
    _marginals,
    _templated_cost_rows,
    _write_input_costs,
)

_TRAJECTORY_ORDER = ["low", "central", "stress"]


def test_boundary_rule_flags_only_cells_shedding_above_the_threshold(csv_str_to_df):
    cells = csv_str_to_df("""
        cell,               year,  delivered_twh,  use_mwh
        ext_low_cap002,     2050,  100.0,          0.0
        ext_central_cap002, 2050,  100.0,          100000.0
        ext_stress_cap002,  2050,  100.0,          100001.0
        ext_low_cap0001,    2050,  100.0,          4200000.0
    """)

    result = _add_load_shedding(cells)

    expected = csv_str_to_df("""
        cell,               year,  delivered_twh,  use_mwh,    use_pct_of_demand,  served_twh,  boundary
        ext_low_cap002,     2050,  100.0,          0.0,        0.0,                100.0,       False
        ext_central_cap002, 2050,  100.0,          100000.0,   0.1,                99.9,        False
        ext_stress_cap002,  2050,  100.0,          100001.0,   0.100001,           99.899999,   True
        ext_low_cap0001,    2050,  100.0,          4200000.0,  4.2,                95.8,        True
    """)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-9)


def test_unpriced_fuel_flags_a_burning_cell_charged_nothing(csv_str_to_df):
    cells = csv_str_to_df("""
        cell,              year,  diagnostic_fuel_cost_per_mwh,  share_Gas,  share_Biomass
        ext_low_c0,        2050,  25.8,                          24.8,       0.5
        ext_low_c0,        2060,  0.0,                           30.2,       0.4
        ext_low_cap00005,  2060,  0.0,                           0.0,        0.1
    """)

    result = _add_unpriced_fuel(cells)

    expected = csv_str_to_df("""
        cell,              year,  diagnostic_fuel_cost_per_mwh,  share_Gas,  share_Biomass,  fuel_unpriced
        ext_low_c0,        2050,  25.8,                          24.8,       0.5,            False
        ext_low_c0,        2060,  0.0,                           30.2,       0.4,            True
        ext_low_cap00005,  2060,  0.0,                           0.0,        0.1,            False
    """)
    pd.testing.assert_frame_equal(result, expected)


def _results_with_a_boundary(csv_str_to_df):
    """Three trajectories at one pressure and year, the middle one shedding load."""
    return csv_str_to_df("""
        cell,               pressure,  trajectory,  year,  delivered_twh,  total_cost_aud_per_yr,  co2e_total_kt_per_yr,  twh_Gas,  twh_Wind,  boundary
        ext_low_cap0001,    cap0001,   low,         2050,  300.0,          3.0e10,                 1000.0,                10.0,     200.0,     False
        ext_central_cap0001,cap0001,   central,     2050,  350.0,          3.7e10,                 1200.0,                12.0,     230.0,     True
        ext_stress_cap0001, cap0001,   stress,      2050,  450.0,          5.0e10,                 1500.0,                16.0,     300.0,     False
    """)


def test_marginals_drop_both_arcs_touching_a_boundary_cell(csv_str_to_df):
    results = _results_with_a_boundary(csv_str_to_df)

    arcs = _marginals(
        results[~results["boundary"]],
        level_order=_TRAJECTORY_ORDER,
        periods=[2050],
        series_column="pressure",
        level_column="trajectory",
    )

    # Both arcs touch the dropped middle trajectory, so no row is differenced at all
    # and the frame carries no columns to name.
    pd.testing.assert_frame_equal(arcs, pd.DataFrame())


def test_marginals_difference_adjacent_trajectories_at_one_pressure(csv_str_to_df):
    results = _results_with_a_boundary(csv_str_to_df).assign(boundary=False)

    arcs = _marginals(
        results,
        level_order=_TRAJECTORY_ORDER,
        periods=[2050],
        series_column="pressure",
        level_column="trajectory",
    )

    expected = csv_str_to_df("""
        pressure, year, from_level, to_level, from_delivered_twh, to_delivered_twh, delta_delivered_twh, from_total_cost_aud_per_yr, to_total_cost_aud_per_yr, marginal_cost_aud_per_mwh, from_co2e_kt_per_yr, to_co2e_kt_per_yr, marginal_co2e_t_per_mwh, marginal_thermal_twh, marginal_renewable_twh, marginal_thermal_per_delivered_pct, marginal_renewable_per_delivered_pct, marginal_thermal_pct_of_generation, marginal_renewable_pct_of_generation
        cap0001, 2050, low, central, 300.0, 350.0, 50.0, 3.0e10, 3.7e10, 140.0, 1000.0, 1200.0, 0.004, 2.0, 30.0, 4.0, 60.0, 6.25, 93.75
        cap0001, 2050, central, stress, 350.0, 450.0, 100.0, 3.7e10, 5.0e10, 130.0, 1200.0, 1500.0, 0.003, 4.0, 70.0, 4.0, 70.0, 5.405405405, 94.594594595
    """)
    pd.testing.assert_frame_equal(arcs, expected, check_exact=False, rtol=1e-8)


def test_cost_monotone_row_per_year_and_pressure(csv_str_to_df):
    results = csv_str_to_df("""
        cell,                pressure,  trajectory,  year,  total_cost_aud_per_yr
        ext_low_c0,          c0,        low,         2050,  3.0e10
        ext_central_c0,      c0,        central,     2050,  3.7e10
        ext_stress_c0,       c0,        stress,      2050,  5.0e10
        ext_low_cap002,      cap002,    low,         2050,  4.0e10
        ext_central_cap002,  cap002,    central,     2050,  3.5e10
        ext_stress_cap002,   cap002,    stress,      2050,  5.5e10
    """)

    rows = _cost_monotone_rows(
        results, [2050], order_pressures(["c0", "cap002"]), _TRAJECTORY_ORDER
    )

    expected = csv_str_to_df("""
        year,  pressure,  test3_cost_monotone_in_demand,  trajectories_compared
        2050,  c0,        True,                           3
        2050,  cap002,    False,                          3
    """)
    pd.testing.assert_frame_equal(pd.DataFrame(rows), expected)


def test_templated_cost_rows_melts_build_costs_and_averages_each_fuel_table(
    tmp_path, csv_str_to_df
):
    tables = {
        "new_entrant_build_costs": """
            technology,  2029_30_$/mw,  2039_40_$/mw
            Wind,        2745000.0,     2100000.0
            CCGT,        2250000.0,     2000000.0
        """,
        "coal_prices": """
            generator,  2029_30_$/gj,  2039_40_$/gj
            Bayswater,  4.0,           3.0
            Eraring,    6.0,           5.0
        """,
        "gas_prices": """
            generator,   2029_30_$/gj,  2039_40_$/gj
            Bairnsdale,  13.0,          13.5
        """,
        "biomass_prices": "2029_30_$/gj, 2039_40_$/gj\n0.6, 0.7",
        "liquid_fuel_prices": "2029_30_$/gj, 2039_40_$/gj\n29.7, 24.9",
        "hydrogen_prices": "2029_30_$/gj, 2039_40_$/gj\n37.7, 24.7",
        "biomethane_prices": "2029_30_$/gj, 2039_40_$/gj\n23.5, 21.7",
    }
    inputs = tmp_path / "ispypsa_inputs"
    inputs.mkdir()
    for stem, csv in tables.items():
        csv_str_to_df(csv).to_csv(inputs / f"{stem}.csv", index=False)

    result = _templated_cost_rows(inputs)

    expected = csv_str_to_df("""
        name,          year,  value,      category,    unit,   source_table
        Wind,          2030,  2745000.0,  build_cost,  A$/MW,  new_entrant_build_costs
        CCGT,          2030,  2250000.0,  build_cost,  A$/MW,  new_entrant_build_costs
        Wind,          2040,  2100000.0,  build_cost,  A$/MW,  new_entrant_build_costs
        CCGT,          2040,  2000000.0,  build_cost,  A$/MW,  new_entrant_build_costs
        Coal,          2030,  5.0,        fuel_price,  A$/GJ,  coal_prices
        Coal,          2040,  4.0,        fuel_price,  A$/GJ,  coal_prices
        Gas,           2030,  13.0,       fuel_price,  A$/GJ,  gas_prices
        Gas,           2040,  13.5,       fuel_price,  A$/GJ,  gas_prices
        Biomass,       2030,  0.6,        fuel_price,  A$/GJ,  biomass_prices
        Biomass,       2040,  0.7,        fuel_price,  A$/GJ,  biomass_prices
        Liquid__Fuel,  2030,  29.7,       fuel_price,  A$/GJ,  liquid_fuel_prices
        Liquid__Fuel,  2040,  24.9,       fuel_price,  A$/GJ,  liquid_fuel_prices
        Hydrogen,      2030,  37.7,       fuel_price,  A$/GJ,  hydrogen_prices
        Hydrogen,      2040,  24.7,       fuel_price,  A$/GJ,  hydrogen_prices
        Biomethane,    2030,  23.5,       fuel_price,  A$/GJ,  biomethane_prices
        Biomethane,    2040,  21.7,       fuel_price,  A$/GJ,  biomethane_prices
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_input_costs_are_skipped_when_no_templated_inputs_are_on_disk(tmp_path, caplog):
    with caplog.at_level("INFO"):
        _write_input_costs(OutputLayout(tmp_path), "ext_central_c0", [2030, 2040])

    assert (
        f"No templated inputs under {tmp_path / 'runs'} for ext_central_c0: "
        "no input_costs.csv"
    ) in caplog.text
    assert not (tmp_path / "exports").exists()
