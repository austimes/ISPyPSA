"""Solve a small biomass market to verify that supply limits affect paid fuel costs."""

import numpy as np
import pandas as pd
import pypsa
import pytest

from ispypsa.pypsa_build.fuel_supply_curve import _add_fuel_supply_curve


@pytest.mark.parametrize("demand_mw", [5.0, 10.0])
def test_biomass_burn_buys_limited_supply_before_uncapped_backstop(demand_mw):
    network = pypsa.Network()
    network.set_snapshots(pd.date_range("2030-01-01", periods=1, freq="h"))
    network.set_investment_periods([2030])
    network.snapshot_weightings.loc[:, :] = 8760.0
    network.add("Carrier", "Biomass")
    network.add("Bus", "grid")
    network.add(
        "Generator",
        "biomass",
        bus="grid",
        carrier="Biomass",
        p_nom=20.0,
        marginal_cost=1.0,
    )
    network.add("Load", "demand", bus="grid", p_set=demand_mw)
    network.optimize.create_model(multi_investment_periods=True)
    curve = pd.DataFrame(
        {
            "investment_period": [2030, 2030],
            "tranche": ["limited_residue", "import_backstop"],
            "cap_pj": [0.5, np.nan],
            "adder_$/gj": [0.0, 5.0],
        }
    )
    generators = pd.DataFrame(
        {
            "name": ["biomass"],
            "carrier": ["Biomass"],
            "isp_heat_rate_gj/mwh": [10.0],
        }
    )
    _add_fuel_supply_curve(network, curve, generators, "Biomass")

    status, condition = network.optimize.solve_model(solver_name="highs")

    assert (status, condition) == ("ok", "optimal")
    generation_mwh = demand_mw * 8760.0
    burn_tj = generation_mwh * 10.0 / 1000.0
    backstop_tj = max(burn_tj - 500.0, 0.0)
    purchases = network.model.variables["biomass_supply_purchases_tj_2030"].solution
    assert float(purchases.sel(biomass_tranche="limited_residue")) <= 500.0 + 1e-7
    assert float(purchases.sum()) >= burn_tj - 1e-7
    assert float(purchases.sel(biomass_tranche="import_backstop")) == pytest.approx(
        backstop_tj
    )
    assert network.objective == pytest.approx(
        generation_mwh + backstop_tj * 1000.0 * 5.0
    )
