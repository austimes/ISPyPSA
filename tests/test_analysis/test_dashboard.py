"""Tests for the campaign dashboard's tidy frame and page rendering."""

from pathlib import Path

import pandas as pd
import pytest

from analysis.dashboard.build import main, tidy_frame


@pytest.fixture
def exports(tmp_path, csv_str_to_df) -> Path:
    """Write a four-row set of export CSVs, one cell-year per row."""
    directory = tmp_path / "exports"
    directory.mkdir()
    tables = {
        "results": """
            cell,   trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, co2e_total_t_per_mwh, avg_cost_aud_per_mwh, total_cost_aud_per_yr, share_Wind
            a,      central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,                 30.0,                 3000.0,                0.5
            b,      high,       c0,       price,         0.0,            2030, 120.0,         True,     0.50,                 35.0,                 4200.0,                0.4
            c,      low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,                 40.0,                 3200.0,                0.6
            d,      low,        c0,       price,         0.0,            2040, 90.0,          False,    0.25,                 45.0,                 4050.0,                0.7
        """,
        "marginals": """
            pressure, year, from_level,  to_level, marginal_co2e_t_per_mwh
            c0,       2030, low_bracket, low,      0.60
            c0,       2030, low,         central,  0.80
            c0,       2030, central,     high,     0.90
        """,
        "manifest": """
            cell, year, model_status, carbon_price, co2_cap_annual_t
            a,    2030, Optimal,      0.0,
            b,    2030, Optimal,      0.0,
            c,    2030, Optimal,      0.0,
            d,    2040, Infeasible,   0.0,
        """,
        "acceptance_per_cell": """
            cell, year, test1_serves_demand, test4_termination
            a,    2030, True,                True
            b,    2030, True,                True
            c,    2030, True,                True
            d,    2040, False,               True
        """,
    }
    for name, csv in tables.items():
        csv_str_to_df(csv).to_csv(directory / f"{name}.csv", index=False)
    return directory


def test_tidy_frame_joins_marginals_and_status(exports, csv_str_to_df):
    result = tidy_frame(exports)

    expected = csv_str_to_df("""
        cell, trajectory, pressure, pressure_kind, pressure_value, year, delivered_twh, boundary, fleet_intensity, avg_cost, total_cost, share_Wind, marginal_intensity, model_status, test1_serves_demand, test4_termination, status
        a,    central,    c0,       price,         0.0,            2030, 100.0,         False,    0.40,            30.0,     3000.0,     0.5,        0.80,               Optimal,      True,                True,              Optimal
        b,    high,       c0,       price,         0.0,            2030, 120.0,         True,     0.50,            35.0,     4200.0,     0.4,        0.90,               Optimal,      True,                True,              boundary
        c,    low,        c0,       price,         0.0,            2030, 80.0,          False,    0.30,            40.0,     3200.0,     0.6,        0.60,               Optimal,      True,                True,              Optimal
        d,    low,        c0,       price,         0.0,            2040, 90.0,          False,    0.25,            45.0,     4050.0,     0.7,        ,                   Infeasible,   False,               True,              missing
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_main_writes_one_html_page(exports):
    page = main(exports.parent)

    assert page == exports.parent / "dashboard.html"
    assert "<h2>Technology mix</h2>" in page.read_text(encoding="utf-8")
