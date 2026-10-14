from pathlib import Path

import numpy as np
import pandas as pd

from ispypsa.templater.renewable_energy_zones import (
    _template_rez_build_limits,
)


def _read_n1_rez_tables(cache_path: Path) -> dict[str, pd.DataFrame]:
    """Read the REZ resource, transmission and sub-region tables, keeping REZ N1."""
    tables = {}
    for name, id_col in [
        ("initial_resource_limits", "REZ ID"),
        ("initial_transmission_limits", "REZ ID"),
        ("renewable_energy_zones", "ID"),
    ]:
        table = pd.read_csv(cache_path / f"{name}.csv")
        tables[name] = table[table[id_col] == "N1"].copy()
    return tables


def test_renewable_energy_zone_build_limits(workbook_table_cache_test_path: Path):
    iasr_tables = _read_n1_rez_tables(workbook_table_cache_test_path)

    scenario = "Step Change"
    build_limits = _template_rez_build_limits(iasr_tables, scenario)
    assert pd.Series(build_limits.rez_id.values).equals(pd.Series(["N1"]))
    assert pd.Series(build_limits.isp_sub_region_id.values).equals(pd.Series(["NNSW"]))
    assert pd.Series(build_limits.wind_generation_total_limits_mw_high.values).equals(
        pd.Series([0.0])
    )
    assert pd.Series(build_limits.wind_generation_total_limits_mw_medium.values).equals(
        pd.Series([0.0])
    )
    assert pd.Series(
        build_limits.wind_generation_total_limits_mw_offshore_fixed.values
    ).equals(pd.Series([0.0]))
    assert pd.Series(
        build_limits.wind_generation_total_limits_mw_offshore_floating.values
    ).equals(pd.Series([0.0]))
    assert pd.Series(
        build_limits.solar_pv_plus_solar_thermal_limits_mw_solar.values
    ).equals(pd.Series([6385.0]))
    assert pd.Series(
        build_limits["rez_resource_limit_violation_penalty_factor_$/mw"].values
    ).equals(pd.Series([300000.0]))

    # Remove while not being used.
    # assert pd.Series(
    #     build_limits.rez_transmission_network_limit_peak_demand.values
    # ).equals(pd.Series([750.0, 700.0, np.nan, np.nan, np.nan, 0.0]))
    assert pd.Series(
        build_limits.rez_transmission_network_limit_summer_typical.values
    ).equals(pd.Series([171.0]))
    # Remove while not being used.
    # assert pd.Series(
    #     build_limits.rez_transmission_network_limit_winter_reference.values
    # ).equals(pd.Series([np.nan, 700.0, 3000.0, 2000.0, np.nan, 0.0]))
    assert pd.Series(build_limits.land_use_limits_mw_wind.values).equals(
        pd.Series([4755.000003804])
    )
    assert pd.Series(build_limits.land_use_limits_mw_solar.values).equals(
        pd.Series([11412.0])
    )


def test_renewable_energy_zone_build_limits_green_energy_exports(
    workbook_table_cache_test_path: Path,
):
    iasr_tables = _read_n1_rez_tables(workbook_table_cache_test_path)
    scenario = "Green Energy Exports"
    build_limits = _template_rez_build_limits(iasr_tables, scenario)
    assert pd.Series(build_limits.land_use_limits_mw_wind.values).equals(
        pd.Series([23775.001902])
    )
    assert pd.Series(build_limits.land_use_limits_mw_solar.values).equals(
        pd.Series([57060.0])
    )
