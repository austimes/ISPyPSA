"""Tests for the Draft 2026 trace-coverage exclusions applied between templater and translator."""

import pandas as pd
import pytest

from analysis.model.flagged_exclusions_2026 import exclude_ecaa_without_trace


def test_an_empty_project_partition_names_the_trace_directory(tmp_path, csv_str_to_df):
    """A moved trace store leaves the VRE link dangling, which must name itself rather than fail inside pandas."""
    (tmp_path / "project").mkdir()
    ecaa = csv_str_to_df("""
        generator,       fuel_type
        Dulacca Wind,    Wind
    """)

    with pytest.raises(FileNotFoundError, match="No project VRE traces under"):
        exclude_ecaa_without_trace(ecaa, tmp_path)


def test_ecaa_vre_without_a_matching_project_trace_is_dropped(tmp_path, csv_str_to_df):
    partition = tmp_path / "project" / "reference_year=2018"
    partition.mkdir(parents=True)
    pd.DataFrame({"project": ["Dulacca Wind"]}).to_parquet(
        partition / "data_0.parquet", index=False
    )
    ecaa = csv_str_to_df("""
        generator,       fuel_type
        Dulacca Wind,    Wind
        Missing Solar,   Solar
        Bayswater,       Black Coal
    """)

    result = exclude_ecaa_without_trace(ecaa, tmp_path)

    expected = csv_str_to_df("""
        generator,       fuel_type
        Dulacca Wind,    Wind
        Bayswater,       Black Coal
    """)
    pd.testing.assert_frame_equal(result, expected)
