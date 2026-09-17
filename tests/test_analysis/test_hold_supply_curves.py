import pandas as pd

from analysis.extension_campaign.hold_supply_curves import hold_curve_to_years


def test_hold_curve_repeats_last_year_for_each_missing_year(csv_str_to_df, caplog):
    curve = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2054,           100,    0.0
        existing,  2055,           110,    0.0
        imports,   2055,           20,     4.5
    """)

    with caplog.at_level("WARNING"):
        held = hold_curve_to_years(curve, [2055, 2060, 2070])

    expected = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2054,           100,    0.0
        existing,  2055,           110,    0.0
        imports,   2055,           20,     4.5
        existing,  2060,           110,    0.0
        imports,   2060,           20,     4.5
        existing,  2070,           110,    0.0
        imports,   2070,           20,     4.5
    """)
    pd.testing.assert_frame_equal(held, expected, check_dtype=False)
    assert (
        "Supply curve held at FY2055 for investment periods beyond the published "
        "data: [2060, 2070]"
    ) in caplog.text


def test_hold_curve_is_identity_inside_published_span(csv_str_to_df, caplog):
    curve = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2050,           100,    0.0
        existing,  2055,           110,    0.0
    """)

    with caplog.at_level("WARNING"):
        held = hold_curve_to_years(curve, [2050, 2055])

    pd.testing.assert_frame_equal(held, curve)
    assert "Supply curve held" not in caplog.text
