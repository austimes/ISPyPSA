"""Tests for the PHES menu repair pre-pass (analysis/model/phes_menu.py)
and its translator/recursive-dynamic plumbing.

Each test follows the strict ordering: inputs → function call → expected → assertion.
"""

import logging
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from analysis.model.phes_menu import _append_extrapolated_build_costs
from analysis.model.phes_menu import apply as phes_menu_apply
from analysis.model.recursive_dynamic import (
    adjust_phes_build_limits_for_carried,
)
from ispypsa.translator.create_pypsa_friendly import (
    _fill_missing_build_limits_with_inf,
)
from ispypsa.translator.storage import _translate_new_entrant_batteries


def _write_mini_phes_cache(cache_dir):
    """A minimal workbook cache carrying the six tables the pre-pass reads.

    Two sub-regions (NNSW, SNW); SNW has a zero 24h limit so the
    zero-limit-skip path is exercised. Values mirror the v7.8 workbook."""
    limit_prefix = "Pumped Hydro Energy Storage (PHES) limits (MW)_"
    pd.DataFrame(
        {
            "Power Station / Technology": [
                "BOTN - Cethana - 20h",
                "Pumped Hydro (10hrs storage)",
                "Pumped Hydro (24hrs storage)",
                "Pumped Hydro (48hrs storage)",
            ],
            "Installed capacity (MW)": [750, 1, 1, 1],
            "Storage capacity (hours)": [20, 10, 24, 48],
            "Pumping efficiency (%)": [80, 76, 76, 76],
        }
    ).to_csv(cache_dir / "pumped_hydro_new_entrant_properties.csv", index=False)
    pd.DataFrame(
        {
            "Name": ["Northern New South Wales", "Sydney, Newcastle, Wollongong"],
            "ISP Sub-region": ["NNSW", "SNW"],
            "Region": ["NSW", "NSW"],
            limit_prefix + "Pumped Hydro (10hrs storage)": [2500, 300],
            limit_prefix + "Pumped Hydro (24hrs storage)": [9400, 0],
            limit_prefix + "Pumped Hydro (48hrs storage)": [19500, 0],
            limit_prefix + "BOTN - Cethana - 20h": [0, 0],
        }
    ).to_csv(cache_dir / "build_limits_phes.csv", index=False)
    pd.DataFrame(
        {
            "Cost zone / REZ ID": ["NNSW", "SNW"],
            "Pumped Hydro (10hrs storage)": [1.0665480320721672, 1.046898289560425],
            "Pumped Hydro (24hrs storage)": [1.0601190499981938, 1.0614079424087675],
            "Pumped Hydro (48hrs storage)": [0.986125928742748, 1.0505176915510523],
        }
    ).to_csv(cache_dir / "technology_specific_lcfs.csv", index=False)
    pd.DataFrame(
        {
            "Region": ["NSW"],
            "Pumped Hydro (10hrs storage)": [101.50227785795153],
            "Pumped Hydro (24hrs storage)": [101.50227785795153],
            "Pumped Hydro (48hrs storage)": [101.50227785795153],
        }
    ).to_csv(cache_dir / "connection_costs_other.csv", index=False)
    pd.DataFrame(
        {
            "Technology type": [
                "Pumped Hydro (10hrs storage)",
                "Pumped Hydro (24hrs storage)",
                "Pumped Hydro (48hrs storage)",
                "BOTN - Cethana",
            ],
            "Step Change": [8.5, 8.5, 8.5, 8.5],
        }
    ).to_csv(cache_dir / "wacc.csv", index=False)
    pd.DataFrame(
        {
            "Technology": [
                "Pumped Hydro (10hrs storage)",
                "Pumped Hydro (24hrs storage)",
                "Pumped Hydro (48hrs storage)",
                "BOTN - Cethana",
            ],
            "Total lead time (years)": [8, 10, 10, 10],
            "Economic life (years)": [40, 40, 40, 40],
        }
    ).to_csv(cache_dir / "lead_time_and_project_life.csv", index=False)


def _stub_config(cache_dir, period):
    return SimpleNamespace(
        paths=SimpleNamespace(parsed_workbook_cache=str(cache_dir)),
        temporal=SimpleNamespace(
            capacity_expansion=SimpleNamespace(investment_periods=[period])
        ),
        scenario="Step Change",
    )


def _mini_build_costs():
    """Templated `new_entrant_build_costs` ($/MW) whose three published PHES
    points sit exactly on capex = 2,000,000 + 50,000 x duration in FY2050 and
    1,800,000 + 45,000 x duration in FY2040, so the fitted coefficients and the
    168/336 h evaluations are known by construction."""
    return pd.DataFrame(
        {
            "technology": [
                "Battery Storage (1hr storage)",
                "Pumped Hydro (10hrs storage)",
                "Pumped Hydro (24hrs storage)",
                "Pumped Hydro (48hrs storage)",
            ],
            "2039_40_$/mw": [500_000.0, 2_250_000.0, 2_880_000.0, 3_960_000.0],
            "2049_50_$/mw": [454_000.0, 2_500_000.0, 3_200_000.0, 4_400_000.0],
        }
    )


def _tables_with_one_battery(sub_regions=("NNSW", "SNW")):
    """`sub_regions` seeds ecaa_batteries so `_existing_sub_regions` treats
    them as present in the model (the pre-pass skips candidates elsewhere)."""
    new_entrants = pd.DataFrame(
        {
            "storage_name": ["battery_storage_1h_nnsw"],
            "technology_type": ["Battery Storage (1hr storage)"],
            "status": ["New Entrant"],
            "region_id": ["NSW"],
            "sub_region_id": ["NNSW"],
            "fuel_type": ["Battery"],
        }
    )
    ecaa = pd.DataFrame(
        {
            "storage_name": [f"Some BESS {s}" for s in sub_regions],
            "sub_region_id": list(sub_regions),
            "fuel_type": ["Battery"] * len(sub_regions),
        }
    )
    return {
        "new_entrant_batteries": new_entrants,
        "ecaa_batteries": ecaa,
        "new_entrant_build_costs": _mini_build_costs(),
    }


def test_phes_menu_2050_offers_candidates_where_limits_are_nonzero(tmp_path):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    phes = result["new_entrant_batteries"]
    phes = phes[phes["fuel_type"] == "Water"].reset_index(drop=True)
    # NNSW: 10h/24h/48h plus the two authored classes; SNW: 10h only (zero
    # 24h/48h limits, and the authored classes key off the 48h limit); no
    # BOTN (zero).
    assert sorted(phes["storage_name"]) == [
        "phes_10h_nnsw",
        "phes_10h_snw",
        "phes_168h_nnsw",
        "phes_24h_nnsw",
        "phes_336h_nnsw",
        "phes_48h_nnsw",
    ]
    row = phes.set_index("storage_name").loc["phes_24h_nnsw"]
    assert row["build_limit_mw"] == 9400.0
    assert row["storage_duration_hours"] == 24.0
    assert row["lifetime"] == 40.0
    assert row["wacc"] == pytest.approx(0.085)
    assert row["fom_$/kw/annum"] == pytest.approx(74.84505)
    assert row["technology_specific_lcf_%"] == pytest.approx(106.01190499981938)
    assert row["connection_cost_$/mw"] == pytest.approx(101502.27785795153)
    assert row["charging_efficiency_%"] == pytest.approx(100 * 0.76**0.5)


def test_phes_menu_2030_offers_no_candidates_before_lead_time(tmp_path, caplog):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()

    with caplog.at_level(logging.INFO):
        result = phes_menu_apply(tables, _stub_config(tmp_path, 2030))

    phes = result["new_entrant_batteries"]
    assert (phes["fuel_type"] == "Water").sum() == 0
    assert (
        "phes_menu: Pumped Hydro (10hrs storage) unavailable at 2030 "
        "(earliest build FY 2033 from IASR total lead time)"
    ) in caplog.text


def test_phes_menu_leaves_battery_rows_unchanged(tmp_path):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()
    battery_before = tables["new_entrant_batteries"].copy()

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    battery_after = result["new_entrant_batteries"]
    battery_after = battery_after[battery_after["fuel_type"] == "Battery"]
    pd.testing.assert_frame_equal(
        battery_after[battery_before.columns].reset_index(drop=True), battery_before
    )
    assert battery_after["build_limit_mw"].isna().all()


def test_phes_menu_appends_kidston_and_phoenix_to_ecaa(tmp_path):
    _write_mini_phes_cache(tmp_path)
    # make Kidston's (NQ) and Phoenix's (CNSW) sub-regions available
    tables = _tables_with_one_battery(sub_regions=("NQ", "CNSW"))

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    ecaa = result["ecaa_batteries"].set_index("storage_name")
    assert ecaa.loc["Kidston", "maximum_capacity_mw"] == 250.0
    assert ecaa.loc["Kidston", "storage_duration_hours"] == 3.6
    assert ecaa.loc["Kidston", "round_trip_efficiency_%"] == 80.0
    assert ecaa.loc["Kidston", "commissioning_date"] == "2027-01-01"
    assert ecaa.loc["Kidston", "closure_year"] == 2065
    assert ecaa.loc["Phoenix Pumped Hydro Project", "maximum_capacity_mw"] == 810.0
    assert ecaa.loc["Phoenix Pumped Hydro Project", "storage_duration_hours"] == 12.0
    assert (
        ecaa.loc["Phoenix Pumped Hydro Project", "commissioning_date"] == "2032-07-01"
    )


def test_phes_menu_multi_period_skips_with_warning(tmp_path, caplog):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()
    battery_before = tables["new_entrant_batteries"].copy()

    with caplog.at_level(logging.WARNING):
        result = phes_menu_apply(
            tables,
            SimpleNamespace(
                paths=SimpleNamespace(parsed_workbook_cache=str(tmp_path)),
                temporal=SimpleNamespace(
                    capacity_expansion=SimpleNamespace(investment_periods=[2030, 2050])
                ),
                scenario="Step Change",
            ),
        )

    pd.testing.assert_frame_equal(result["new_entrant_batteries"], battery_before)
    assert "PHES menu is NOT offered" in caplog.text


def test_phes_menu_configless_skips_with_warning(caplog):
    tables = _tables_with_one_battery()
    battery_before = tables["new_entrant_batteries"].copy()

    with caplog.at_level(logging.WARNING):
        result = phes_menu_apply(tables, config=None)

    pd.testing.assert_frame_equal(result["new_entrant_batteries"], battery_before)
    assert "PHES menu NOT offered" in caplog.text


def test_phes_menu_missing_cache_table_fails_loud(tmp_path):
    _write_mini_phes_cache(tmp_path)
    (tmp_path / "build_limits_phes.csv").unlink()

    with pytest.raises(FileNotFoundError, match="build_limits_phes"):
        phes_menu_apply(_tables_with_one_battery(), _stub_config(tmp_path, 2050))


# ---------------------------------------------------------------------------
# Authored long-duration classes: capex extrapolation
# ---------------------------------------------------------------------------


def test_capex_fit_extrapolates_published_points_to_168_and_336(csv_str_to_df):
    build_costs = _mini_build_costs()

    result = _append_extrapolated_build_costs(build_costs)

    expected = csv_str_to_df("""
        technology,                        2039_40_$/mw,  2049_50_$/mw
        Battery__Storage__(1hr__storage),  500000.0,      454000.0
        Pumped__Hydro__(10hrs__storage),   2250000.0,     2500000.0
        Pumped__Hydro__(24hrs__storage),   2880000.0,     3200000.0
        Pumped__Hydro__(48hrs__storage),   3960000.0,     4400000.0
        Pumped__Hydro__(168hrs__storage),  9360000.0,     10400000.0
        Pumped__Hydro__(336hrs__storage),  16920000.0,    18800000.0
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_capex_extrapolation_warns_with_auditable_coefficients(caplog):
    build_costs = _mini_build_costs()

    with caplog.at_level(logging.WARNING):
        _append_extrapolated_build_costs(build_costs)

    assert (
        "phes_menu: capex for ['Pumped Hydro (168hrs storage)', "
        "'Pumped Hydro (336hrs storage)'] is extrapolated beyond the published "
        "10-48 h duration range by a per-financial-year least-squares fit of "
        "capex against duration; FY2050 power cost 2000.0 $/kW, reservoir cost "
        "50.00 $/kW per storage hour"
    ) in caplog.text
    assert "is not linear in duration" not in caplog.text


def test_capex_fit_warns_when_published_points_are_not_linear(caplog):
    build_costs = _mini_build_costs()
    build_costs["2049_50_$/mw"] = [454_000.0, 2_000_000.0, 2_100_000.0, 5_000_000.0]

    with caplog.at_level(logging.WARNING):
        _append_extrapolated_build_costs(build_costs)

    assert (
        "phes_menu: published 10/24/48 h capex is not linear in duration "
        "(R-squared below 0.95) in financial years ['2049_50_$/mw']; the "
        "extrapolated 168/336 h capex is less reliable there"
    ) in caplog.text


# ---------------------------------------------------------------------------
# Authored long-duration classes: candidates and shared site limits
# ---------------------------------------------------------------------------


def test_long_duration_classes_inherit_the_48_hour_parameters(tmp_path, csv_str_to_df):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    columns = [
        "storage_name",
        "technology_type",
        "isp_resource_type",
        "storage_duration_hours",
        "round_trip_efficiency_%",
        "charging_efficiency_%",
        "fom_$/kw/annum",
        "technology_specific_lcf_%",
        "connection_cost_$/mw",
        "lifetime",
        "wacc",
        "build_limit_mw",
    ]
    long_duration = result["new_entrant_batteries"]
    long_duration = long_duration[
        long_duration["storage_name"].isin(["phes_168h_nnsw", "phes_336h_nnsw"])
    ]
    # build_limit_mw is NNSW's 48-hour limit (19,500 MW) for both classes.
    expected = csv_str_to_df("""
        storage_name,    technology_type,                   isp_resource_type,     storage_duration_hours, round_trip_efficiency_%, charging_efficiency_%, fom_$/kw/annum, technology_specific_lcf_%, connection_cost_$/mw, lifetime, wacc,  build_limit_mw
        phes_168h_nnsw,  Pumped__Hydro__(168hrs__storage),  Pumped__Hydro__168h,   168.0,                  76.0,                    87.17797887081348,     85.5372,        98.6125928742748,          101502.27785795153,   40.0,     0.085, 19500.0
        phes_336h_nnsw,  Pumped__Hydro__(336hrs__storage),  Pumped__Hydro__336h,   336.0,                  76.0,                    87.17797887081348,     85.5372,        98.6125928742748,          101502.27785795153,   40.0,     0.085, 19500.0
    """)
    pd.testing.assert_frame_equal(
        long_duration[columns].reset_index(drop=True), expected
    )


def test_long_duration_classes_gated_by_the_inherited_lead_time(tmp_path, caplog):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()

    with caplog.at_level(logging.INFO):
        result = phes_menu_apply(tables, _stub_config(tmp_path, 2034))

    phes = result["new_entrant_batteries"]
    assert phes["storage_name"].isin(["phes_168h_nnsw", "phes_336h_nnsw"]).sum() == 0
    assert (
        "phes_menu: Pumped Hydro (168hrs storage) unavailable at 2034 "
        "(earliest build FY 2035 from IASR total lead time)"
    ) in caplog.text


def test_shared_site_constraint_sums_every_phes_class_in_a_sub_region(
    tmp_path, csv_str_to_df
):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery()

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    # SNW has a zero 48-hour limit, so it gets no site constraint at all.
    expected_lhs = csv_str_to_df("""
        constraint_id,              term_type,         term_id,                  coefficient
        phes_site_limit_nnsw_2050,  storage_capacity,  phes_10h_nnsw_2050,       1.0
        phes_site_limit_nnsw_2050,  storage_capacity,  phes_24h_nnsw_2050,       1.0
        phes_site_limit_nnsw_2050,  storage_capacity,  phes_48h_nnsw_2050,       1.0
        phes_site_limit_nnsw_2050,  storage_capacity,  phes_168h_nnsw_2050,      1.0
        phes_site_limit_nnsw_2050,  storage_capacity,  phes_336h_nnsw_2050,      1.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_lhs"], expected_lhs)

    expected_rhs = csv_str_to_df("""
        constraint_id,              constraint_type,  rhs
        phes_site_limit_nnsw_2050,  <=,               19500.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_rhs"], expected_rhs)


def test_sub_region_without_a_48_hour_limit_gets_neither_long_duration_class(
    tmp_path,
):
    _write_mini_phes_cache(tmp_path)
    tables = _tables_with_one_battery(sub_regions=("SNW",))

    result = phes_menu_apply(tables, _stub_config(tmp_path, 2050))

    phes = result["new_entrant_batteries"]
    phes = phes[phes["fuel_type"] == "Water"]
    # SNW's only non-zero limit is the 10-hour class.
    assert sorted(phes["storage_name"]) == ["phes_10h_snw"]
    assert "custom_constraints_lhs" not in result


# ---------------------------------------------------------------------------
# Translator: build_limit_mw -> p_nom_max
# ---------------------------------------------------------------------------


def _translator_input_tables():
    new_entrant_batteries = pd.DataFrame(
        {
            "storage_name": ["battery_storage_1h_nnsw", "phes_24h_nnsw"],
            "isp_resource_type": ["Battery Storage 1h", "Pumped Hydro 24h"],
            "technology_type": [
                "Battery Storage (1hr storage)",
                "Pumped Hydro (24hrs storage)",
            ],
            "status": ["New Entrant", "New Entrant"],
            "region_id": ["NSW", "NSW"],
            "sub_region_id": ["NNSW", "NNSW"],
            "rez_id": [np.nan, np.nan],
            "fuel_type": ["Battery", "Water"],
            "fom_$/kw/annum": [9.1647, 74.84505],
            "connection_cost_$/mw": [84758.45506486473, 101502.27785795153],
            "technology_specific_lcf_%": [100.0, 106.01190499981938],
            "storage_duration_hours": [1.0, 24.0],
            "lifetime": [20, 40],
            "round_trip_efficiency_%": [84.0, 76.0],
            "charging_efficiency_%": [92.0, 100 * 0.76**0.5],
            "discharging_efficiency_%": [92.0, 100 * 0.76**0.5],
            "wacc": [0.08, 0.085],
            "build_limit_mw": [np.nan, 9400.0],
        }
    )
    build_costs = pd.DataFrame(
        {
            "technology": [
                "Battery Storage (1hr storage)",
                "Pumped Hydro (24hrs storage)",
            ],
            "2049_50_$/mw": [454000.0, 4338000.0],
        }
    )
    return {
        "new_entrant_batteries": new_entrant_batteries,
        "new_entrant_build_costs": build_costs,
    }


def test_translator_maps_build_limit_to_p_nom_max_and_fills_batteries_inf():
    tables = _translator_input_tables()

    translated = _translate_new_entrant_batteries(tables, [2050], wacc=0.07)

    result = _fill_missing_build_limits_with_inf(translated)

    result = result.set_index("name")
    assert result.loc["phes_24h_nnsw_2050", "p_nom_max"] == 9400.0
    assert np.isinf(result.loc["battery_storage_1h_nnsw_2050", "p_nom_max"])


def test_translator_phes_capital_cost_annuitises_at_workbook_wacc_and_life():
    tables = _translator_input_tables()

    result = _translate_new_entrant_batteries(tables, [2050], wacc=0.07)

    # (4,338,000 x 1.0601190499981938 + 101,502.27785795153) x CRF(8.5%, 40y)
    # + 74.84505 x 1000, CRF = 0.085 / (1 - 1.085^-40)
    crf = 0.085 / (1 - 1.085**-40)
    expected = (4338000.0 * 1.0601190499981938 + 101502.27785795153) * crf + 74845.05
    result = result.set_index("name")
    assert result.loc["phes_24h_nnsw_2050", "capital_cost"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Recursive-dynamic: carried PHES nets off candidate p_nom_max
# ---------------------------------------------------------------------------


def test_carried_phes_decrements_candidate_p_nom_max():
    batteries = pd.DataFrame(
        {
            "name": ["phes_24h_nnsw_2050", "phes_24h_nnsw_2040", "batt_1h_x_2050"],
            "p_nom": [0.0, 1200.0, 0.0],
            "p_nom_max": [9400.0, np.inf, np.inf],
            "p_nom_extendable": [True, False, True],
            "build_year": [2050, 2040, 2050],
        }
    )
    pypsa_friendly = {"batteries": batteries}

    adjustments = adjust_phes_build_limits_for_carried(pypsa_friendly, 2050)

    assert adjustments == {"phes_24h_nnsw": 1200.0}
    assert (
        pypsa_friendly["batteries"]
        .set_index("name")
        .loc["phes_24h_nnsw_2050", "p_nom_max"]
        == 8200.0
    )


def test_carried_adjustment_noop_without_p_nom_max_column():
    batteries = pd.DataFrame(
        {
            "name": ["batt_1h_x_2050"],
            "p_nom": [0.0],
            "p_nom_extendable": [True],
            "build_year": [2050],
        }
    )

    adjustments = adjust_phes_build_limits_for_carried({"batteries": batteries}, 2050)

    assert adjustments == {}
