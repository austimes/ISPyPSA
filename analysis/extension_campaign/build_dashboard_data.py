"""Collect solved extension-campaign chains into one JSON blob for the dashboard.

Scans the campaign's run records and solved networks and writes a single file the
dashboard page loads. Chains still solving are reported with the milestones they have
finished so the dashboard is useful while the grid is still running.

Usage:
    uv run python analysis/extension_campaign/build_dashboard_data.py \\
        --output-root outputs --out outputs/campaign/dashboard_data.json
"""

import argparse
import json
from pathlib import Path

import pandas as pd
import pypsa

SLACK_BUS = "bus_for_custom_constraint_gens"
_STORAGE_CARRIERS = ("Battery", "Water")


def _carrier_energy_twh(network: pypsa.Network) -> dict[str, float]:
    """Annual sent-out energy by carrier, snapshot-weighted."""
    weights = network.snapshot_weightings["generators"]
    energy = network.generators_t.p.clip(lower=0).mul(weights, axis=0).sum()
    by_carrier = energy.groupby(network.generators.carrier).sum() / 1e6
    return {str(k): round(float(v), 4) for k, v in by_carrier.items() if v > 1e-6}


def _carrier_capacity_gw(network: pypsa.Network) -> dict[str, float]:
    """Installed generator capacity by carrier, excluding the slack bus."""
    real = network.generators[network.generators["bus"] != SLACK_BUS]
    by_carrier = real.groupby("carrier")["p_nom_opt"].sum() / 1e3
    return {str(k): round(float(v), 4) for k, v in by_carrier.items() if v > 1e-3}


def _storage_gw_and_gwh(network: pypsa.Network) -> dict[str, float]:
    """Storage power and energy, split by carrier, plus the longest duration built."""
    units = network.storage_units
    if units.empty:
        return {}
    built = units[units["p_nom_opt"] > 1.0]
    out = {}
    for carrier in _STORAGE_CARRIERS:
        rows = built[built["carrier"] == carrier]
        out[f"{carrier}_gw"] = round(float(rows["p_nom_opt"].sum()) / 1e3, 4)
        out[f"{carrier}_gwh"] = round(
            float((rows["p_nom_opt"] * rows["max_hours"]).sum()) / 1e3, 4
        )
    out["longest_duration_h"] = round(float(built["max_hours"].max()), 1)
    return out


def _unserved_twh(network: pypsa.Network) -> float:
    """Load shed, which marks a cell as a feasibility boundary rather than a menu member."""
    weights = network.snapshot_weightings["generators"]
    slack = network.generators.index[network.generators["carrier"] == "Unserved Energy"]
    present = slack.intersection(network.generators_t.p.columns)
    return round(
        float(network.generators_t.p[present].mul(weights, axis=0).sum().sum()) / 1e6, 6
    )


def _cap_dual(run_dir: Path) -> float | None:
    """Implied carbon price in AUD per tonne, from the emissions cap's shadow price."""
    duals = run_dir / "outputs" / "constraint_duals.json"
    if not duals.exists():
        return None
    value = json.loads(duals.read_text()).get("co2_cap_annual_t_dual")
    return None if value is None else round(-float(value), 2)


def _milestone(record_path: Path, runs: Path, archetype: str) -> dict | None:
    """One solved milestone, or None when its network was never written."""
    record = json.loads(record_path.read_text())
    run_dir = runs / f"{record_path.stem}__{archetype}"
    network_path = run_dir / "outputs" / "capacity_expansion.nc"
    if not network_path.exists():
        return None
    network = pypsa.Network(network_path)
    weights = network.snapshot_weightings["generators"]
    delivered = float(network.loads_t.p_set.sum(axis=1).mul(weights).sum()) / 1e6
    cap = record.get("co2_cap_annual_t")
    realised = record.get("annual_residual_co2e_t")
    return {
        "year": int(record_path.stem.rsplit("_", 1)[1]),
        "status": record.get("status"),
        "model_status": record.get("model_status"),
        "objective_aud": record.get("objective_value"),
        "wall_minutes": round(record.get("wall_clock_s", 0) / 60, 1),
        "delivered_twh": round(delivered, 3),
        "cap_t": cap,
        "realised_co2e_t": realised,
        "cap_tracking_pct": None if not cap else round(100 * (realised - cap) / cap, 4),
        "intensity_t_per_mwh": None
        if not delivered
        else round(realised / (delivered * 1e6), 6),
        "implied_carbon_price_aud_per_t": _cap_dual(run_dir),
        "unserved_twh": _unserved_twh(network),
        "energy_twh": _carrier_energy_twh(network),
        "capacity_gw": _carrier_capacity_gw(network),
        "storage": _storage_gw_and_gwh(network),
        "host": record.get("host"),
        "threads": record.get("threads"),
    }


def collect_chains(output_root: Path, archetype: str = "cost_optimal") -> list[dict]:
    """Every campaign chain found under the output root, with its solved milestones."""
    records, runs = output_root / "records", output_root / "runs"
    chains = []
    for chain_record in sorted(records.glob("ext_*.json")):
        if chain_record.stem[-4:].isdigit():
            continue  # a per-milestone record; collected under its chain below
        summary = json.loads(chain_record.read_text())
        milestones = [
            m
            for p in sorted(records.glob(f"{chain_record.stem}_20??.json"))
            if (m := _milestone(p, runs, archetype)) is not None
        ]
        chains.append(
            {
                "run_id": chain_record.stem,
                "trajectory": summary.get("trajectory"),
                "carbon_price": summary.get("carbon_price"),
                "cap_schedule": summary.get("co2_cap_t_schedule"),
                "chain_hours": round(
                    summary.get("cumulative_wall_clock_s", 0) / 3600, 2
                ),
                "milestones": milestones,
            }
        )
    return chains


def _trajectory_from_run_id(run_id: str) -> str:
    """Chains are named ext_<trajectory>_<pressure>, with the trajectory possibly hyphenated."""
    return run_id.removeprefix("ext_").rsplit("_", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=Path("outputs"))
    parser.add_argument(
        "--out", type=Path, default=Path("outputs/campaign/dashboard_data.json")
    )
    parser.add_argument("--archetype", default="cost_optimal")
    args = parser.parse_args()

    chains = collect_chains(args.output_root, args.archetype)
    for chain in chains:
        chain["trajectory"] = chain["trajectory"] or _trajectory_from_run_id(
            chain["run_id"]
        )
    solved = sum(len(c["milestones"]) for c in chains)
    blob = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "chains_found": len(chains),
        "milestones_solved": solved,
        "chains": chains,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(blob, indent=1))
    print(f"{len(chains)} chains, {solved} solved milestones -> {args.out}")


if __name__ == "__main__":
    main()
