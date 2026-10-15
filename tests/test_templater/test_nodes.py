from pathlib import Path

import pandas as pd

from ispypsa.templater.nodes import (
    _template_regions,
    _template_sub_regions,
)


def test_node_templater_nem_regions(
    workbook_table_cache_test_path: Path, csv_str_to_df
):
    filepath = workbook_table_cache_test_path / Path("regional_reference_nodes.csv")
    regional_reference_nodes = pd.read_csv(filepath)

    regional_template = _template_regions(regional_reference_nodes)

    expected = csv_str_to_df("""
        nem_region_id,  isp_sub_region_id,  regional_reference_node,  regional_reference_node_voltage_kv
        QLD,            SQ,                 South__Pine,              275
        NSW,            SNW,                Sydney__West,             330
        VIC,            MEL,                Thomastown,               66
        SA,             CSA,                Torrens__Island,          66
        TAS,            TAS,                George__Town,             220
    """)
    pd.testing.assert_frame_equal(regional_template, expected)


def test_templater_sub_regions(workbook_table_cache_test_path: Path, csv_str_to_df):
    filepath = workbook_table_cache_test_path / Path("sub_regional_reference_nodes.csv")
    sub_regional_reference_nodes = pd.read_csv(filepath)

    sub_regions_template = _template_sub_regions(sub_regional_reference_nodes)

    expected = csv_str_to_df("""
        isp_sub_region_id,  nem_region_id,  sub_region_reference_node,  sub_region_reference_node_voltage_kv
        NQ,                 QLD,            Ross,                       275
        CQ,                 QLD,            Broadsound,                 275
        GG,                 QLD,            Calliope__River,            275
        SQ,                 QLD,            South__Pine,                275
        NNSW,               NSW,            Armidale,                   330
        CNSW,               NSW,            Wellington,                 330
        SNSW,               NSW,            Canberra,                   330
        SNW,                NSW,            Sydney__West,               330
        WNV,                VIC,            Moorabool,                  220
        SEV,                VIC,            Hazelwood,                  500
        MEL,                VIC,            Thomastown,                 66
        NSA,                SA,             Davenport,                  275
        CSA,                SA,             Torrens__Island,            66
        SESA,               SA,             South__East,                132
        TAS,                TAS,            George__Town,               220
    """)
    pd.testing.assert_frame_equal(sub_regions_template, expected)


def test_templater_sub_regions_mapping_only(
    workbook_table_cache_test_path: Path, csv_str_to_df
):
    filepath = workbook_table_cache_test_path / Path("sub_regional_reference_nodes.csv")
    sub_regional_reference_nodes = pd.read_csv(filepath)

    sub_regions_template = _template_sub_regions(
        sub_regional_reference_nodes, mapping_only=True
    )

    expected = csv_str_to_df("""
        isp_sub_region_id,  nem_region_id
        NQ,                 QLD
        CQ,                 QLD
        GG,                 QLD
        SQ,                 QLD
        NNSW,               NSW
        CNSW,               NSW
        SNSW,               NSW
        SNW,                NSW
        WNV,                VIC
        SEV,                VIC
        MEL,                VIC
        NSA,                SA
        CSA,                SA
        SESA,               SA
        TAS,                TAS
    """)
    pd.testing.assert_frame_equal(sub_regions_template, expected)
