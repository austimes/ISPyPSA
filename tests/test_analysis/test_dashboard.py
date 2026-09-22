"""Tests for the campaign dashboard's tidy frame, its figures and page rendering."""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from plotly.subplots import make_subplots

from analysis.dashboard import figures
from analysis.dashboard.build import (
    ASSUMPTIONS_HEADING,
    SECTIONS,
    main,
    tidy_frame,
)
from analysis.dashboard.figures import (
    CARRIER_COLOURS,
    COST_COMPONENTS,
    GRID_SIZE,
    HATCH_NOTE,
    INPUT_COST_LABELS,
    add_axis_match_buttons,
    figure_cost_decomposition,
    figure_cost_frontier,
    figure_cost_heatmap,
    figure_cost_pathway,
    figure_demand_marginals,
    figure_implied_carbon_price,
    figure_input_costs,
    figure_pathway_intensities,
    figure_storage_build,
    figure_tech_mix,
    html_search_grid,
    pressure_label,
)


def _write_campaign(run: Path, name: str, text: str) -> None:
    """Write one launch record into a run's ``campaign/`` directory."""
    (run / "campaign").mkdir(parents=True)
    (run / "campaign" / name).write_text(text, encoding="utf-8")


def _write_exports(directory: Path, tables: dict[str, str], csv_str_to_df) -> Path:
    """Write one export CSV per named table into ``directory``."""
    directory.mkdir(parents=True)
    for name, csv in tables.items():
        csv_str_to_df(csv).to_csv(directory / f"{name}.csv", index=False)
    return directory


@pytest.fixture
def exports(tmp_path, csv_str_to_df) -> Path:
    """Write a six-row set of export CSVs: three trajectories priced, and one cap chain."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, social_licence_premium_aud_per_yr, build_rate_premium_aud_per_yr, twh_Wind
            a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 30.0,                 3000.0,                40000.0,              0.0,               25.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                   12000000.0,                        3000000.0,                     0.5
            b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     0.50,                 35.0,                 4200.0,                60000.0,              0.2,               29.0,                          5.0,                          1.0,                            1200000000.0,             240000000.0,                   14000000.0,                        3500000.0,                     0.4
            c,    low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,                 40.0,                 3200.0,                24000.0,              0.0,               34.0,                          5.0,                          1.0,                            800000000.0,              160000000.0,                   9000000.0,                         2000000.0,                     0.6
            d,    low,        c0,       price,         0.0,            2040, 90.0,          False,    0.25,                 45.0,                 4050.0,                22500.0,              3.0,               39.0,                          5.0,                          1.0,                            900000000.0,              180000000.0,                   10000000.0,                        2500000.0,                     0.7
            e,    central,    cap0005,  cap,           0.005,          2030, 105.0,         False,    0.10,                 55.0,                 5775.0,                10500.0,              0.0,               48.0,                          4.0,                          3.0,                            1500000000.0,             210000000.0,                   20000000.0,                        6000000.0,                     0.8
            f,    central,    cap0005,  cap,           0.005,          2040, 110.0,         False,    0.05,                 65.0,                 7150.0,                5500.0,               0.0,               58.0,                          4.0,                          3.0,                            1700000000.0,             220000000.0,                   24000000.0,                        7000000.0,                     0.9
        """,
        "marginals": """
            pressure, year, from_level,  to_level, marginal_cost_aud_per_mwh, marginal_co2e_t_per_mwh
            c0,       2030, low_bracket, low,      50.0,                      0.60
            c0,       2030, low,         central,  60.0,                      0.80
            c0,       2030, central,     high,     70.0,                      0.90
            cap0005,  2030, low,         central,  90.0,                      0.50
        """,
        "manifest": """
            cell, year, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t
            a,    2030, Optimal,      ,                 0.0
            b,    2030, Optimal,      ,                 0.0
            c,    2030, Optimal,      ,                 0.0
            d,    2040, Infeasible,   ,                 0.0
            e,    2030, Optimal,      10500.0,          120.0
            f,    2040, Optimal,      5500.0,           900.0
        """,
        "acceptance_per_cell": """
            cell, year, test1_serves_demand, test4_termination
            a,    2030, True,                True
            b,    2030, True,                True
            c,    2030, True,                True
            d,    2040, False,               True
            e,    2030, True,                True
            f,    2040, True,                True
        """,
        "storage": """
            cell, year, carrier, duration_class, power_gw
            a,    2030, Battery, 2_2to4h,        1.0
            b,    2030, Battery, 2_2to4h,        1.2
            c,    2030, Battery, 2_2to4h,        0.8
            d,    2040, Battery, 2_2to4h,        0.9
            e,    2030, Battery, 2_2to4h,        2.0
            e,    2030, Water,   6_over24h,      0.5
            f,    2040, Battery, 2_2to4h,        2.4
            f,    2040, Water,   6_over24h,      0.5
        """,
    }
    return _write_exports(tmp_path / "run_a" / "exports", tables, csv_str_to_df)


@pytest.fixture
def two_cell_exports(tmp_path, csv_str_to_df) -> Path:
    """Write a two-cell set of export CSVs, too few for the cost surface to be interpolated."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, twh_Wind
            a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 30.0,                 3000.0,                40000.0,              0.0,               25.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.5
            b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     0.50,                 35.0,                 4200.0,                60000.0,              0.0,               29.0,                          5.0,                          1.0,                            1200000000.0,             240000000.0,                      0.4
        """,
        "marginals": """
            pressure, year, from_level, to_level, marginal_cost_aud_per_mwh, marginal_co2e_t_per_mwh
            c0,       2030, central,    high,     70.0,                      0.90
        """,
        "manifest": """
            cell, year, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t
            a,    2030, Optimal,      ,                 0.0
            b,    2030, Optimal,      ,                 0.0
        """,
        "acceptance_per_cell": """
            cell, year, test1_serves_demand, test4_termination
            a,    2030, True,                True
            b,    2030, True,                True
        """,
        "storage": """
            cell, year, carrier, duration_class, power_gw
            a,    2030, Battery, 2_2to4h,        1.0
            b,    2030, Battery, 2_2to4h,        1.2
        """,
    }
    return _write_exports(tmp_path / "run_b" / "exports", tables, csv_str_to_df)


@pytest.fixture
def collinear_exports(tmp_path, csv_str_to_df) -> Path:
    """Write four accepted cells that share one marginal intensity, so their points lie on a line."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, twh_Wind
            a,    low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,                 25.0,                 2000.0,                24000.0,              0.0,               20.0,                          4.0,                          1.0,                            800000000.0,              160000000.0,                      0.5
            b,    central,    c0,       price,         0.0,            2030, 90.0,          False,    0.35,                 30.0,                 2700.0,                31500.0,              0.0,               25.0,                          4.0,                          1.0,                            900000000.0,              180000000.0,                      0.5
            c,    high,       c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 35.0,                 3500.0,                40000.0,              0.0,               30.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.5
            d,    very_high,  c0,       price,         0.0,            2030, 110.0,         False,    0.45,                 40.0,                 4400.0,                49500.0,              0.0,               35.0,                          4.0,                          1.0,                            1100000000.0,             220000000.0,                      0.5
        """,
        "marginals": """
            pressure, year, from_level,  to_level,   marginal_cost_aud_per_mwh, marginal_co2e_t_per_mwh
            c0,       2030, low_bracket, low,        50.0,                      0.50
            c0,       2030, low,         central,    60.0,                      0.50
            c0,       2030, central,     high,       70.0,                      0.50
            c0,       2030, high,        very_high,  80.0,                      0.50
        """,
        "manifest": """
            cell, year, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t
            a,    2030, Optimal,      ,                 0.0
            b,    2030, Optimal,      ,                 0.0
            c,    2030, Optimal,      ,                 0.0
            d,    2030, Optimal,      ,                 0.0
        """,
        "acceptance_per_cell": """
            cell, year, test1_serves_demand, test4_termination
            a,    2030, True,                True
            b,    2030, True,                True
            c,    2030, True,                True
            d,    2030, True,                True
        """,
        "storage": """
            cell, year, carrier, duration_class, power_gw
            a,    2030, Battery, 2_2to4h,        0.8
            b,    2030, Battery, 2_2to4h,        0.9
            c,    2030, Battery, 2_2to4h,        1.0
            d,    2030, Battery, 2_2to4h,        1.1
        """,
    }
    return _write_exports(tmp_path / "run_line" / "exports", tables, csv_str_to_df)


@pytest.fixture
def grid_exports(tmp_path, csv_str_to_df) -> Path:
    """Write exports where ``c150`` is planned for ``central`` only, and absent there in 2040."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, twh_Water, twh_Wind
            a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 30.06,                3006.0,                40000.0,              0.0,               25.06,                         4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.2,         0.8
            b,    central,    c0,       price,         0.0,            2040, 110.0,         False,    0.35,                 40.0,                 4400.0,                38500.0,              0.0,               35.0,                          4.0,                          1.0,                            1100000000.0,             220000000.0,                      0.3,         0.7
            c,    central,    c150,     price,         150.0,          2030, 100.0,         True,     0.20,                 55.0,                 5500.0,                20000.0,              0.0,               48.0,                          4.0,                          3.0,                            1500000000.0,             210000000.0,                      0.4,         0.6
            d,    low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,                 25.0,                 2000.0,                24000.0,              0.0,               20.0,                          4.0,                          1.0,                            800000000.0,              160000000.0,                      0.5,         0.5
            e,    low,        c0,       price,         0.0,            2040, 90.0,          False,    0.25,                 35.0,                 3150.0,                22500.0,              0.0,               30.0,                          4.0,                          1.0,                            900000000.0,              180000000.0,                      0.6,         0.4
        """,
        "marginals": """
            pressure, year, from_level, to_level, marginal_cost_aud_per_mwh, marginal_co2e_t_per_mwh
            c0,       2030, low,        central,  60.0,                      0.80
        """,
        "manifest": """
            cell, year, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t
            a,    2030, Optimal,      ,                 0.0
            b,    2040, Optimal,      ,                 0.0
            c,    2030, Optimal,      ,                 150.0
            d,    2030, Optimal,      ,                 0.0
            e,    2040, Optimal,      ,                 0.0
        """,
        "acceptance_per_cell": """
            cell, year, test1_serves_demand, test4_termination
            a,    2030, True,                True
            b,    2040, True,                True
            c,    2030, True,                True
            d,    2030, False,               True
            e,    2040, True,                True
        """,
        "storage": """
            cell, year, carrier, duration_class, power_gw
            a,    2030, Battery, 2_2to4h,        1.0
            b,    2040, Battery, 2_2to4h,        1.1
            c,    2030, Water,   6_over24h,      0.5
            d,    2030, Battery, 2_2to4h,        0.8
            e,    2040, Battery, 2_2to4h,        0.9
        """,
    }
    return _write_exports(tmp_path / "run_grid" / "exports", tables, csv_str_to_df)


def test_tidy_frame_joins_every_export(exports, csv_str_to_df):
    result = tidy_frame(exports)

    expected = csv_str_to_df("""
        cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, fleet_intensity, avg_cost, total_cost, twh_Wind, social_licence_premium_aud_per_yr, build_rate_premium_aud_per_yr, marginal_cost, marginal_intensity, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t, test1_serves_demand, test4_termination, storage_Battery_2_2to4h, storage_Water_6_over24h, status,     pressure_name
        a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    40000.0,              0.0,               25.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.40,            30.0,     3000.0,     0.5, 12000000.0, 3000000.0,        60.0,          0.80,               Optimal,      ,                 0.0,                            True,                True,              1.0,                     ,                        solved,     uncapped__(A$0/t)
        b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     60000.0,              0.2,               29.0,                          5.0,                          1.0,                            1200000000.0,             240000000.0,                      0.50,            35.0,     4200.0,     0.4, 14000000.0, 3500000.0,        70.0,          0.90,               Optimal,      ,                 0.0,                            True,                True,              1.2,                     ,                        solved,     uncapped__(A$0/t)
        c,    low,        c0,       price,         0.0,            2030, 80.0,          False,    24000.0,              0.0,               34.0,                          5.0,                          1.0,                            800000000.0,              160000000.0,                      0.30,            40.0,     3200.0,     0.6, 9000000.0, 2000000.0,        50.0,          0.60,               Optimal,      ,                 0.0,                            True,                True,              0.8,                     ,                        solved,     uncapped__(A$0/t)
        d,    low,        c0,       price,         0.0,            2040, 90.0,          False,    22500.0,              3.0,               39.0,                          5.0,                          1.0,                            900000000.0,              180000000.0,                      0.25,            45.0,     4050.0,     0.7, 10000000.0, 2500000.0,        ,              ,                   Infeasible,   ,                 0.0,                            False,               True,              0.9,                     ,                        unaccepted, uncapped__(A$0/t)
        e,    central,    cap0005,  cap,           0.005,          2030, 105.0,         False,    10500.0,              0.0,               48.0,                          4.0,                          3.0,                            1500000000.0,             210000000.0,                      0.10,            55.0,     5775.0,     0.8, 20000000.0, 6000000.0,        90.0,          0.50,               Optimal,      10500.0,          120.0,                          True,                True,              2.0,                     0.5,                     solved,     cap__0.005__t__CO2e/MWh__by__2050
        f,    central,    cap0005,  cap,           0.005,          2040, 110.0,         False,    5500.0,               0.0,               58.0,                          4.0,                          3.0,                            1700000000.0,             220000000.0,                      0.05,            65.0,     7150.0,     0.9, 24000000.0, 7000000.0,        ,              ,                   Optimal,      5500.0,           900.0,                          True,                True,              2.4,                     0.5,                     solved,     cap__0.005__t__CO2e/MWh__by__2050
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_tidy_frame_logs_cell_years_with_no_marginal(exports, caplog):
    with caplog.at_level("INFO"):
        tidy_frame(exports)

    assert (
        "Cell-years with no matching marginal: 2, in trajectories ['central', 'low']"
    ) in caplog.text


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("c0", "uncapped (A$0/t)"),
        ("c150", "carbon price A$150/t"),
        ("cap0005", "cap 0.005 t CO2e/MWh by 2050"),
    ],
)
def test_pressure_label_spells_out_each_family(key, expected):
    assert pressure_label(key) == expected


def test_pressure_label_wraps_on_the_given_separator():
    assert pressure_label("cap0005", "<br>") == "cap<br>0.005<br>t CO2e/MWh<br>by 2050"


def test_cost_frontier_draws_a_ladder_line_beside_each_trajectory(exports):
    figure = figure_cost_frontier(tidy_frame(exports))

    # One marker trace per trajectory and year, and a ladder line beside each of them.
    modes = [trace.mode for trace in figure.data]
    assert modes == ["markers"] * 5 + ["lines"] * 5


def test_cost_frontier_buttons_retype_every_faceted_x_axis(exports):
    figure = figure_cost_frontier(tidy_frame(exports))

    linear, log = figure.layout.updatemenus[0].buttons
    assert [linear.label, log.label] == ["Linear", "Log"]
    assert log.args[0] == {"xaxis.type": "log", "xaxis2.type": "log"}


def test_cost_heatmap_blanks_the_cells_the_interpolation_could_not_reach(exports):
    figure = figure_cost_heatmap(tidy_frame(exports))

    # Only 2030 holds enough solved cells to interpolate, so the figure is a single panel.
    (cells,) = figure.data
    assert (cells.type, cells.z.shape, cells.coloraxis) == (
        "heatmap",
        (GRID_SIZE, GRID_SIZE),
        "coloraxis",
    )
    # Grid points outside the solved cells' hull stay NaN, which plotly draws as a gap.
    assert np.isnan(cells.z).any()
    assert figure.layout.coloraxis.colorbar.title.text == "Average cost (A$/MWh)"
    assert figure.layout.yaxis.title.text == "Demand-marginal intensity (t CO2e/MWh)"


def test_cost_heatmap_offers_to_share_its_panels_axes(exports):
    figure = figure_cost_heatmap(tidy_frame(exports))

    assert [button.label for button in figure.layout.updatemenus[0].buttons] == [
        "Shared axes",
        "Independent axes",
    ]


def test_axis_match_buttons_tie_every_panel_to_the_first():
    figure = add_axis_match_buttons(make_subplots(rows=1, cols=3))

    shared, independent = figure.layout.updatemenus[0].buttons
    assert shared.args[0] == {
        "xaxis2.matches": "x",
        "xaxis3.matches": "x",
        "yaxis2.matches": "y",
        "yaxis3.matches": "y",
    }
    assert independent.args[0] == {
        "xaxis2.matches": None,
        "xaxis3.matches": None,
        "yaxis2.matches": None,
        "yaxis3.matches": None,
    }


def test_cost_heatmap_is_dropped_when_no_year_holds_enough_cells(two_cell_exports):
    assert figure_cost_heatmap(tidy_frame(two_cell_exports)) is None


def test_cost_heatmap_skips_a_year_whose_cells_lie_on_a_line(collinear_exports, caplog):
    with caplog.at_level("WARNING"):
        figure = figure_cost_heatmap(tidy_frame(collinear_exports))

    assert figure is None
    assert (
        "No cost surface for 2030: its accepted cells cannot be triangulated"
    ) in caplog.text


def test_cost_heatmap_logs_nothing_when_every_year_interpolates(exports, caplog):
    with caplog.at_level("WARNING"):
        figure_cost_heatmap(tidy_frame(exports))

    assert "No cost surface" not in caplog.text


def test_cost_pathway_draws_one_line_per_pressure_and_trajectory(exports):
    figure = figure_cost_pathway(tidy_frame(exports))

    assert [(trace.name, trace.xaxis) for trace in figure.data] == [
        ("uncapped (A$0/t)", "x"),
        ("uncapped (A$0/t)", "x2"),
        ("uncapped (A$0/t)", "x3"),
        ("cap 0.005 t CO2e/MWh by 2050", "x2"),
    ]


def test_pathway_intensities_draws_one_line_per_chain_and_burnt_fuel(csv_str_to_df):
    frame = csv_str_to_df("""
        cell,    trajectory, pressure, pressure_name,        year, delivered_twh, cost_per_mwh_excl_fuel_carbon, fleet_intensity, gj_per_mwh_coal, gj_per_mwh_natural_gas, gj_per_mwh_biomass
        central, central,    c0,       uncapped (A$0/t),     2030, 100.0,         25.0,                          0.40,            1.1,             0.3,                    0.0
        central, central,    c0,       uncapped (A$0/t),     2040, 110.0,         30.0,                          0.20,            0.9,             0.4,                    0.0
        high,    high,       c150,     carbon price A$150/t, 2030, 120.0,         35.0,                          0.30,            0.0,             0.5,                    0.1
        high,    high,       c150,     carbon price A$150/t, 2040, 130.0,         40.0,                          0.10,            0.0,             0.6,                    0.2
    """)

    figure = figure_pathway_intensities(frame)

    # The AEMO reference overlay, then cost and emissions for both chains, then the fuels each chain
    # burns: coal and gas, gas and biomass.
    assert [(trace.name, trace.line.dash) for trace in figure.data] == [
        (None, None),
        ("AEMO scenario range", None),
        ("AEMO draft ISP: Slower Growth", "dot"),
        ("AEMO draft ISP: Step Change", "dot"),
        ("AEMO draft ISP: Accelerated Transition", "dot"),
        ("central demand, uncapped (A$0/t)", "solid"),
        ("central demand, uncapped (A$0/t)", "solid"),
        ("central demand, uncapped (A$0/t)", "solid"),
        ("central demand, uncapped (A$0/t)", "dash"),
        ("high demand, carbon price A$150/t", "solid"),
        ("high demand, carbon price A$150/t", "solid"),
        ("high demand, carbon price A$150/t", "dash"),
        ("high demand, carbon price A$150/t", "dot"),
    ]
    assert [trace.name for trace in figure.data if trace.showlegend] == [
        "AEMO scenario range",
        "AEMO draft ISP: Slower Growth",
        "AEMO draft ISP: Step Change",
        "AEMO draft ISP: Accelerated Transition",
        "central demand, uncapped (A$0/t)",
        "high demand, carbon price A$150/t",
    ]


def test_pathway_intensities_overlays_the_aemo_scenarios_on_the_emissions_panel(
    csv_str_to_df,
):
    frame = csv_str_to_df("""
        cell,    trajectory, pressure, pressure_name,    year, delivered_twh, cost_per_mwh_excl_fuel_carbon, fleet_intensity
        central, central,    c0,       uncapped (A$0/t), 2030, 100.0,         25.0,                          0.40
        central, central,    c0,       uncapped (A$0/t), 2040, 110.0,         30.0,                          0.20
    """)

    figure = figure_pathway_intensities(frame)

    overlay = [trace for trace in figure.data if trace.legendgroup == "AEMO draft ISP"]
    assert [trace.name for trace in overlay] == [
        None,
        "AEMO scenario range",
        "AEMO draft ISP: Slower Growth",
        "AEMO draft ISP: Step Change",
        "AEMO draft ISP: Accelerated Transition",
    ]
    assert {trace.yaxis for trace in overlay} == {"y2"}
    assert min(overlay[2].x) == 2030


def test_implied_carbon_price_leaves_out_the_price_chains(exports):
    figure = figure_implied_carbon_price(tidy_frame(exports))

    assert [list(trace.y) for trace in figure.data] == [[120.0], [900.0]]


def test_demand_marginals_faces_each_step_with_both_measures(exports):
    figure = figure_demand_marginals(tidy_frame(exports))

    assert {note.text for note in figure.layout.annotations} == {
        "up to low",
        "up to central",
        "up to high",
        "Demand-marginal cost (A$/MWh)",
        "Demand-marginal intensity (t CO2e/MWh)",
    }


def test_cost_decomposition_stacks_every_component_of_the_central_trajectory(exports):
    figure = figure_cost_decomposition(tidy_frame(exports))

    assert {trace.name for trace in figure.data} == set(COST_COMPONENTS)
    carried = next(trace for trace in figure.data if trace.name == "carried capex")
    assert list(carried.y) == pytest.approx([10.0, 14.2857142857])


def test_storage_build_lists_each_duration_once_across_both_carriers(exports):
    figure = figure_storage_build(tidy_frame(exports))

    assert [trace.name for trace in figure.data if trace.showlegend] == [
        "2 to 4 h",
        "over 24 h",
    ]


@pytest.fixture
def input_costs(csv_str_to_df) -> pd.DataFrame:
    """Two technologies, two fuels and one tranche adder, over two years."""
    return csv_str_to_df("""
        category,    name,                 year,  value,      unit,          source_table
        build_cost,  Wind,                 2030,  2745000.0,  A$/MW,         new_entrant_build_costs
        build_cost,  Wind,                 2040,  2100000.0,  A$/MW,         new_entrant_build_costs
        build_cost,  CCGT,                 2030,  2250000.0,  A$/MW,         new_entrant_build_costs
        build_cost,  CCGT,                 2040,  2000000.0,  A$/MW,         new_entrant_build_costs
        fuel_price,  Gas,                  2030,  13.0,       A$/GJ,         gas_prices
        fuel_price,  Gas,                  2040,  13.5,       A$/GJ,         gas_prices
        fuel_price,  Biomass,              2030,  0.6,        A$/GJ,         biomass_prices
        fuel_price,  Biomass,              2040,  0.7,        A$/GJ,         biomass_prices
        fuel_adder,  gas__lng__imports,    2030,  6.0,        A$/GJ__adder,  gas_supply_curve.csv
        fuel_adder,  gas__lng__imports,    2040,  6.0,        A$/GJ__adder,  gas_supply_curve.csv
    """)


def test_input_costs_draws_one_panel_per_category_with_build_cost_on_a_log_axis(
    input_costs,
):
    figure = figure_input_costs(input_costs)

    assert [note.text for note in figure.layout.annotations] == list(
        INPUT_COST_LABELS.values()
    )
    assert (figure.layout.yaxis.type, figure.layout.yaxis2.type) == ("log", None)
    # Gas and biomass are generation carriers, so they keep the colours the mix figures give them.
    coloured = {trace.name: trace.line.color for trace in figure.data}
    assert coloured["Gas"] == CARRIER_COLOURS["Gas"]
    assert coloured["Biomass"] == CARRIER_COLOURS["Biomass"]


def test_search_grid_heads_each_column_with_its_spelled_out_name(grid_exports):
    html = html_search_grid(tidy_frame(grid_exports))

    headings = re.findall(r"<th>(.*?)</th>", html)
    assert headings == [
        "Demand trajectory",
        "Year",
        "Delivered energy (TWh)",
        "uncapped (A$0/t)",
        "carbon price A$150/t",
    ]


def test_search_grid_classes_each_cell_by_its_solve_status(grid_exports):
    html = html_search_grid(tidy_frame(grid_exports))

    assert '<span class="solved">30.1</span>' in html
    assert '<span class="solved">55.0 (boundary)</span>' in html
    assert '<span class="unaccepted">25.0</span>' in html
    assert '<span class="missing"></span>' in html
    assert '<span class="unplanned"></span>' in html


def test_tech_mix_hatches_unaccepted_cells_and_renames_water(grid_exports):
    figure = figure_tech_mix(tidy_frame(grid_exports))

    assert {(trace.name, trace.marker.pattern.shape) for trace in figure.data} == {
        ("Hydro (conventional)", ""),
        ("Hydro (conventional)", "/"),
        ("Wind", ""),
        ("Wind", "/"),
        ("Unserved", ""),
        ("Unserved", "/"),
    }


def test_tech_mix_dots_storage_discharge_on_top_of_the_generation_carriers(exports):
    frame = tidy_frame(exports).assign(twh_Battery=3.0, **{"twh_Pumped hydro": 1.0})

    figure = figure_tech_mix(frame)

    # The ``high`` trajectory's one cell, bottom of the stack to the top.
    stack = [
        (trace.name, trace.marker.pattern.shape)
        for trace in figure.data
        if trace.xaxis == "x"
    ]
    assert stack == [
        ("Wind", ""),
        ("Battery", "."),
        ("Pumped hydro", "."),
        ("Unserved", ""),
    ]


def test_tech_mix_lists_each_carrier_in_the_legend_once_then_unserved(grid_exports):
    figure = figure_tech_mix(tidy_frame(grid_exports))

    listed = [trace.name for trace in figure.data if trace.showlegend]
    assert listed == ["Hydro (conventional)", "Wind", "Unserved"]


def test_tech_mix_stacks_energy_delivered_in_twh(exports):
    figure = figure_tech_mix(tidy_frame(exports))

    # The ``high`` trajectory's one cell: 0.4 TWh of wind, and 0.2% of its 120 TWh demand unserved.
    high = [(trace.name, list(trace.y)) for trace in figure.data if trace.xaxis == "x"]
    assert high == [("Wind", [0.4]), ("Unserved", [120.0 * 0.2 / 100])]
    assert figure.layout.yaxis.title.text == "Energy delivered (TWh)"


def test_tech_mix_labels_facets_with_the_manifest_pressure_names(grid_exports):
    figure = figure_tech_mix(tidy_frame(grid_exports))

    assert {note.text for note in figure.layout.annotations} == {
        "uncapped<br>(A$0/t)",
        "carbon price<br>A$150/t",
        "central",
        "low",
        HATCH_NOTE,
    }


def test_main_writes_one_html_page(exports):
    page = main(exports.parent)

    text = page.read_text(encoding="utf-8")
    assert page == exports.parent / "dashboard.html"
    assert "<h2>Cost frontier</h2>" in text
    assert "<h2>Storage build</h2>" in text
    # Every section's box, plus the assumptions table that sits under the technology mix.
    assert text.count('<div class="divider"') == len(SECTIONS) + 1
    assert text.count('querySelectorAll(".divider")') == 1


def test_main_leaves_every_figure_to_fill_its_own_box(exports):
    page = main(exports.parent)

    # Everything past plotly's bundle: the figures, the boxes holding them and the page script.
    text = page.read_text(encoding="utf-8").partition("</script>")[2]
    assert '"height":' not in text
    assert (
        text.count('<div class="box" style="overflow: auto; height:')
        == len(SECTIONS) + 1
    )
    assert text.count('"Fullscreen"') == 1


def test_main_renders_a_run_too_small_to_interpolate(two_cell_exports):
    page = main(two_cell_exports.parent)

    text = page.read_text(encoding="utf-8")
    assert "<h2>Cost surface as heatmap</h2>" not in text
    assert "<h2>Technology mix</h2>" in text


def _assumptions_table(page: Path) -> list[str]:
    """Every heading and cell of the page's assumptions table, in reading order."""
    text = page.read_text(encoding="utf-8")
    table = text.partition(f"<h2>{ASSUMPTIONS_HEADING}</h2>")[2].partition("</table>")[
        0
    ]
    return re.findall(r"<t[hd]>(.*?)</t[hd]>", table)


def test_main_lists_what_the_run_was_launched_under(exports):
    _write_campaign(
        exports.parent,
        "assumptions.json",
        '{"rez_limit_factor": 1.5, "max_cap": 20, "chains": 4}',
    )

    page = main(exports.parent)

    assert _assumptions_table(page) == [
        "assumption",
        "value",
        "rez_limit_factor",
        "1.5",
        "max_cap",
        "20.0",
        "chains",
        "4.0",
    ]


def test_main_names_the_input_package_a_run_recorded_no_assumptions_for(
    two_cell_exports,
):
    _write_campaign(two_cell_exports.parent, "inputs.txt", "2026-01-01T00.00_final\n")

    page = main(two_cell_exports.parent)

    assert _assumptions_table(page) == [
        "assumption",
        "value",
        "inputs",
        "2026-01-01T00.00_final",
    ]


def test_transmission_limits_draw_the_deepest_central_cap_against_both_ceilings(
    csv_str_to_df,
):
    links = csv_str_to_df("""
        cell,                 year,  link,   kind,       p_nom_mw,  p_nom_opt_mw,  expansion_limit_mw,  transmission_limit_mw
        ext_central_cap002,   2050,  Q1-NQ,  rez,        3000.0,    3000.0,        5160.0,              3000.0
        ext_central_cap0005,  2050,  Q1-NQ,  rez,        3000.0,    3500.0,        5160.0,              3000.0
        ext_central_cap0005,  2050,  Q3-NQ,  rez,        100000.0,  100000.0,      ,
        ext_central_cap0005,  2050,  CQ-NQ,  flow_path,  1200.0,    2000.0,        6000.0,
    """)

    figure = figures.figure_transmission_limits(links, 4.0, 4.0)

    # The shallower cap and the REZ connection with no published limit are both left out, and a
    # flow path's own corridor capacity is AEMO's, so only its expansion headroom divides by four.
    # The premium step is one more helping of published headroom above AEMO's limit.
    assert "ext_central_cap0005" in figure.layout.title.text
    assert [(list(bar.x), list(bar.y)) for bar in figure.data if bar.type == "bar"] == [
        (["Q1-NQ"], [3500.0]),
        (["CQ-NQ"], [2000.0]),
    ]
    assert [
        (dash.name, list(dash.y)) for dash in figure.data if dash.type == "scatter"
    ] == [
        ("AEMO IASR limit", [2040.0]),
        ("2x AEMO limit (premium step)", [3330.0]),
        ("Relaxed limit", [8160.0]),
        ("AEMO IASR limit", [2700.0]),
        ("2x AEMO limit (premium step)", [4200.0]),
        ("Relaxed limit", [7200.0]),
    ]
