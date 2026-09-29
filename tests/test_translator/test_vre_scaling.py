import pandas as pd

from ispypsa.translator.vre_scaling import scale_sampled_vre_trace


def test_scaled_sampled_mean_matches_full_year_mean_per_period(csv_str_to_df, caplog):
    trace = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.2
        2,          0.4
        3,          0.6
        4,          0.8
        5,          0.4
        6,          0.2
    """)
    snapshots = csv_str_to_df("""
        snapshots,  investment_periods,  generators
        1,          2025,                1.0
        2,          2025,                1.0
        5,          2030,                1.0
    """)
    full_year_snapshots = csv_str_to_df("""
        snapshots,  investment_periods
        1,          2025
        2,          2025
        3,          2025
        4,          2025
        5,          2030
        6,          2030
    """)

    with caplog.at_level("INFO"):
        result = scale_sampled_vre_trace(
            "Wind Farm A", trace, snapshots, full_year_snapshots
        )

    expected = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.3333333
        2,          0.6666667
        5,          0.3
    """)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-5)
    assert caplog.text == ""


def test_capped_energy_is_redistributed_over_uncapped_snapshots(csv_str_to_df):
    trace = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.9
        2,          0.3
        3,          1.0
        4,          1.0
    """)
    snapshots = csv_str_to_df("""
        snapshots,  investment_periods,  generators
        1,          2025,                1.0
        2,          2025,                1.0
    """)
    full_year_snapshots = csv_str_to_df("""
        snapshots,  investment_periods
        1,          2025
        2,          2025
        3,          2025
        4,          2025
    """)

    result = scale_sampled_vre_trace(
        "Wind Farm A", trace, snapshots, full_year_snapshots
    )

    expected = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          1.0
        2,          0.6
    """)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-5)


def test_zero_availability_trace_is_unchanged(csv_str_to_df):
    trace = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.0
        2,          0.0
        3,          0.0
    """)
    snapshots = csv_str_to_df("""
        snapshots,  investment_periods,  generators
        1,          2025,                1.0
        2,          2025,                1.0
    """)
    full_year_snapshots = csv_str_to_df("""
        snapshots,  investment_periods
        1,          2025
        2,          2025
        3,          2025
    """)

    result = scale_sampled_vre_trace(
        "Solar Farm A", trace, snapshots, full_year_snapshots
    )

    expected = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.0
        2,          0.0
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_snapshot_weights_set_the_sampled_mean(csv_str_to_df):
    trace = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.2
        2,          0.6
        3,          0.5
        4,          0.5
    """)
    snapshots = csv_str_to_df("""
        snapshots,  investment_periods,  generators
        1,          2025,                3.0
        2,          2025,                1.0
    """)
    full_year_snapshots = csv_str_to_df("""
        snapshots,  investment_periods
        1,          2025
        2,          2025
        3,          2025
        4,          2025
    """)

    result = scale_sampled_vre_trace(
        "Solar Farm A", trace, snapshots, full_year_snapshots
    )

    expected = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          0.3
        2,          0.9
    """)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-5)


def test_logs_generators_whose_target_the_cap_blocks(csv_str_to_df, caplog):
    trace = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          1.0
        2,          0.0
        3,          1.0
        4,          1.0
    """)
    snapshots = csv_str_to_df("""
        snapshots,  investment_periods,  generators
        1,          2025,                1.0
        2,          2025,                1.0
    """)
    full_year_snapshots = csv_str_to_df("""
        snapshots,  investment_periods
        1,          2025
        2,          2025
        3,          2025
        4,          2025
    """)

    with caplog.at_level("INFO"):
        result = scale_sampled_vre_trace(
            "Wind Farm A", trace, snapshots, full_year_snapshots
        )

    expected = csv_str_to_df("""
        snapshots,  p_max_pu
        1,          1.0
        2,          0.0
    """)
    pd.testing.assert_frame_equal(result, expected)
    assert (
        "Sampled availability of Wind Farm A is capped at 1 and stays below its "
        "full-year mean in investment periods: [2025]"
    ) in caplog.text
