from pathlib import Path

import pandas as pd
import pytest

from ispypsa.data_fetch import read_csvs
from ispypsa.templater.energy_policy_targets import (
    _template_renewable_generation_targets,
    _template_renewable_share_targets,
    _template_technology_capacity_targets,
)


def test_template_renewable_share_targets(workbook_table_cache_test_path: Path):
    """Test the renewable share targets template creation"""

    iasr_tables = read_csvs(workbook_table_cache_test_path)

    df = _template_renewable_share_targets(iasr_tables)

    # Check basic DataFrame structure
    expected_columns = ["FY", "region_id", "pct", "policy_id"]
    assert all(col in df.columns for col in expected_columns)

    # Check data types
    assert df["FY"].dtype == "object"  # String type
    assert df["region_id"].dtype == "object"  # String type
    assert df["policy_id"].dtype == "object"  # String type
    assert df["pct"].dtype == "float64"
    assert all(df["pct"].between(0, 100))

    # Check that FY format is correct (YYYY_YY)
    assert all(df["FY"].str.match(r"\d{4}_\d{2}"))

    # Check expected regions are present
    expected_regions = {"VIC", "SA"}
    assert set(df["region_id"]) == expected_regions

    # Test specific known values (sample check)
    vic_2024 = df[(df["region_id"] == "VIC") & (df["FY"] == "2024_25")]["pct"].iloc[0]
    sa_2026 = df[(df["region_id"] == "SA") & (df["FY"] == "2026_27")]["pct"].iloc[0]

    assert vic_2024 == 40
    assert sa_2026 == 100

    # test specific known values (sample check)
    vic_policy_2024 = df[(df["region_id"] == "VIC") & (df["FY"] == "2024_25")][
        "policy_id"
    ].iloc[0]
    sa_policy_2026 = df[(df["region_id"] == "SA") & (df["FY"] == "2026_27")][
        "policy_id"
    ].iloc[0]

    assert vic_policy_2024 == "vret"
    assert sa_policy_2026 == "sa_net_renewable"


def test_template_technology_capacity_targets(workbook_table_cache_test_path: Path):
    """Test the technology capacity targets template creation"""

    iasr_tables = read_csvs(workbook_table_cache_test_path)
    df = _template_technology_capacity_targets(iasr_tables)

    # Check basic DataFrame structure
    expected_columns = ["FY", "region_id", "capacity_mw", "policy_id"]
    assert all(col in df.columns for col in expected_columns)

    # Check data types
    assert df["FY"].dtype == "object"  # String type
    assert df["region_id"].dtype == "object"  # String type
    assert df["capacity_mw"].dtype == "float64"
    assert df["policy_id"].dtype == "object"  # String type

    # Check that capacity values are non-negative
    assert all(df["capacity_mw"] >= 0)

    # Check that FY format is correct (YYYY_YY)
    assert all(df["FY"].str.match(r"\d{4}_\d{2}"))

    # Check expected technologies are present
    expected_policy_ids = {"nsw_eir_sto", "vic_storage", "vic_offshore_wind"}
    assert set(df["policy_id"]) == expected_policy_ids

    # Test specific known values (sample check)
    vic_storage_2029 = df[
        (df["region_id"] == "VIC")
        & (df["policy_id"] == "vic_storage")
        & (df["FY"] == "2029_30")
    ]["capacity_mw"].iloc[0]
    nsw_storage_2029 = df[
        (df["region_id"] == "NSW")
        & (df["policy_id"] == "nsw_eir_sto")
        & (df["FY"] == "2029_30")
    ]["capacity_mw"].iloc[0]

    assert vic_storage_2029 == 2600.0
    assert nsw_storage_2029 == 2000.0

    # Check sorting
    assert df.equals(
        df.sort_values(["region_id", "policy_id", "FY"]).reset_index(drop=True)
    )


def test_template_renewable_generation_targets(workbook_table_cache_test_path: Path):
    """Test the renewable generation targets template creation"""
    iasr_tables = read_csvs(workbook_table_cache_test_path)
    df = _template_renewable_generation_targets(iasr_tables, "Step Change")

    # Check basic DataFrame structure
    expected_columns = ["FY", "region_id", "capacity_mwh"]
    assert all(col in df.columns for col in expected_columns)

    # Check data types
    assert df["FY"].dtype == "object"  # String type
    assert df["region_id"].dtype == "object"  # String type
    assert df["capacity_mwh"].dtype == "float64"
    assert df["policy_id"].dtype == "object"  # String type

    # Check that capacity values are non-negative
    assert all(df["capacity_mwh"] >= 0)

    # Check that FY format is correct (YYYY_YY)
    assert all(df["FY"].str.match(r"\d{4}_\d{2}"))

    # Test specific known values (sample check)
    nsw_2029 = df[(df["region_id"] == "NSW") & (df["FY"] == "2029_30")][
        "capacity_mwh"
    ].iloc[0]
    tas_2039 = df[(df["region_id"] == "TAS") & (df["FY"] == "2039_40")][
        "capacity_mwh"
    ].iloc[0]

    assert nsw_2029 == 43291000.0
    assert tas_2039 == 21000000.0

    # Verify no "Notes" rows in output
    assert not df["FY"].str.contains("Notes", case=False).any()


def test_template_technology_capacity_targets_iasr_v7_tables(csv_str_to_df):
    iasr_tables = {
        "vic_offshore_wind_target": csv_str_to_df("""
            Calendar__year,  All__scenarios
            2032,            2.0__GW
            2040,            9.0__GW
        """),
        "nsw_roadmap_storage_power_capacity_trajectory": csv_str_to_df("""
            Financial__year,                 2029-30
            NSW__EIR__Storage__Target__(MW),  2000
        """),
        "vic_storage_target": csv_str_to_df("""
            Calendar__year,  All__scenarios
            2030,            2.6__GW
        """),
    }

    result = _template_technology_capacity_targets(iasr_tables)

    expected = csv_str_to_df("""
        FY,       capacity_mw,  region_id,  policy_id
        2029_30,  2000.0,       NSW,        nsw_eir_sto
        2031_32,  2000.0,       VIC,        vic_offshore_wind
        2039_40,  9000.0,       VIC,        vic_offshore_wind
        2029_30,  2600.0,       VIC,        vic_storage
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_template_renewable_share_targets_iasr_v7_tables(csv_str_to_df):
    iasr_tables = {
        "vic_renewable_target": csv_str_to_df("""
            Calendar__year,  All__scenarios
            2025,            40.0
            2030,            65.0
        """),
        "sa_renewable_generation_target": csv_str_to_df("""
            Financial__year,  All__scenarios
            2026-27,          100
        """),
    }

    result = _template_renewable_share_targets(iasr_tables)

    expected = csv_str_to_df("""
        FY,       region_id,  policy_id,         pct
        2024_25,  VIC,        vret,              40.0
        2029_30,  VIC,        vret,              65.0
        2026_27,  SA,         sa_net_renewable,  100.0
    """)
    pd.testing.assert_frame_equal(result, expected)


@pytest.fixture
def renewable_generation_tables(csv_str_to_df):
    return {
        "nsw_roadmap_min_vre_generation_target": csv_str_to_df("""
            Financial__year,                                2028-29,  2029-30
            NSW__EIR__Generation__Target__(GWh),            ,         33600
            NSW__IIO__Modelled__Generation__Target__(GWh),  29199,    43291
        """),
        "tas_renewable_target_trajectory": csv_str_to_df("""
            Financial__year,                2029-30
            Generation__target__(GWh),      15750
            Notes,                          Target__year
        """),
    }


def test_template_renewable_generation_targets_keeps_nsw_iio_row(
    renewable_generation_tables, csv_str_to_df
):
    result = _template_renewable_generation_targets(
        renewable_generation_tables, "Step Change"
    )

    expected = csv_str_to_df("""
        FY,       region_id,  policy_id,    capacity_mwh
        2029_30,  TAS,        tret,         15750000.0
        2028_29,  NSW,        nsw_iio_gen,  29199000.0
        2029_30,  NSW,        nsw_iio_gen,  43291000.0
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_template_renewable_generation_targets_keeps_nsw_eir_row_in_slower_growth(
    renewable_generation_tables, csv_str_to_df
):
    result = _template_renewable_generation_targets(
        renewable_generation_tables, "Progressive Change"
    )

    expected = csv_str_to_df("""
        FY,       region_id,  policy_id,    capacity_mwh
        2029_30,  TAS,        tret,         15750000.0
        2029_30,  NSW,        nsw_iio_gen,  33600000.0
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_template_renewable_share_targets_raises_on_missing_table(csv_str_to_df):
    iasr_tables = {
        "vic_renewable_target": csv_str_to_df("""
            Calendar__year,  All__scenarios
            2030,            65.0
        """),
    }

    with pytest.raises(KeyError, match="sa_renewable_generation_target"):
        _template_renewable_share_targets(iasr_tables)
