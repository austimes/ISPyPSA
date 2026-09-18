import pytest

from analysis.extension_campaign.build_cost_dashboard_data import build_payload

PLAN = {
    "demand_paths_source_twh": {
        "iasr_central": {"2050": 365, "2060": 431},
        "iasr_stress": {"2050": 490, "2060": 585},
        "iasr_low": {"2050": 336, "2060": 402},
    }
}


@pytest.fixture
def results(csv_str_to_df):
    """Two trajectories by two pressure settings at one milestone, one cell shedding."""
    return csv_str_to_df("""
        cell,                pressure,  trajectory,  year,  delivered_twh,  served_twh,  avg_cost_aud_per_mwh,  cost_per_mwh_excl_fuel_carbon,  diagnostic_fuel_cost_per_mwh,  diagnostic_carbon_cost_per_mwh,  total_cost_aud_per_yr,  co2e_total_t_per_mwh,  co2e_total_kt_per_yr,  renewable_fraction_pct,  share_Gas,  share_Wind,  twh_Gas,  twh_Wind,  use_mwh,    use_pct_of_demand,  boundary,  fuel_unpriced,  carried_gw,  tolerance_robust
        ext_central_c150,    c150,      central,     2050,  365.0,          365.0,       120.0,                 90.0,                           20.0,                          10.0,                            4.38e10,                0.05,                  18250.0,               80.0,                    12.0,       50.0,        44.0,     183.0,     0.0,        0.0,                False,     False,          40.0,        True
        ext_stress_c150,     c150,      stress,      2050,  490.0,          490.0,       130.0,                 100.0,                          20.0,                          10.0,                            6.37e10,                0.06,                  29400.0,               78.0,                    14.0,       48.0,        69.0,     235.0,     0.0,        0.0,                False,     False,          55.0,        True
        ext_central_cap0001, cap0001,   central,     2050,  365.0,          365.0,       150.0,                 140.0,                          10.0,                          0.0,                             5.475e10,               0.001,                 365.0,                 96.0,                    1.0,        60.0,        3.65,     219.0,     0.0,        0.0,                False,     False,          52.0,        True
        ext_stress_cap0001,  cap0001,   stress,      2050,  490.0,          485.1,       160.0,                 152.0,                          8.0,                           0.0,                             7.84e10,                0.001,                 490.0,                 97.0,                    0.8,        61.0,        3.92,     299.0,     4900000.0,  1.0,                True,      False,          70.0,        False
    """)


@pytest.fixture
def marginals(csv_str_to_df):
    return csv_str_to_df("""
        pressure,  year,  from_level,  to_level,  from_delivered_twh,  to_delivered_twh,  delta_delivered_twh,  from_total_cost_aud_per_yr,  to_total_cost_aud_per_yr,  marginal_cost_aud_per_mwh,  marginal_co2e_t_per_mwh,  marginal_thermal_pct_of_generation,  marginal_renewable_pct_of_generation
        c150,      2050,  central,     stress,    365.0,               490.0,             125.0,                4.38e10,                     6.37e10,                   159.2,                      0.089,                    22.0,                                78.0
    """)


@pytest.fixture
def storage(csv_str_to_df):
    return csv_str_to_df("""
        cell,                year,  carrier,  duration_class,  power_gw,  energy_gwh,  units
        ext_central_c150,    2050,  Battery,  2_2to4h,         10.0,      40.0,        12
        ext_central_c150,    2050,  Battery,  5_over8to24h,    4.0,       48.0,        3
        ext_central_cap0001, 2050,  Battery,  2_2to4h,         18.0,      72.0,        20
    """)


@pytest.fixture
def manifest(csv_str_to_df):
    return csv_str_to_df("""
        cell,                year,  implied_carbon_price_aud_per_t,  ipm_final_pinf,  ipm_final_dinf,  wall_clock_s,  lp_rows,   peak_rss_gib
        ext_central_c150,    2050,  150.0,                           1.5e-05,         3.8e-08,         3600.0,        13000000,  21.0
        ext_stress_c150,     2050,  150.0,                           2.0e-05,         4.0e-08,         5400.0,        14000000,  23.0
        ext_central_cap0001, 2050,  4815.9,                          5.0e-04,         9.0e-08,         7200.0,        13500000,  22.0
        ext_stress_cap0001,  2050,  9021.4,                          1.4e-02,         1.0e-07,         9000.0,        14500000,  25.0
    """)


def test_axes_carry_labels_families_and_order(results, marginals, storage, manifest):
    payload = build_payload(results, marginals, storage, manifest, PLAN)

    assert payload["meta"]["pressures"] == [
        {
            "key": "c150",
            "label": "A$150/t",
            "short": "$150",
            "kind": "price",
            "value": 150.0,
        },
        {
            "key": "cap0001",
            "label": "cap 0.001",
            "short": ".001",
            "kind": "cap",
            "value": 0.001,
        },
    ]
    assert payload["meta"]["demands"] == [
        {"key": "central", "label": "Central", "source_twh": {"2050": 365}},
        {"key": "stress", "label": "Stress", "source_twh": {"2050": 490}},
    ]
    assert payload["meta"]["years"] == [2050]
    assert payload["meta"]["chains"] == 4


def test_a_cell_carries_its_costs_mix_boundary_flag_and_implied_price(
    results, marginals, storage, manifest
):
    payload = build_payload(results, marginals, storage, manifest, PLAN)

    assert payload["cells"][0] == {
        "pressure": "c150",
        "demand": "central",
        "year": 2050,
        "delivered_twh": 365.0,
        "served_twh": 365.0,
        "avg_cost": 120.0,
        "cost_excl": 90.0,
        "cost_fuel": 20.0,
        "cost_carbon": 10.0,
        "total_cost_bn": 43.8,
        "co2e_intensity": 0.05,
        "co2e_mt": 18.25,
        "renewable_pct": 80.0,
        "thermal_pct": 12.0,
        "use_mwh": 0.0,
        "use_pct": 0.0,
        "boundary": False,
        "fuel_unpriced": False,
        "implied_carbon_price": 150.0,
        "carried_gw": 40.0,
        "mix": {
            "Wind": {"share": 50.0, "twh": 183.0},
            "Gas": {"share": 12.0, "twh": 44.0},
        },
    }


def test_the_shedding_cell_is_a_boundary_with_its_cap_shadow_price(
    results, marginals, storage, manifest
):
    payload = build_payload(results, marginals, storage, manifest, PLAN)

    shedding = next(
        c
        for c in payload["cells"]
        if c["demand"] == "stress" and c["pressure"] == "cap0001"
    )
    assert (shedding["boundary"], shedding["use_pct"], shedding["served_twh"]) == (
        True,
        1.0,
        485.1,
    )
    assert shedding["implied_carbon_price"] == 9021.4


def test_marginals_and_storage_are_keyed_on_the_two_campaign_axes(
    results, marginals, storage, manifest
):
    payload = build_payload(results, marginals, storage, manifest, PLAN)

    assert payload["marginals"] == [
        {
            "pressure": "c150",
            "year": 2050,
            "from": "central",
            "to": "stress",
            "from_twh": 365.0,
            "to_twh": 490.0,
            "d_twh": 125.0,
            "from_cost_bn": 43.8,
            "to_cost_bn": 63.7,
            "mc": 159.2,
            "mco2e": 0.089,
            "thermal_pct": 22.0,
            "renewable_pct": 78.0,
        }
    ]
    assert payload["storage"][0] == {
        "pressure": "c150",
        "demand": "central",
        "year": 2050,
        "carrier": "Battery",
        "cls": "2_2to4h",
        "gw": 10.0,
        "gwh": 40.0,
    }


def test_diagnostics_count_the_solves_the_boundaries_and_the_certifications(
    results, marginals, storage, manifest
):
    payload = build_payload(results, marginals, storage, manifest, PLAN)

    assert payload["diagnostics"]["solves"] == 4
    assert payload["diagnostics"]["chains"] == 4
    assert payload["diagnostics"]["certified"] == 3
    assert payload["diagnostics"]["boundaries"] == 1
    assert payload["diagnostics"]["fuel_unpriced"] == 0
    assert payload["diagnostics"]["wall_total_h"] == 7.0
