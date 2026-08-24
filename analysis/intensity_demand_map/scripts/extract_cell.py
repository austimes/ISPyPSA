"""Per-cell extraction for the intensity x demand map.

One row per solved cell, from the saved network plus its run record. This is the
map's own extraction layer — the previous sweep's committed deliverables are not
touched. Two deliberate differences from demand_carbon_sweep/build_deliverables:

1. CCS reporting fix (Stage 0.4). Generation and capacity are grouped on
   technology groups built from `isp_technology_type` (joined from the run's
   sibling pypsa_friendly/generators.csv, because the PyPSA component table
   drops isp_* metadata), so 'CCGT with CCS' reports as gas_ccs separately from
   unabated gas rather than disappearing into carrier 'Gas'.

2. Both marginals. The emissions-cap dual comes from outputs/
   constraint_duals.json (written in-process by instrumented_runner, since the
   linopy model is not persisted); the demand-balance marginal is the
   load-weighted mean of bus marginal prices from the saved network.

Renewable share is reported in the colleague's convention (r_total, r_VRE on
real grid generation: slack and unserved excluded; rooftop PV outside the
topology; storage output never in generators_t.p) alongside the previous
sweep's definition for continuity.
"""

import json
from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
RECORDS = Path("analysis/benchmarks/records")

RENEWABLE_CARRIERS = {"Wind", "Solar", "Water", "Biomass"}
VRE_CARRIERS = {"Wind", "Solar"}
SLACK_BUS = "bus_for_custom_constraint_gens"
REPORTING_FLOOR_MW = 1.0


def _tech_group(carrier: str, technology_type: str) -> str:
    """Reporting group: carrier, except gas which splits on abatement."""
    if carrier == "Gas":
        return "Gas CCS" if technology_type == "CCGT with CCS" else "Gas unabated"
    return carrier


def run_root(run_id: str) -> Path:
    return RUNS / f"{run_id}__cost_optimal"


def extract_cell(run_id: str) -> dict:
    root = run_root(run_id)
    network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")
    pf = pd.read_csv(root / "pypsa_friendly" / "generators.csv").set_index("name")
    record = json.loads((RECORDS / f"{run_id}.json").read_text())

    weights = network.snapshot_weightings["generators"]
    energy = network.generators_t.p.clip(lower=0).mul(weights, axis=0).sum()
    gens = network.generators
    delivered_mwh = float(network.loads_t.p_set.sum(axis=1).mul(weights).sum())

    real = (gens["bus"] != SLACK_BUS) & (gens["carrier"] != "Unserved Energy")
    tech = pf["isp_technology_type"].reindex(gens.index).fillna("")
    group = pd.Series(
        [_tech_group(c, t) for c, t in zip(gens["carrier"], tech)], index=gens.index
    )

    row = {"run_id": run_id, "delivered_twh": delivered_mwh / 1e6}

    energy_real = energy[real[energy.index]]
    by_group = energy_real.groupby(group.loc[energy_real.index]).sum() / 1e6
    generation_twh = float(by_group.sum())
    row["generation_twh"] = generation_twh
    for name, twh in by_group.items():
        key = name.lower().replace(" ", "_")
        row[f"twh_{key}"] = twh
        row[f"share_{key}_pct"] = twh / generation_twh * 100

    built = gens[real & (gens["p_nom_opt"] > REPORTING_FLOOR_MW)]
    for name, gw in (built.groupby(group.loc[built.index])["p_nom_opt"].sum() / 1e3).items():
        row[f"gw_{name.lower().replace(' ', '_')}"] = gw
    storage = network.storage_units
    storage_built = storage[storage["p_nom_opt"] > REPORTING_FLOOR_MW]
    for name, gw in (storage_built.groupby("carrier")["p_nom_opt"].sum() / 1e3).items():
        row[f"gw_storage_{name.lower().replace(' ', '_')}"] = gw

    renewable_twh = sum(
        by_group.get(c, 0.0) for c in RENEWABLE_CARRIERS
    )
    row["r_total_pct"] = renewable_twh / generation_twh * 100
    row["r_vre_pct"] = (
        sum(by_group.get(c, 0.0) for c in VRE_CARRIERS) / generation_twh * 100
    )
    row["use_mwh"] = float(energy[gens["carrier"] == "Unserved Energy"].sum())

    resid = pd.to_numeric(pf["isp_residual_co2_t_per_mwh"], errors="coerce").fillna(0.0)
    captured = pd.to_numeric(pf["isp_captured_co2_t_per_mwh"], errors="coerce").fillna(0.0)
    co2e_t = float((energy * resid.reindex(energy.index).fillna(0.0)).sum())
    row["residual_co2e_t"] = co2e_t
    row["captured_co2_t"] = float(
        (energy * captured.reindex(energy.index).fillna(0.0)).sum()
    )
    row["intensity_delivered_t_per_mwh"] = co2e_t / delivered_mwh
    row["intensity_generated_t_per_mwh"] = co2e_t / (generation_twh * 1e6)

    # Demand-balance marginal: load-weighted mean of bus marginal prices, AUD/MWh.
    prices = network.buses_t.marginal_price
    load = network.loads_t.p_set
    bus_of_load = network.loads["bus"]
    load_by_bus = load.T.groupby(bus_of_load).sum().T
    common = [b for b in load_by_bus.columns if b in prices.columns]
    weighted = (prices[common] * load_by_bus[common]).mul(weights, axis=0)
    row["demand_marginal_aud_per_mwh"] = float(
        weighted.sum().sum() / load_by_bus[common].mul(weights, axis=0).sum().sum()
    )

    duals_path = root / "outputs" / "constraint_duals.json"
    if duals_path.exists():
        duals = json.loads(duals_path.read_text())
        row["co2_cap_dual_raw"] = duals.get("co2_cap_annual_t_dual")
        row["objective_weight"] = duals.get("objective_weight")
        # Sign convention: for a binding <= cap in a minimisation, dObj/dRHS <= 0;
        # the implied carbon price is the magnitude.
        if row["co2_cap_dual_raw"] is not None:
            row["implied_carbon_price_aud_per_t"] = abs(row["co2_cap_dual_raw"])
        row["share_min_dual_raw"] = duals.get("renewable_share_min_dual")

    for key in (
        "co2_cap_annual_t", "renewable_share_min", "annual_residual_co2e_t",
        "model_status", "objective_value", "solve_s", "wall_clock_s",
        "lp_rows", "pdlp_final_gap_rel", "pdlp_final_pinf_rel",
        "pdlp_final_dinf_rel", "gurobi_barrier_iterations", "status",
    ):
        if key in record:
            row[f"rec_{key}"] = record[key]
    return row
