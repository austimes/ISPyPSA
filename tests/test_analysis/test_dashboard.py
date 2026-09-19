"""Tests for the campaign dashboard's tidy frame, its figures and page rendering."""

import re
from pathlib import Path

import pandas as pd
import pytest

from analysis.dashboard.build import SECTIONS, main, tidy_frame
from analysis.dashboard.figures import (
    COST_COMPONENTS,
    HATCH_NOTE,
    figure_cap_tracking,
    figure_cost_decomposition,
    figure_cost_frontier,
    figure_cost_frontier_animated,
    figure_cost_frontier_overlaid,
    figure_cost_pathway,
    figure_demand_marginals,
    figure_implied_carbon_price,
    figure_storage_build,
    figure_tech_mix,
    html_search_grid,
    pressure_label,
)


def _write_exports(directory: Path, tables: dict[str, str], csv_str_to_df) -> Path:
    """Write one export CSV per named table into ``directory``."""
    directory.mkdir()
    for name, csv in tables.items():
        csv_str_to_df(csv).to_csv(directory / f"{name}.csv", index=False)
    return directory


@pytest.fixture
def exports(tmp_path, csv_str_to_df) -> Path:
    """Write a six-row set of export CSVs: three trajectories priced, and one cap chain."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, share_Wind
            a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 30.0,                 3000.0,                40000.0,              0.0,               25.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.5
            b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     0.50,                 35.0,                 4200.0,                60000.0,              0.2,               29.0,                          5.0,                          1.0,                            1200000000.0,             240000000.0,                      0.4
            c,    low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,                 40.0,                 3200.0,                24000.0,              0.0,               34.0,                          5.0,                          1.0,                            800000000.0,              160000000.0,                      0.6
            d,    low,        c0,       price,         0.0,            2040, 90.0,          False,    0.25,                 45.0,                 4050.0,                22500.0,              3.0,               39.0,                          5.0,                          1.0,                            900000000.0,              180000000.0,                      0.7
            e,    central,    cap0005,  cap,           0.005,          2030, 105.0,         False,    0.10,                 55.0,                 5775.0,                10500.0,              0.0,               48.0,                          4.0,                          3.0,                            1500000000.0,             210000000.0,                      0.8
            f,    central,    cap0005,  cap,           0.005,          2040, 110.0,         False,    0.05,                 65.0,                 7150.0,                5500.0,               0.0,               58.0,                          4.0,                          3.0,                            1700000000.0,             220000000.0,                      0.9
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
    return _write_exports(tmp_path / "exports", tables, csv_str_to_df)


@pytest.fixture
def two_cell_exports(tmp_path, csv_str_to_df) -> Path:
    """Write a two-cell set of export CSVs, too few for the cost surface to be interpolated."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, share_Wind
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
    return _write_exports(tmp_path / "exports", tables, csv_str_to_df)


@pytest.fixture
def grid_exports(tmp_path, csv_str_to_df) -> Path:
    """Write exports where ``c150`` is planned for ``central`` only, and absent there in 2040."""
    tables = {
        "results": """
            cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, share_Water, share_Wind
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
    return _write_exports(tmp_path / "exports", tables, csv_str_to_df)


def test_tidy_frame_joins_every_export(exports, csv_str_to_df):
    result = tidy_frame(exports)

    expected = csv_str_to_df("""
        cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_kt_per_yr, use_pct_of_demand, cost_per_mwh_excl_fuel_carbon, diagnostic_fuel_cost_per_mwh, diagnostic_carbon_cost_per_mwh, carried_capex_aud_per_yr, existing_fleet_fom_aud_per_yr, fleet_intensity, avg_cost, total_cost, share_Wind, marginal_cost, marginal_intensity, model_status, co2_cap_annual_t, implied_carbon_price_aud_per_t, test1_serves_demand, test4_termination, storage_Battery_2_2to4h, storage_Water_6_over24h, status,     pressure_name
        a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    40000.0,              0.0,               25.0,                          4.0,                          1.0,                            1000000000.0,             200000000.0,                      0.40,            30.0,     3000.0,     0.5,        60.0,          0.80,               Optimal,      ,                 0.0,                            True,                True,              1.0,                     ,                        solved,     uncapped__(A$0/t)
        b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     60000.0,              0.2,               29.0,                          5.0,                          1.0,                            1200000000.0,             240000000.0,                      0.50,            35.0,     4200.0,     0.4,        70.0,          0.90,               Optimal,      ,                 0.0,                            True,                True,              1.2,                     ,                        solved,     uncapped__(A$0/t)
        c,    low,        c0,       price,         0.0,            2030, 80.0,          False,    24000.0,              0.0,               34.0,                          5.0,                          1.0,                            800000000.0,              160000000.0,                      0.30,            40.0,     3200.0,     0.6,        50.0,          0.60,               Optimal,      ,                 0.0,                            True,                True,              0.8,                     ,                        solved,     uncapped__(A$0/t)
        d,    low,        c0,       price,         0.0,            2040, 90.0,          False,    22500.0,              3.0,               39.0,                          5.0,                          1.0,                            900000000.0,              180000000.0,                      0.25,            45.0,     4050.0,     0.7,        ,              ,                   Infeasible,   ,                 0.0,                            False,               True,              0.9,                     ,                        unaccepted, uncapped__(A$0/t)
        e,    central,    cap0005,  cap,           0.005,          2030, 105.0,         False,    10500.0,              0.0,               48.0,                          4.0,                          3.0,                            1500000000.0,             210000000.0,                      0.10,            55.0,     5775.0,     0.8,        90.0,          0.50,               Optimal,      10500.0,          120.0,                          True,                True,              2.0,                     0.5,                     solved,     cap__0.005__t__CO2e/MWh__by__2050
        f,    central,    cap0005,  cap,           0.005,          2040, 110.0,         False,    5500.0,               0.0,               58.0,                          4.0,                          3.0,                            1700000000.0,             220000000.0,                      0.05,            65.0,     7150.0,     0.9,        ,              ,                   Optimal,      5500.0,           900.0,                          True,                True,              2.4,                     0.5,                     solved,     cap__0.005__t__CO2e/MWh__by__2050
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


def test_cost_frontier_animated_plays_one_frame_per_year(exports):
    figure = figure_cost_frontier_animated(tidy_frame(exports))

    assert [panel.name for panel in figure.frames] == ["2030", "2040"]
    assert [trace.mode for trace in figure.data] == ["markers"] * 3 + ["lines"] * 3


def test_cost_frontier_overlaid_draws_every_year_in_one_panel(exports):
    figure = figure_cost_frontier_overlaid(tidy_frame(exports))

    assert [trace.name for trace in figure.data if trace.mode == "markers"] == [
        "2030, low",
        "2030, central",
        "2030, high",
        "2040, low",
        "2040, central",
    ]


def test_cost_pathway_draws_one_line_per_pressure_and_trajectory(exports):
    figure = figure_cost_pathway(tidy_frame(exports))

    assert [(trace.name, trace.xaxis) for trace in figure.data] == [
        ("uncapped (A$0/t)", "x"),
        ("uncapped (A$0/t)", "x2"),
        ("uncapped (A$0/t)", "x3"),
        ("cap 0.005 t CO2e/MWh by 2050", "x2"),
    ]


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


def test_cap_tracking_draws_a_cap_line_for_the_cap_chain_only(exports):
    figure = figure_cap_tracking(tidy_frame(exports))

    dashed = [trace.name for trace in figure.data if trace.line.dash == "dash"]
    assert dashed == ["cap 0.005 t CO2e/MWh by 2050, cap"]


def test_storage_build_lists_each_duration_once_across_both_carriers(exports):
    figure = figure_storage_build(tidy_frame(exports))

    assert [trace.name for trace in figure.data if trace.showlegend] == [
        "2 to 4 h",
        "over 24 h",
    ]


def test_search_grid_heads_each_column_with_its_spelled_out_name(grid_exports):
    html = html_search_grid(tidy_frame(grid_exports))

    headings = re.findall(r"<th>(.*?)</th>", html)
    assert headings == [
        "Trajectory",
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
    }


def test_tech_mix_lists_each_carrier_in_the_legend_once(grid_exports):
    figure = figure_tech_mix(tidy_frame(grid_exports))

    listed = [trace.name for trace in figure.data if trace.showlegend]
    assert listed == ["Hydro (conventional)", "Wind"]


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
    assert text.count('<div class="divider"') == len(SECTIONS)
    assert text.count('querySelectorAll(".divider")') == 1


def test_main_renders_a_run_too_small_to_interpolate(two_cell_exports):
    page = main(two_cell_exports.parent)

    text = page.read_text(encoding="utf-8")
    assert "<h2>Cost surface over demand and marginal intensity</h2>" not in text
    assert "<h2>Technology mix</h2>" in text
