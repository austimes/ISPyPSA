import pandas as pd
import pytest

from ispypsa.translator.ccs_supply_curve import (
    _add_ccs_transport_columns,
    _map_generators_to_sinks,
    _translate_ccs_sink_tranches,
    _translate_ccs_transport_adders,
    _validate_sinks_have_tranches,
)

_TRANCHE_CSV = "sink,financial_year,cap_kt,storage_$/t\n"
_TRANSPORT_CSV = "isp_sub_region_id,sink,distance_km,transport_$/t\n"


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def _generators(csv_str_to_df):
    return csv_str_to_df("""
        name,                    bus,   isp_captured_co2_t_per_mwh
        ccgt_with_ccs_snw_2050,  SNW,   0.419232
        ccgt_with_ccs_sq_2050,   SQ,    0.419232
        ccgt_snw_2050,           SNW,   0.0
        wind_snw_2050,           SNW,
    """)


def test_translate_sink_tranches_filters_to_investment_periods(tmp_path):
    csv = _write(
        tmp_path,
        "tranches.csv",
        _TRANCHE_CSV
        + "carbonnet,2045,3000.0,18.5\n"
        + "carbonnet,2050,3000.0,18.5\n"
        + "cooper_hub,2045,10000.0,18.5\n"
        + "cooper_hub,2050,10000.0,18.5\n",
    )

    result = _translate_ccs_sink_tranches(csv, [2050])

    expected = pd.DataFrame(
        {
            "investment_period": [2050, 2050],
            "sink": ["carbonnet", "cooper_hub"],
            "cap_kt": [3000.0, 10000.0],
            "storage_$/t": [18.5, 18.5],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_translate_sink_tranches_keeps_an_all_zero_variant(tmp_path):
    """The conservative variant is all zeros and is a valid curve, not an empty one:
    it states that no injection is available. There is no uncapped backstop to
    require, unlike the fuel supply curves."""
    csv = _write(tmp_path, "tranches.csv", _TRANCHE_CSV + "carbonnet,2050,0.0,18.5\n")

    result = _translate_ccs_sink_tranches(csv, [2050])

    expected = pd.DataFrame(
        {
            "investment_period": [2050],
            "sink": ["carbonnet"],
            "cap_kt": [0.0],
            "storage_$/t": [18.5],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_translate_sink_tranches_raises_on_missing_columns(tmp_path):
    csv = _write(tmp_path, "tranches.csv", "sink,financial_year\ncarbonnet,2050\n")

    with pytest.raises(
        ValueError, match=r"missing columns: \['cap_kt', 'storage_\$/t'\]"
    ):
        _translate_ccs_sink_tranches(csv, [2050])


def test_translate_sink_tranches_raises_on_uncovered_investment_period(tmp_path):
    csv = _write(
        tmp_path, "tranches.csv", _TRANCHE_CSV + "carbonnet,2050,3000.0,18.5\n"
    )

    with pytest.raises(
        ValueError, match=r"investment period pairs: \[\('carbonnet', 2030\)\]"
    ):
        _translate_ccs_sink_tranches(csv, [2030, 2050])


def test_translate_sink_tranches_raises_on_a_sink_and_period_gap(tmp_path):
    """Both periods and both sinks appear, but cooper_hub has no 2030 row. Checking
    sinks and periods separately would pass this and leave the build with no cap or
    price for cooper_hub in 2030."""
    csv = _write(
        tmp_path,
        "tranches.csv",
        _TRANCHE_CSV
        + "carbonnet,2030,3000.0,18.5\n"
        + "carbonnet,2050,3000.0,18.5\n"
        + "cooper_hub,2050,10000.0,18.5\n",
    )

    with pytest.raises(
        ValueError, match=r"investment period pairs: \[\('cooper_hub', 2030\)\]"
    ):
        _translate_ccs_sink_tranches(csv, [2030, 2050])


def test_translate_sink_tranches_raises_on_repeated_sink_and_period(tmp_path):
    """Two rows for one sink and period would have their caps added together while
    only one row's storage price was charged."""
    csv = _write(
        tmp_path,
        "tranches.csv",
        _TRANCHE_CSV + "carbonnet,2050,3000.0,18.5\n" + "carbonnet,2050,1000.0,45.0\n",
    )

    with pytest.raises(
        ValueError,
        match=r"more than one row for these sink and investment period "
        r"pairs: \[\('carbonnet', 2050\)\]",
    ):
        _translate_ccs_sink_tranches(csv, [2050])


def test_translate_transport_adders_selects_the_assignment_columns(tmp_path):
    csv = _write(
        tmp_path,
        "transport.csv",
        _TRANSPORT_CSV + "SNW,carbonnet,770.0,84.39\nSQ,cooper_hub,1580.0,173.17\n",
    )

    result = _translate_ccs_transport_adders(csv)

    expected = pd.DataFrame(
        {
            "isp_sub_region_id": ["SNW", "SQ"],
            "sink": ["carbonnet", "cooper_hub"],
            "transport_$/t": [84.39, 173.17],
        }
    )
    pd.testing.assert_frame_equal(result, expected)


def test_translate_transport_adders_raises_on_duplicate_sub_region(tmp_path):
    csv = _write(
        tmp_path,
        "transport.csv",
        _TRANSPORT_CSV + "SNW,carbonnet,770.0,84.39\nSNW,cooper_hub,1500.0,164.4\n",
    )

    with pytest.raises(
        ValueError, match=r"more than one sink to sub-regions: \['SNW'\]"
    ):
        _translate_ccs_transport_adders(csv)


def test_add_transport_columns_prices_only_capturing_generators(csv_str_to_df):
    adders = csv_str_to_df("""
        isp_sub_region_id,  sink,        transport_$/t
        SNW,                carbonnet,   84.39
        SQ,                 cooper_hub,  173.17
    """)

    result = _add_ccs_transport_columns(_generators(csv_str_to_df), adders)

    expected = csv_str_to_df("""
        name,                    bus,   isp_captured_co2_t_per_mwh,  isp_ccs_transport_$/t
        ccgt_with_ccs_snw_2050,  SNW,   0.419232,                    84.39
        ccgt_with_ccs_sq_2050,   SQ,    0.419232,                    173.17
        ccgt_snw_2050,           SNW,   0.0,                         0.0
        wind_snw_2050,           SNW,   ,                            0.0
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_add_transport_columns_is_idempotent(csv_str_to_df):
    """Re-applied after carried recursive-dynamic rows are appended, so applying it
    twice must not change the answer."""
    adders = csv_str_to_df("""
        isp_sub_region_id,  sink,        transport_$/t
        SNW,                carbonnet,   84.39
        SQ,                 cooper_hub,  173.17
    """)
    generators = _generators(csv_str_to_df)

    once = _add_ccs_transport_columns(generators, adders)
    twice = _add_ccs_transport_columns(once, adders)

    pd.testing.assert_frame_equal(once, twice)


def test_add_transport_columns_raises_when_a_capturing_bus_is_unassigned(
    csv_str_to_df,
):
    adders = csv_str_to_df("""
        isp_sub_region_id,  sink,       transport_$/t
        SNW,                carbonnet,  84.39
    """)

    with pytest.raises(ValueError, match=r"cannot be priced: \['SQ'\]"):
        _add_ccs_transport_columns(_generators(csv_str_to_df), adders)


def test_map_generators_to_sinks_covers_only_capturing_generators(csv_str_to_df):
    adders = csv_str_to_df("""
        isp_sub_region_id,  sink,        transport_$/t
        SNW,                carbonnet,   84.39
        SQ,                 cooper_hub,  173.17
    """)

    result = _map_generators_to_sinks(_generators(csv_str_to_df), adders)

    expected = pd.Series(
        ["carbonnet", "cooper_hub"],
        index=pd.Index(
            ["ccgt_with_ccs_snw_2050", "ccgt_with_ccs_sq_2050"], name="name"
        ),
        name="bus",
    )
    pd.testing.assert_series_equal(result, expected)


def test_validate_sinks_have_tranches_raises_when_a_sink_is_unconstrained(
    csv_str_to_df,
):
    """A bus assigned to a sink with no tranche rows would dispose of its CO2
    without any injectivity limit at all, which is the silent hole this guards."""
    adders = csv_str_to_df("""
        isp_sub_region_id,  sink,        transport_$/t
        SNW,                carbonnet,   84.39
        SQ,                 cooper_hub,  173.17
    """)
    tranches = csv_str_to_df("""
        investment_period,  sink,       cap_kt,  storage_$/t
        2050,               carbonnet,  3000.0,  18.5
    """)

    with pytest.raises(
        ValueError, match=r"no injectivity tranche rows.*\['cooper_hub'\]"
    ):
        _validate_sinks_have_tranches(adders, tranches)
