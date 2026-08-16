import pandas as pd
import pypsa
import pytest

from ispypsa.pypsa_build.ccs_supply_curve import _add_ccs_supply_curve

# 100 MW served all year captures 100 * 8760 * 0.4 = 350,400 t = 350.4 kt.
_LOAD_MW = 100.0
_CAPTURED_T_PER_MWH = 0.4
_ANNUAL_CAPTURED_KT = 350.4
_CCS_MARGINAL_COST = 50.0
# Dearer than CCS, so the LP only reaches for it when injectivity runs out.
_BACKUP_MARGINAL_COST = 500.0
_ANNUAL_HOURS = 8760.0


def _build_ccs_network(periods=(2050,), years=1, buses=("SNW",)):
    """Minimal solvable network: one CCS generator and one uncapturing backup per
    bus, four snapshots per period each weighted to a quarter of the year."""
    snapshots = pd.MultiIndex.from_tuples(
        [
            (period, timestamp)
            for period in periods
            for timestamp in pd.date_range(f"{period}-01-01", periods=4, freq="h")
        ],
        names=["period", "timestep"],
    )
    network = pypsa.Network(snapshots=snapshots, investment_periods=list(periods))
    network.snapshot_weightings = pd.DataFrame(
        {"objective": 8760 / 4, "generators": 8760 / 4, "stores": 1.0}, index=snapshots
    )
    network.investment_period_weightings = pd.DataFrame(
        {"objective": [float(years)] * len(periods), "years": [years] * len(periods)},
        index=pd.Index(list(periods), name="period"),
    )
    network.add("Carrier", "Gas")
    for bus in buses:
        network.add("Bus", bus)
        network.add("Load", f"load_{bus}", bus=bus, p_set=_LOAD_MW)
        network.add(
            "Generator",
            f"ccs_{bus}",
            bus=bus,
            carrier="Gas",
            p_nom=200.0,
            marginal_cost=_CCS_MARGINAL_COST,
        )
        network.add(
            "Generator",
            f"backup_{bus}",
            bus=bus,
            carrier="Gas",
            p_nom=200.0,
            marginal_cost=_BACKUP_MARGINAL_COST,
        )
    return network


def _generators_table(buses=("SNW",), captured=_CAPTURED_T_PER_MWH):
    rows = []
    for bus in buses:
        rows.append(
            {
                "name": f"ccs_{bus}",
                "bus": bus,
                "isp_captured_co2_t_per_mwh": captured,
            }
        )
        rows.append(
            {"name": f"backup_{bus}", "bus": bus, "isp_captured_co2_t_per_mwh": 0.0}
        )
    return pd.DataFrame(rows)


def _transport_adders(assignment=(("SNW", "carbonnet"),)):
    return pd.DataFrame(
        [
            {"isp_sub_region_id": bus, "sink": sink, "transport_$/t": 10.0}
            for bus, sink in assignment
        ]
    )


def _tranches(periods, cap_kt_by_sink, storage_cost=18.5):
    return pd.DataFrame(
        [
            {
                "investment_period": period,
                "sink": sink,
                "cap_kt": cap_kt,
                "storage_$/t": storage_cost,
            }
            for period in periods
            for sink, cap_kt in cap_kt_by_sink.items()
        ]
    )


def _solve_with_curve(network, tranches, generators, adders):
    network.optimize.create_model(multi_investment_periods=True)
    _add_ccs_supply_curve(network, tranches, adders, generators)
    network.optimize.solve_model(solver_name="highs")


def _annual_mwh(network, generator, period):
    dispatch = network.generators_t.p[generator]
    weights = network.snapshot_weightings["generators"]
    in_period = network.snapshots.get_level_values(0) == period
    return float((dispatch * weights)[in_period].sum())


def _purchase_kt(network, sink, period):
    return float(
        network.model.variables[f"ccs_injection_purchases_kt_{sink}_{period}"].solution
    )


def test_tranche_meters_captured_co2_and_binds_generation():
    """A cap of 200 kt lets through exactly 200/0.4 = 500,000 MWh of CCS energy."""
    network = _build_ccs_network()
    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 200.0}),
        _generators_table(),
        _transport_adders(),
    )

    assert _purchase_kt(network, "carbonnet", 2050) == pytest.approx(200.0, rel=1e-6)
    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(500_000.0, rel=1e-6)
    # The rest of the 876,000 MWh of load falls to the uncapturing backup.
    assert _annual_mwh(network, "backup_SNW", 2050) == pytest.approx(
        376_000.0, rel=1e-6
    )


def test_cap_is_annual_and_not_multiplied_by_period_span():
    """The cap is annual against an annual quantity, so a 5-year period span must
    not loosen it. PyPSA multiplies weightings by `years` only for GlobalConstraint
    operational limits; this curve builds its constraint at the linopy level from
    raw snapshot weightings, so applying `years` here would make every cap 5x too
    loose."""
    one_year = _build_ccs_network(years=1)
    _solve_with_curve(
        one_year,
        _tranches([2050], {"carbonnet": 200.0}),
        _generators_table(),
        _transport_adders(),
    )

    five_year = _build_ccs_network(years=5)
    _solve_with_curve(
        five_year,
        _tranches([2050], {"carbonnet": 200.0}),
        _generators_table(),
        _transport_adders(),
    )

    assert _annual_mwh(five_year, "ccs_SNW", 2050) == pytest.approx(
        _annual_mwh(one_year, "ccs_SNW", 2050), rel=1e-6
    )
    assert _annual_mwh(five_year, "ccs_SNW", 2050) == pytest.approx(
        500_000.0, rel=1e-6
    )


def test_zero_cap_forces_captured_co2_and_ccs_generation_to_zero():
    """The conservative variant. Every cap zero means no injection is available,
    so the capturing fleet cannot run at all and the backup carries the load."""
    network = _build_ccs_network()
    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 0.0}),
        _generators_table(),
        _transport_adders(),
    )

    assert _purchase_kt(network, "carbonnet", 2050) == pytest.approx(0.0, abs=1e-6)
    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(0.0, abs=1e-3)
    assert _annual_mwh(network, "backup_SNW", 2050) == pytest.approx(
        _LOAD_MW * _ANNUAL_HOURS, rel=1e-6
    )


def test_uncapped_demand_below_the_cap_does_not_bind():
    """Headroom leaves the fleet alone: the purchase settles at actual capture."""
    network = _build_ccs_network()
    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 1_000.0}),
        _generators_table(),
        _transport_adders(),
    )

    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(
        _LOAD_MW * _ANNUAL_HOURS, rel=1e-6
    )
    assert _purchase_kt(network, "carbonnet", 2050) == pytest.approx(
        _ANNUAL_CAPTURED_KT, rel=1e-6
    )


def test_generators_are_metered_at_their_own_capture_intensity():
    """The general form, pinned so per-plant capture rates cannot silently break it.
    Today every CCS unit shares one intensity, which makes an Mt cap exactly a TWh
    cap; the constraint must not rely on that. Two units at one sink with different
    intensities must each be metered at their own rate, so the cheaper-to-dispose
    unit delivers more energy per tonne injected."""
    network = _build_ccs_network()
    network.add(
        "Generator",
        "ccs_half_SNW",
        bus="SNW",
        carrier="Gas",
        p_nom=200.0,
        marginal_cost=_CCS_MARGINAL_COST - 1.0,
    )
    generators = pd.concat(
        [
            _generators_table(),
            pd.DataFrame(
                [
                    {
                        "name": "ccs_half_SNW",
                        "bus": "SNW",
                        "isp_captured_co2_t_per_mwh": 0.2,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 100.0}),
        generators,
        _transport_adders(),
    )

    # The 0.2 t/MWh unit is cheapest, so it takes the whole 100 kt allowance and
    # converts it at its own intensity: 100,000 / 0.2 = 500,000 MWh.
    assert _annual_mwh(network, "ccs_half_SNW", 2050) == pytest.approx(
        500_000.0, rel=1e-6
    )
    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(0.0, abs=1e-3)
    assert _purchase_kt(network, "carbonnet", 2050) == pytest.approx(100.0, rel=1e-6)


def test_each_sink_is_constrained_independently():
    """Injectivity is per reservoir, so slack at one sink cannot relieve another."""
    network = _build_ccs_network(buses=("SNW", "SQ"))
    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 100.0, "cooper_hub": 1_000.0}),
        _generators_table(buses=("SNW", "SQ")),
        _transport_adders((("SNW", "carbonnet"), ("SQ", "cooper_hub"))),
    )

    # SNW is squeezed to 100/0.4 = 250,000 MWh; SQ has headroom and runs flat out.
    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(250_000.0, rel=1e-6)
    assert _annual_mwh(network, "ccs_SQ", 2050) == pytest.approx(
        _LOAD_MW * _ANNUAL_HOURS, rel=1e-6
    )


def test_storage_cost_can_price_capturing_generation_out():
    """Storage enters the objective at the tranche, so a dear enough sink makes the
    uncapturing backup cheaper despite having injectivity headroom."""
    network = _build_ccs_network()
    # 0.4 t/MWh at $2,000/t adds $800/MWh, well past the $500/MWh backup.
    _solve_with_curve(
        network,
        _tranches([2050], {"carbonnet": 1_000.0}, storage_cost=2_000.0),
        _generators_table(),
        _transport_adders(),
    )

    assert _annual_mwh(network, "ccs_SNW", 2050) == pytest.approx(0.0, abs=1e-3)
    assert _annual_mwh(network, "backup_SNW", 2050) == pytest.approx(
        _LOAD_MW * _ANNUAL_HOURS, rel=1e-6
    )


def test_no_capturing_generators_logs_and_adds_nothing(caplog):
    network = _build_ccs_network()
    generators = _generators_table()
    generators["isp_captured_co2_t_per_mwh"] = 0.0
    network.optimize.create_model(multi_investment_periods=True)

    with caplog.at_level("WARNING"):
        _add_ccs_supply_curve(
            network,
            _tranches([2050], {"carbonnet": 100.0}),
            _transport_adders(),
            generators,
        )

    assert (
        "CCS supply curve configured but the network has no CO2-capturing "
        "generators, so no CCS supply curve constraints were added."
    ) in caplog.text
    assert "ccs_injection_purchases_kt_carbonnet_2050" not in network.model.variables
