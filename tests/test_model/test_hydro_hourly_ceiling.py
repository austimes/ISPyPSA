"""Check hydro ceilings and energy limits through the build and update interfaces."""

import pandas as pd
import pytest

from ispypsa.pypsa_build import build_pypsa_network, update_network_timeseries


@pytest.fixture
def hydro_inputs(csv_str_to_df):
    """Provide two hydro units and weighted snapshots in two financial years."""
    return {
        "snapshots": csv_str_to_df("""
            investment_periods, snapshots,            generators, objective, stores
            2025,               2024-07-31 23:30:00,   0.5,        2.0,       0.5
            2025,               2024-08-01 00:00:00,   1.5,        2.0,       0.5
            2025,               2024-12-31 23:30:00,   1000.0,     2.0,       0.5
            2025,               2025-01-01 00:00:00,   7758.0,     2.0,       0.5
            2030,               2029-07-31 23:30:00,   2.0,        3.0,       0.5
            2030,               2029-08-01 00:00:00,   6.0,        3.0,       0.5
            2030,               2029-12-31 23:30:00,   2000.0,     3.0,       0.5
            2030,               2030-01-01 00:00:00,   6752.0,     3.0,       0.5
        """),
        "investment_period_weights": csv_str_to_df("""
            period, years, objective
            2025,   5,     7.0
            2030,   10,    9.0
        """),
        "buses": csv_str_to_df("name\nbus1"),
        "generators": csv_str_to_df("""
            name,    carrier, bus,  p_nom, p_max_pu, marginal_cost
            hydro_1, Water,   bus1, 100.0, 0.85,     0.0
            hydro_2, Water,   bus1, 50.0,  0.60,     0.0
            gas,     Gas,     bus1, 100.0, 1.00,     100.0
        """),
        "custom_constraints_rhs": pd.DataFrame(),
        "custom_constraints_lhs": pd.DataFrame(),
    }


def test_default_hydro_ceiling_matches_explicit_monthly_cf(hydro_inputs, tmp_path):
    """Keep default generator data and every model constraint unchanged."""
    default = build_pypsa_network(hydro_inputs, tmp_path)
    explicit = build_pypsa_network(
        hydro_inputs, tmp_path, hydro_hourly_ceiling="monthly_cf"
    )

    pd.testing.assert_frame_equal(default.generators, explicit.generators)
    expected = pd.DataFrame(
        {"hydro_1": [0.4, 0.4, 0.3, 0.25] * 2, "hydro_2": [0.4, 0.4, 0.3, 0.25] * 2},
        index=default.snapshots,
    ).rename_axis(columns="name")
    pd.testing.assert_frame_equal(default.generators_t.p_max_pu, expected)
    assert list(default.model.constraints) == list(explicit.model.constraints)
    for name in default.model.constraints:
        assert default.model.constraints[name].data.equals(
            explicit.model.constraints[name].data
        )
    assert not any(
        name.startswith("water_monthly") for name in default.model.constraints
    )


def test_hydro_dispatch_respects_individual_energy_and_availability_limits(
    hydro_inputs, tmp_path, csv_str_to_df
):
    """Cap one unit by its monthly energy and another by its hourly availability."""
    hydro_inputs["snapshots"] = csv_str_to_df("""
        investment_periods, snapshots,           generators, objective, stores
        2025,               2024-07-01 12:00:00,  1.0,        1.0,       1.0
        2025,               2024-07-01 13:00:00,  1.0,        1.0,       1.0
    """)
    hydro_inputs["investment_period_weights"] = csv_str_to_df("""
        period, years, objective
        2025,   1,     1.0
    """)
    demand = hydro_inputs["snapshots"][["investment_periods", "snapshots"]].assign(
        p_set=[200.0, 0.0]
    )
    demand["snapshots"] = pd.to_datetime(demand["snapshots"])
    demand_dir = tmp_path / "demand_traces"
    demand_dir.mkdir()
    demand.to_parquet(demand_dir / "bus1.parquet")

    network = build_pypsa_network(
        hydro_inputs, tmp_path, hydro_hourly_ceiling="availability"
    )
    status, condition = network.optimize.solve_model(solver_name="highs")

    assert (status, condition) == ("ok", "optimal")
    expected = pd.DataFrame(
        {"hydro_1": [80.0, 0.0], "hydro_2": [30.0, 0.0], "gas": [90.0, 0.0]},
        index=network.snapshots,
    ).rename_axis(columns="name")
    pd.testing.assert_frame_equal(network.generators_t.p, expected)


def test_hydro_monthly_limits_use_calendar_months_and_generator_weights(
    hydro_inputs, tmp_path, csv_str_to_df
):
    """Use each period's sampled month hours without investment or objective weights."""
    network = build_pypsa_network(
        hydro_inputs, tmp_path, hydro_hourly_ceiling="availability"
    )

    limits = pd.DataFrame(
        {
            name: network.model.constraints[name].rhs.to_series()
            for name in network.model.constraints
            if name.startswith("water_monthly")
        }
    ).T
    expected = (
        csv_str_to_df("""
        constraint,                   hydro_1,  hydro_2
        water_monthly_energy_2025_07,  20.0,     10.0
        water_monthly_energy_2025_08,  60.0,     30.0
        water_monthly_energy_2025_12,  30000.0,  15000.0
        water_monthly_energy_2025_01,  193950.0, 96975.0
        water_monthly_energy_2030_07,  80.0,     40.0
        water_monthly_energy_2030_08,  240.0,    120.0
        water_monthly_energy_2030_12,  60000.0,  30000.0
        water_monthly_energy_2030_01,  168800.0, 84400.0
    """)
        .set_index("constraint")
        .rename_axis(index=None, columns="name")
    )
    pd.testing.assert_frame_equal(limits, expected)
    for name in limits.index:
        constraint = network.model.constraints[name]
        period, month = name.rsplit("_", 2)[1:]
        snapshots = hydro_inputs["snapshots"]
        in_month = (snapshots["investment_periods"] == int(period)) & (
            snapshots["snapshots"].dt.month == int(month)
        )
        expected_weight = snapshots.loc[in_month, "generators"].item()
        assert (constraint.coeffs == expected_weight).all()


@pytest.mark.parametrize("initial_mode", ["monthly_cf", "availability"])
@pytest.mark.parametrize("updated_mode", ["monthly_cf", "availability"])
def test_hydro_timeseries_update_matches_build(
    hydro_inputs, tmp_path, initial_mode, updated_mode
):
    """Switching modes and replacing weights gives the same hydro limits as a build."""
    network = build_pypsa_network(
        hydro_inputs, tmp_path, hydro_hourly_ceiling=initial_mode
    )
    snapshots = hydro_inputs["snapshots"].copy()
    if updated_mode == "availability":
        snapshots.loc[:, "generators"] = [1.0, 3.0, 2.0, 6.0] * 2
        snapshots.loc[:, "objective"] = [2.0, 3.0, 4.0, 5.0] * 2
        snapshots.loc[:, "stores"] = [0.25, 0.75, 0.5, 1.5] * 2
    inputs = {**hydro_inputs, "snapshots": snapshots}
    expected = build_pypsa_network(inputs, tmp_path, hydro_hourly_ceiling=updated_mode)

    update_network_timeseries(network, inputs, snapshots, tmp_path, updated_mode)

    pd.testing.assert_frame_equal(
        network.generators_t.p_max_pu, expected.generators_t.p_max_pu
    )
    if updated_mode == "availability":
        pd.testing.assert_frame_equal(network.generators, expected.generators)
    pd.testing.assert_frame_equal(
        network.snapshot_weightings, expected.snapshot_weightings
    )
    assert list(network.model.constraints) == list(expected.model.constraints)
    for name in network.model.constraints:
        assert network.model.constraints[name].data.equals(
            expected.model.constraints[name].data
        )


def test_hydro_update_with_new_snapshots_and_default_availability(
    hydro_inputs, tmp_path
):
    """Remove stale ceilings on new timestamps when no static availability is supplied."""
    hydro_inputs["generators"] = hydro_inputs["generators"].drop(columns="p_max_pu")
    network = build_pypsa_network(hydro_inputs, tmp_path)
    snapshots = hydro_inputs["snapshots"].copy()
    snapshots["snapshots"] += pd.Timedelta(days=1)
    snapshots.loc[:, "generators"] = 0.5
    inputs = {**hydro_inputs, "snapshots": snapshots}
    expected = build_pypsa_network(
        inputs, tmp_path, hydro_hourly_ceiling="availability"
    )

    update_network_timeseries(network, inputs, snapshots, tmp_path, "availability")

    pd.testing.assert_frame_equal(network.generators, expected.generators)
    pd.testing.assert_frame_equal(
        network.generators_t.p_max_pu, expected.generators_t.p_max_pu
    )
    pd.testing.assert_frame_equal(
        network.snapshot_weightings, expected.snapshot_weightings
    )
    assert list(network.model.constraints) == list(expected.model.constraints)
    for name in network.model.constraints:
        assert network.model.constraints[name].data.equals(
            expected.model.constraints[name].data
        )


def test_unsupported_hydro_ceiling_is_rejected_before_the_network_changes(
    hydro_inputs, tmp_path
):
    """A misspelt mode raises instead of silently applying no hydro limit."""
    with pytest.raises(ValueError, match="hydro_hourly_ceiling must be one of"):
        build_pypsa_network(hydro_inputs, tmp_path, hydro_hourly_ceiling="availablity")

    network = build_pypsa_network(hydro_inputs, tmp_path)
    before = network.generators_t.p_max_pu.copy()
    snapshots = hydro_inputs["snapshots"].copy()
    with pytest.raises(ValueError, match="hydro_hourly_ceiling must be one of"):
        update_network_timeseries(
            network, hydro_inputs, snapshots, tmp_path, "availablity"
        )
    pd.testing.assert_frame_equal(network.generators_t.p_max_pu, before)
