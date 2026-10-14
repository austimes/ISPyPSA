import pandas as pd

from ispypsa.translator.technology_capacity_targets import (
    _map_buses_to_nem_regions,
    _translate_technology_capacity_targets,
)


def test_translate_technology_capacity_targets(csv_str_to_df):
    targets = csv_str_to_df("""
        FY,       region_id,  policy_id,          capacity_mw
        2029_30,  NSW,        nsw_eir_sto,        2000.0
        2032_33,  VIC,        vic_offshore_wind,  2000.0
        2035_36,  VIC,        vic_offshore_wind,  4000.0
        2026_27,  NEM,        cis_generator,      4000.0
    """)
    generators = csv_str_to_df("""
        name,              bus,   build_year,  lifetime,  isp_technology_type
        offshore_v8_2030,  V8,    2030,        30,        Wind__-__offshore__(fixed)
        offshore_v8_2035,  V8,    2035,        30,        Wind__-__offshore__(fixed)
        offshore_n10_2035, N10,   2035,        30,        Wind__-__offshore__(floating)
        onshore_v8_2035,   V8,    2035,        30,        Wind
    """)
    batteries = csv_str_to_df("""
        name,            bus,   build_year,  lifetime,  max_hours
        existing_8h,     CNSW,  2025,        8,         8.0
        new_8h_2035,     CNSW,  2035,        20,        8.0
        new_2h_2035,     CNSW,  2035,        20,        2.0
    """)
    sub_regions = csv_str_to_df("""
        isp_sub_region_id,  nem_region_id
        CNSW,               NSW
        SEV,                VIC
        TAS,                TAS
    """)
    renewable_energy_zones = csv_str_to_df("""
        rez_id,  isp_sub_region_id
        N10,     CNSW
        V8,      SEV
    """)

    lhs, rhs = _translate_technology_capacity_targets(
        targets,
        {"generators": generators, "batteries": batteries},
        _map_buses_to_nem_regions(sub_regions, renewable_energy_zones),
        [2030, 2035],
    )

    expected_rhs = csv_str_to_df("""
        constraint_name,         rhs,     constraint_type
        nsw_eir_sto_2030,        2000.0,  >=
        nsw_eir_sto_2035,        2000.0,  >=
        vic_offshore_wind_2035,  2000.0,  >=
    """)
    pd.testing.assert_frame_equal(
        rhs.sort_values("constraint_name").reset_index(drop=True), expected_rhs
    )
    expected_lhs = csv_str_to_df("""
        constraint_name,         variable_name,     coefficient,  component,    attribute
        nsw_eir_sto_2030,        existing_8h,       1.0,          StorageUnit,  p_nom
        nsw_eir_sto_2035,        new_8h_2035,       1.0,          StorageUnit,  p_nom
        vic_offshore_wind_2035,  offshore_v8_2030,  1.0,          Generator,    p_nom
        vic_offshore_wind_2035,  offshore_v8_2035,  1.0,          Generator,    p_nom
    """)
    pd.testing.assert_frame_equal(
        lhs.sort_values(["constraint_name", "variable_name"]).reset_index(drop=True),
        expected_lhs,
    )


def test_translate_technology_capacity_targets_no_targets(csv_str_to_df):
    targets = pd.DataFrame(columns=["FY", "region_id", "policy_id", "capacity_mw"])
    generators = csv_str_to_df("""
        name,              bus,  build_year,  lifetime,  isp_technology_type
        offshore_v8_2035,  V8,   2035,        30,        Wind__-__offshore__(fixed)
    """)
    batteries = csv_str_to_df("""
        name,         bus,   build_year,  lifetime,  max_hours
        new_8h_2035,  CNSW,  2035,        20,        8.0
    """)
    bus_regions = {"V8": "VIC", "CNSW": "NSW"}

    lhs, rhs = _translate_technology_capacity_targets(
        targets, {"generators": generators, "batteries": batteries}, bus_regions, [2035]
    )

    expected_rhs = csv_str_to_df("constraint_name,  rhs,  constraint_type")
    pd.testing.assert_frame_equal(
        rhs, expected_rhs, check_dtype=False, check_index_type=False
    )
    expected_lhs = csv_str_to_df(
        "constraint_name,  variable_name,  coefficient,  component,  attribute"
    )
    pd.testing.assert_frame_equal(
        lhs, expected_lhs, check_dtype=False, check_index_type=False
    )
