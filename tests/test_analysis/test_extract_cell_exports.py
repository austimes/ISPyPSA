"""Tests for the curtailment and biomass exports on the intensity x demand map.

Both quantities are derived, not read off the network: curtailment needs the
switchable `p_max_pu` (static or trace) reconstructed against `p_nom_opt`, and
biomass burn needs the heat rate from the run's sibling pypsa_friendly table,
which the PyPSA component table drops.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pypsa
import pytest

from analysis.intensity_demand_map.scripts import extract_cell as module

_PF_COLUMNS = (
    "name,isp_technology_type,isp_heat_rate_gj/mwh,"
    "isp_residual_co2_t_per_mwh,isp_captured_co2_t_per_mwh\n"
    "wind_cwo_2030,Wind,0.0,0.0,0.0\n"
    "biomass_nq_2030,Biomass,12.0,0.0,0.0\n"
)


def _solved_network() -> pypsa.Network:
    """One bus, two snapshots, a curtailed wind farm and a biomass unit."""
    n = pypsa.Network()
    n.set_snapshots(pd.date_range("2030-01-01", periods=2, freq="h"))
    n.add("Bus", "node")
    n.add("Load", "load", bus="node", p_set=[100.0, 100.0])
    n.add(
        "Generator",
        "wind_cwo_2030",
        bus="node",
        carrier="Wind",
        p_nom=200.0,
        p_max_pu=[0.5, 0.25],
    )
    n.add("Generator", "biomass_nq_2030", bus="node", carrier="Biomass", p_nom=50.0)
    n.generators["p_nom_opt"] = [200.0, 50.0]
    n.generators_t.p = pd.DataFrame(
        {"wind_cwo_2030": [80.0, 40.0], "biomass_nq_2030": [20.0, 60.0]},
        index=n.snapshots,
    )
    n.buses_t.marginal_price = pd.DataFrame({"node": [50.0, 60.0]}, index=n.snapshots)
    return n


@pytest.fixture
def cell_run(tmp_path, monkeypatch) -> str:
    """Stage one solved cell in the layout `extract_cell` reads, return its run id."""
    run_id = "sweep_c150_d100_2030"
    root = tmp_path / "runs" / f"{run_id}__cost_optimal"
    (root / "outputs").mkdir(parents=True)
    (root / "pypsa_friendly").mkdir()
    _solved_network().export_to_netcdf(root / "outputs" / "capacity_expansion.nc")
    (root / "pypsa_friendly" / "generators.csv").write_text(_PF_COLUMNS)
    records = tmp_path / "records"
    records.mkdir()
    (records / f"{run_id}.json").write_text(json.dumps({"model_status": "optimal"}))
    monkeypatch.setattr(module, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(module, "RECORDS", records)
    return run_id


def test_curtailment_and_biomass_exports(cell_run):
    """Wind availability is 100 then 50 MW against 80 and 40 MW dispatched, so
    30 MWh is curtailed out of 150 MWh available. Biomass burns 80 MWh at
    12 GJ/MWh."""
    row = module.extract_cell(cell_run)

    assert row["curtailment_mwh"] == pytest.approx(30.0)
    assert row["curtailment_pct_of_available"] == pytest.approx(20.0)
    assert row["biomass_burn_pj"] == pytest.approx(960.0 / 1e6)
    # 960 GJ x 1.8 kg CO2e/GJ / 1000 = 1.728 t. The factor is the CH4 + N2O
    # combustion residual; biogenic CO2 is zero-rated under NGER.
    assert row["biomass_co2e_t"] == pytest.approx(1.728)


def test_biomass_factor_is_the_nger_non_co2_residual():
    """The exported CO2e term must track the NGER cross-walk, not a local copy."""
    assert module.BIOMASS_CO2E_KG_PER_GJ == pytest.approx(1.8)


def test_vre_curtailment_ignores_non_vre_carriers():
    """Biomass is dispatchable, so its headroom below p_nom is not curtailment."""
    n = _solved_network()

    curtailed_mwh, delivered_mwh = module._vre_curtailment(n)

    assert curtailed_mwh == pytest.approx(30.0)
    assert delivered_mwh == pytest.approx(120.0)


def test_biomass_burn_uses_pypsa_friendly_heat_rate(tmp_path: Path):
    """Heat rate comes from the sibling pypsa_friendly table, because the PyPSA
    component table drops the isp_* metadata: 80 MWh x 12 GJ/MWh = 960 GJ."""
    pf_path = tmp_path / "generators.csv"
    pf_path.write_text(_PF_COLUMNS)
    pf = pd.read_csv(pf_path).set_index("name")

    burn_gj = module._biomass_burn_gj(_solved_network(), pf)

    assert burn_gj == pytest.approx(960.0)
