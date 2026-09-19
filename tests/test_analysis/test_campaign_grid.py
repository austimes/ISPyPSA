import pytest

from analysis.hpc.campaign_grid import (
    CAP_KIND,
    PRICE_KIND,
    order_pressures,
    parse_pressure,
    split_chain_id,
    trajectories_from_plan,
)


@pytest.mark.parametrize(
    "key, label, short, kind, value",
    [
        ("c0", "A$0/t", "$0", PRICE_KIND, 0.0),
        ("c150", "A$150/t", "$150", PRICE_KIND, 150.0),
        ("c550", "A$550/t", "$550", PRICE_KIND, 550.0),
        ("cap002", "cap 0.02", ".02", CAP_KIND, 0.02),
        ("cap0005", "cap 0.005", ".005", CAP_KIND, 0.005),
        ("cap00005", "cap 0.0005", ".0005", CAP_KIND, 0.0005),
    ],
)
def test_parse_pressure(key, label, short, kind, value):
    pressure = parse_pressure(key)

    assert (pressure.key, pressure.label, pressure.short) == (key, label, short)
    assert (pressure.kind, pressure.value) == (kind, value)


def test_parse_pressure_rejects_an_unknown_key():
    with pytest.raises(ValueError, match="unrecognised pressure key"):
        parse_pressure("tax99")


def test_price_chain_carbon_price_is_its_value_and_a_cap_chain_prices_carbon_at_zero():
    assert parse_pressure("c300").carbon_price == 300.0
    assert parse_pressure("cap001").carbon_price == 0.0


def test_order_pressures_runs_prices_up_then_caps_shallow_to_deep():
    keys = [
        "cap0001",
        "c550",
        "cap002",
        "c0",
        "cap00005",
        "c150",
        "cap001",
        "c300",
        "cap0005",
        "cap0002",
    ]

    ordered = order_pressures(keys)

    assert [p.key for p in ordered] == [
        "c0",
        "c150",
        "c300",
        "c550",
        "cap002",
        "cap001",
        "cap0005",
        "cap0002",
        "cap0001",
        "cap00005",
    ]


def test_order_pressures_collapses_duplicates():
    ordered = order_pressures(["c0", "cap002", "c0", "cap002"])

    assert [p.key for p in ordered] == ["c0", "cap002"]


@pytest.mark.parametrize(
    "chain_id, trajectory, pressure",
    [
        ("ext_central_c0", "central", "c0"),
        ("ext_stress_cap00005", "stress", "cap00005"),
        ("ext_low_bracket_cap0005", "low_bracket", "cap0005"),
    ],
)
def test_split_chain_id(chain_id, trajectory, pressure):
    assert split_chain_id(chain_id) == (trajectory, pressure)


def test_trajectories_from_plan_orders_by_load_and_strips_the_scenario_prefix():
    plan = {
        "demand_paths_source_twh": {
            "iasr_stress": {"2030": 225, "2060": 585},
            "iasr_low_bracket": {"2030": 165.6, "2060": 369.84},
            "iasr_central": {"2030": 183, "2060": 431},
        }
    }

    trajectories = trajectories_from_plan(plan)

    assert [t.key for t in trajectories] == ["low_bracket", "central", "stress"]
    assert [t.label for t in trajectories] == ["Low bracket", "Central", "Stress"]
    assert trajectories[0].source_twh == {2030: 165.6, 2060: 369.84}
    assert trajectories[-1].peak_source_twh == 585
