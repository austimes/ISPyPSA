# tests/test_translator/test_helpers.py
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from ispypsa.translator.helpers import (
    _add_investment_periods_as_build_years,
    _extend_trajectory_to_periods,
    _get_financial_year_int_from_string,
)


def test_get_financial_year_int_from_string():
    """Test financial year string translation to integer."""
    # Standard financial year format
    assert _get_financial_year_int_from_string("2023_24", "test", "fy") == 2024
    assert _get_financial_year_int_from_string("2023_24_extra", "test", "fy") == 2024
    assert _get_financial_year_int_from_string("2099_00", "test", "fy") == 2100

    # Error cases
    with pytest.raises(ValueError, match="Invalid financial year string"):
        _get_financial_year_int_from_string("invalid", "test", "fy")

    with pytest.raises(ValueError, match="Unknown year_type"):
        _get_financial_year_int_from_string("2023_24", "test", "unknown")

    with pytest.raises(NotImplementedError, match="Calendar years are not implemented"):
        _get_financial_year_int_from_string("2023", "test", "calendar")


def test_add_investment_periods_as_build_years(csv_str_to_df):
    """Test adding investment periods as build years to a DataFrame."""
    # Input DataFrame
    input_df_csv = """
    generator_name,  technology,  capacity_mw
    Gen1,            Solar,       100
    Gen2,            Wind,        200
    """
    input_df = csv_str_to_df(input_df_csv)

    # Investment periods
    investment_periods = [2020, 2025, 2030]

    # Call the function
    result = _add_investment_periods_as_build_years(input_df, investment_periods)

    # Expected result
    expected_csv = """
    generator_name,  technology,  capacity_mw,  build_year
    Gen1,            Solar,       100,          2020
    Gen1,            Solar,       100,          2025
    Gen1,            Solar,       100,          2030
    Gen2,            Wind,        200,          2020
    Gen2,            Wind,        200,          2025
    Gen2,            Wind,        200,          2030
    """
    expected = csv_str_to_df(expected_csv)

    # Sort both DataFrames for consistent comparison
    pd.testing.assert_frame_equal(
        result.sort_values(["generator_name", "build_year"]).reset_index(drop=True),
        expected.sort_values(["generator_name", "build_year"]).reset_index(drop=True),
    )


def test_add_investment_periods_as_build_years_empty(csv_str_to_df):
    """Test adding investment periods to an empty DataFrame."""
    # Empty input DataFrame
    input_df = pd.DataFrame(columns=["generator_name", "technology", "capacity_mw"])

    # Investment periods
    investment_periods = [2020, 2025, 2030]

    # Call the function
    result = _add_investment_periods_as_build_years(input_df, investment_periods)

    # Expected result - empty DataFrame with build_year column
    expected = pd.DataFrame(
        columns=["generator_name", "technology", "capacity_mw", "build_year"]
    )

    # Compare DataFrames
    assert result.empty
    assert "build_year" in result.columns
    assert list(result.columns) == list(expected.columns)


def test_extend_trajectory_to_periods_within_published_span(csv_str_to_df, caplog):
    """Periods inside the published span leave the trajectory untouched."""
    trajectory = csv_str_to_df("""
    technology,  build_year,  cost_$/mw
    CCGT,        2053,        1900000
    CCGT,        2054,        1850000
    """)

    with caplog.at_level("WARNING"):
        result = _extend_trajectory_to_periods(
            trajectory, "build_year", [2050, 2053, 2054]
        )

    expected = csv_str_to_df("""
    technology,  build_year,  cost_$/mw
    CCGT,        2053,        1900000
    CCGT,        2054,        1850000
    """)
    pd.testing.assert_frame_equal(result, expected)
    assert "Trajectory held at" not in caplog.text


def test_extend_trajectory_to_periods_beyond_published_span(csv_str_to_df, caplog):
    """Periods beyond the last published year repeat that year's rows, and log once."""
    trajectory = csv_str_to_df("""
    technology,  build_year,  cost_$/mw
    CCGT,        2053,        1900000
    CCGT,        2054,        1850000
    Wind,        2053,        2900000
    Wind,        2054,        2800000
    """)

    with caplog.at_level("WARNING"):
        result = _extend_trajectory_to_periods(
            trajectory, "build_year", [2054, 2060, 2065]
        )

    expected = csv_str_to_df("""
    technology,  build_year,  cost_$/mw
    CCGT,        2053,        1900000
    CCGT,        2054,        1850000
    Wind,        2053,        2900000
    Wind,        2054,        2800000
    CCGT,        2060,        1850000
    Wind,        2060,        2800000
    CCGT,        2065,        1850000
    Wind,        2065,        2800000
    """)
    pd.testing.assert_frame_equal(result, expected)
    assert (
        "Trajectory held at FY2054 for investment periods beyond the published "
        "data: [2060, 2065]"
    ) in caplog.text


def test_extend_trajectory_to_periods_empty(caplog):
    """An empty trajectory has no published year to hold, so it is returned as is."""
    trajectory = pd.DataFrame(columns=["technology", "build_year", "cost_$/mw"])

    with caplog.at_level("WARNING"):
        result = _extend_trajectory_to_periods(trajectory, "build_year", [2060])

    expected = pd.DataFrame(columns=["technology", "build_year", "cost_$/mw"])
    pd.testing.assert_frame_equal(result, expected)
    assert "Trajectory held at" not in caplog.text
