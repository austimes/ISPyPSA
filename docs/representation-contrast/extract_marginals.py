"""Extract system totals and two-run marginal quantities from solved ISPyPSA runs.

Read-only. Writes a single JSON of totals per run plus the differenced marginal
quantities, which the explainer reads. Nothing is inferred or plugged: every
marginal number here is (arm_B_total - arm_A_total) / (arm_B_demand - arm_A_demand),
and both totals are carried through to the output so the difference can be audited.

Emissions use the pipeline's own per-generator Scope 1 factor
(`isp_residual_co2_t_per_mwh`, post-capture for CCS units), which is the NGER
combined CO2e factor times the generator's heat rate.
"""

import json
import logging
import sys
import warnings
from pathlib import Path

import pandas as pd
import pypsa

warnings.filterwarnings("ignore")
logging.disable(logging.INFO)

RUNS = Path("analysis/benchmarks/runs_myopic")


def _weighted_generation_mwh(network):
    """Per-generator annual MWh, snapshot weightings applied (rep weeks -> year)."""
    weights = network.snapshot_weightings["generators"]
    return network.generators_t.p.mul(weights, axis=0).sum()


def _served_demand_mwh(network):
    weights = network.snapshot_weightings["generators"]
    return float(network.loads_t.p.mul(weights, axis=0).sum().sum())


def _co2_factor_by_generator(run_dir):
    gens = pd.read_csv(run_dir / "pypsa_friendly" / "generators.csv")
    return gens.set_index("name")["isp_residual_co2_t_per_mwh"].fillna(0.0)


def _load_weighted_price(network):
    """Demand-weighted mean of the nodal energy-balance dual: AUD per MWh served."""
    weights = network.snapshot_weightings["generators"]
    load_bus = network.loads["bus"]
    load_p = network.loads_t.p
    prices = network.buses_t.marginal_price[load_bus.values]
    prices.columns = load_p.columns
    numerator = (load_p * prices).mul(weights, axis=0).sum().sum()
    denominator = load_p.mul(weights, axis=0).sum().sum()
    return float(numerator / denominator)


def _unserved_energy_mwh(network, generation):
    unserved = network.generators.index[network.generators["carrier"] == "Unserved Energy"]
    return float(generation.reindex(unserved).fillna(0.0).sum())


def summarise(run_id):
    run_dir = RUNS / f"{run_id}__cost_optimal"
    network = pypsa.Network(run_dir / "outputs" / "capacity_expansion.nc")

    generation = _weighted_generation_mwh(network)
    co2_factor = _co2_factor_by_generator(run_dir).reindex(generation.index).fillna(0.0)
    carriers = network.generators["carrier"]

    by_carrier = generation.groupby(carriers).sum()
    emissions_by_carrier = (generation * co2_factor).groupby(carriers).sum()

    return {
        "run_id": run_id,
        "objective_aud": float(network.objective),
        "served_demand_mwh": _served_demand_mwh(network),
        "total_generation_mwh": float(generation.sum()),
        "unserved_energy_mwh": _unserved_energy_mwh(network, generation),
        "emissions_t_co2e": float((generation * co2_factor).sum()),
        "load_weighted_price_aud_per_mwh": _load_weighted_price(network),
        "generation_mwh_by_carrier": {k: float(v) for k, v in by_carrier.items()},
        "emissions_t_by_carrier": {k: float(v) for k, v in emissions_by_carrier.items()},
        "capacity_mw_by_carrier": {
            k: float(v)
            for k, v in network.generators.groupby("carrier")["p_nom_opt"].sum().items()
        },
        "storage_power_mw": float(network.storage_units["p_nom_opt"].sum()),
        "n_snapshots": int(len(network.snapshots)),
    }


def difference(base, perturbed):
    """Marginal quantities as a plain difference quotient over served demand."""
    delta_demand = perturbed["served_demand_mwh"] - base["served_demand_mwh"]
    delta_cost = perturbed["objective_aud"] - base["objective_aud"]
    delta_emissions = perturbed["emissions_t_co2e"] - base["emissions_t_co2e"]

    carriers = sorted(
        set(base["generation_mwh_by_carrier"]) | set(perturbed["generation_mwh_by_carrier"])
    )
    delta_generation = {
        c: perturbed["generation_mwh_by_carrier"].get(c, 0.0)
        - base["generation_mwh_by_carrier"].get(c, 0.0)
        for c in carriers
    }

    return {
        "base_run": base["run_id"],
        "perturbed_run": perturbed["run_id"],
        "delta_served_demand_mwh": delta_demand,
        "delta_objective_aud": delta_cost,
        "delta_emissions_t_co2e": delta_emissions,
        "marginal_cost_aud_per_mwh": delta_cost / delta_demand,
        "marginal_intensity_t_co2e_per_mwh": delta_emissions / delta_demand,
        "average_cost_aud_per_mwh": base["objective_aud"] / base["served_demand_mwh"],
        "average_intensity_t_co2e_per_mwh": base["emissions_t_co2e"] / base["served_demand_mwh"],
        "delta_generation_mwh_by_carrier": delta_generation,
        "marginal_generation_share_by_carrier": {
            c: v / delta_demand for c, v in delta_generation.items()
        },
    }


if __name__ == "__main__":
    run_ids = sys.argv[1:-1]
    out_path = Path(sys.argv[-1])
    totals = {}
    for run_id in run_ids:
        print(f"reading {run_id} ...")
        totals[run_id] = summarise(run_id)
    out_path.write_text(json.dumps({"totals": totals}, indent=2))
    print(f"wrote {out_path}")
