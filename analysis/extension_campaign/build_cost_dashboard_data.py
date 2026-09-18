"""Shape the campaign's deliverable tables into one compact JSON for the cost dashboard.

The dashboard is a single self-contained HTML file with no network access, so every
number it draws has to be inlined. This keeps the shaping in Python (where the CSVs
already live) rather than in the page.

The two axes are generalised from the demand x carbon sweep's. Its integer carbon
price becomes a `pressure` with a key, a label and a family (`price` or `cap`), and its
demand scalar becomes a demand `trajectory` positioned on the cost surface by the
milestone's delivered TWh, which differs by year. See `campaign_grid.py` for both.

Usage:
    uv run python analysis/extension_campaign/build_cost_dashboard_data.py
"""

import argparse
import json
import sys
from pathlib import Path

# Run as a script, sys.path[0] is this file's directory, so the repository root has to
# be put on the path before the `analysis` package resolves.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from analysis.benchmarks.output_layout import DEFAULT_OUTPUT_ROOT
from analysis.extension_campaign.build_deliverables import (
    BOUNDARY_USE_PCT,
    DEFAULT_PLAN,
)
from analysis.extension_campaign.campaign_grid import (
    Pressure,
    Trajectory,
    order_pressures,
    trajectories_from_plan,
)

CARRIERS = [
    "Wind",
    "Solar",
    "Gas",
    "Water",
    "Biomass",
    "Black Coal",
    "Brown Coal",
    "Liquid Fuel",
]
THERMAL_CARRIERS = ["Gas", "Black Coal", "Brown Coal", "Liquid Fuel"]


def _round(value, digits: int = 3) -> float | None:
    """Round for transport, mapping every flavour of missing to JSON null."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _mix(row: pd.Series) -> dict[str, dict]:
    """Generation by carrier for one cell, dropping the carriers it does not use."""
    mix = {}
    for carrier in CARRIERS:
        share = row.get(f"share_{carrier}")
        if share is not None and not pd.isna(share) and abs(float(share)) > 1e-9:
            mix[carrier] = {
                "share": _round(share),
                "twh": _round(row.get(f"twh_{carrier}")),
            }
    return mix


def _cell(row: pd.Series) -> dict:
    """One solved cell-year as the page reads it."""
    thermal = sum(float(row.get(f"share_{c}", 0) or 0) for c in THERMAL_CARRIERS)
    return {
        "pressure": row["pressure"],
        "demand": row["trajectory"],
        "year": int(row["year"]),
        "delivered_twh": _round(row["delivered_twh"]),
        "served_twh": _round(row["served_twh"]),
        "avg_cost": _round(row["avg_cost_aud_per_mwh"], 2),
        "cost_excl": _round(row["cost_per_mwh_excl_fuel_carbon"], 2),
        "cost_fuel": _round(row["diagnostic_fuel_cost_per_mwh"], 2),
        "cost_carbon": _round(row["diagnostic_carbon_cost_per_mwh"], 2),
        "total_cost_bn": _round(row["total_cost_aud_per_yr"] / 1e9, 3),
        "co2e_intensity": _round(row["co2e_total_t_per_mwh"], 5),
        "co2e_mt": _round(row["co2e_total_kt_per_yr"] / 1e3, 3),
        "renewable_pct": _round(row["renewable_fraction_pct"], 2),
        "thermal_pct": _round(thermal),
        "use_mwh": _round(row["use_mwh"], 1),
        "use_pct": _round(row["use_pct_of_demand"], 3),
        "boundary": bool(row["boundary"]),
        "fuel_unpriced": bool(row["fuel_unpriced"]),
        "implied_carbon_price": _round(row["implied_carbon_price_aud_per_t"], 1),
        "carried_gw": _round(row.get("carried_gw"), 2),
        "mix": _mix(row),
    }


def cells(results: pd.DataFrame, implied_prices: pd.DataFrame) -> list[dict]:
    """Every solved cell-year, with the implied carbon price joined on from the manifest."""
    joined = results.merge(implied_prices, on=["cell", "year"], how="left")
    return [_cell(row) for _, row in joined.iterrows()]


def marginals(frame: pd.DataFrame) -> list[dict]:
    """The adjacent-trajectory demand arcs, one row each."""
    return [
        {
            "pressure": row["pressure"],
            "year": int(row["year"]),
            "from": row["from_level"],
            "to": row["to_level"],
            "from_twh": _round(row["from_delivered_twh"]),
            "to_twh": _round(row["to_delivered_twh"]),
            "d_twh": _round(row["delta_delivered_twh"]),
            "from_cost_bn": _round(row["from_total_cost_aud_per_yr"] / 1e9, 3),
            "to_cost_bn": _round(row["to_total_cost_aud_per_yr"] / 1e9, 3),
            "mc": _round(row["marginal_cost_aud_per_mwh"], 2),
            "mco2e": _round(row["marginal_co2e_t_per_mwh"], 5),
            "thermal_pct": _round(row["marginal_thermal_pct_of_generation"], 2),
            "renewable_pct": _round(row["marginal_renewable_pct_of_generation"], 2),
        }
        for _, row in frame.iterrows()
    ]


def storage(frame: pd.DataFrame, chain_axes: pd.DataFrame) -> list[dict]:
    """Storage build by duration class, keyed on the two campaign axes."""
    joined = frame.merge(chain_axes, on="cell", how="left")
    grouped = (
        joined.groupby(["pressure", "trajectory", "year", "carrier", "duration_class"])
        .agg(power_gw=("power_gw", "sum"), energy_gwh=("energy_gwh", "sum"))
        .reset_index()
    )
    return [
        {
            "pressure": row["pressure"],
            "demand": row["trajectory"],
            "year": int(row["year"]),
            "carrier": row["carrier"],
            "cls": row["duration_class"],
            "gw": _round(row["power_gw"]),
            "gwh": _round(row["energy_gwh"], 1),
        }
        for _, row in grouped.iterrows()
    ]


def diagnostics(manifest: pd.DataFrame, results: pd.DataFrame) -> dict:
    """Solver summary across the campaign, for the provenance strip and tiles."""
    return {
        "solves": int(len(manifest)),
        "chains": int(manifest["cell"].nunique()),
        "certified": int(results["tolerance_robust"].sum()),
        "boundaries": int(results["boundary"].sum()),
        "fuel_unpriced": int(results["fuel_unpriced"].sum()),
        "fuel_unpriced_years": sorted(
            int(y) for y in results.loc[results["fuel_unpriced"], "year"].unique()
        ),
        "pinf_max": _round(manifest["ipm_final_pinf"].max(), 6),
        "dinf_max": _round(manifest["ipm_final_dinf"].max(), 8),
        "wall_min_min": _round(manifest["wall_clock_s"].min() / 60, 0),
        "wall_max_min": _round(manifest["wall_clock_s"].max() / 60, 0),
        "wall_mean_min": _round(manifest["wall_clock_s"].mean() / 60, 0),
        "wall_total_h": _round(manifest["wall_clock_s"].sum() / 3600, 1),
        "rows_max": int(manifest["lp_rows"].max()),
        "peak_rss_gib_max": _round(manifest["peak_rss_gib"].max(), 1),
    }


def _pressure_payload(pressure: Pressure) -> dict:
    """One pressure setting as the page's series descriptor."""
    return {
        "key": pressure.key,
        "label": pressure.label,
        "short": pressure.short,
        "kind": pressure.kind,
        "value": pressure.value,
    }


def _trajectory_payload(trajectory: Trajectory, years: list[int]) -> dict:
    """One demand trajectory, with the source load the plan authored for each milestone."""
    return {
        "key": trajectory.key,
        "label": trajectory.label,
        "source_twh": {str(year): trajectory.source_twh.get(year) for year in years},
    }


def build_payload(
    results: pd.DataFrame,
    marginals_frame: pd.DataFrame,
    storage_frame: pd.DataFrame,
    manifest: pd.DataFrame,
    plan: dict,
) -> dict:
    """The whole dashboard payload: the two axes, the cells, and the solver record."""
    years = sorted(int(y) for y in results.year.unique())
    pressures = order_pressures(list(results["pressure"]))
    trajectories = [
        t for t in trajectories_from_plan(plan) if t.key in set(results["trajectory"])
    ]
    chain_axes = results[["cell", "pressure", "trajectory"]].drop_duplicates()
    implied = manifest[["cell", "year", "implied_carbon_price_aud_per_t"]]
    return {
        "meta": {
            "pressures": [_pressure_payload(p) for p in pressures],
            "demands": [_trajectory_payload(t, years) for t in trajectories],
            "years": years,
            "carriers": CARRIERS,
            "chains": int(results.cell.nunique()),
            "boundary_use_pct": BOUNDARY_USE_PCT,
        },
        "cells": cells(results, implied),
        "marginals": marginals(marginals_frame),
        "storage": storage(storage_frame, chain_axes),
        "diagnostics": diagnostics(manifest, results),
    }


def _parse_args() -> argparse.Namespace:
    """Command line for the cost dashboard data builder."""
    parser = argparse.ArgumentParser(
        description="Shape the campaign exports for the cost dashboard."
    )
    parser.add_argument("--exports", type=Path, default=DEFAULT_OUTPUT_ROOT / "exports")
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Default <exports>/cost_dashboard_data.json",
    )
    args = parser.parse_args()
    args.out = args.out or args.exports / "cost_dashboard_data.json"
    return args


def main() -> None:
    args = _parse_args()
    payload = build_payload(
        pd.read_csv(args.exports / "results.csv"),
        pd.read_csv(args.exports / "marginals.csv"),
        pd.read_csv(args.exports / "storage.csv"),
        pd.read_csv(args.exports / "manifest.csv"),
        json.loads(args.plan.read_text(encoding="utf-8")),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {args.out}  ({args.out.stat().st_size / 1024:.1f} KiB)")
    print(
        f"  cells {len(payload['cells'])}  marginals {len(payload['marginals'])}"
        f"  storage {len(payload['storage'])}"
    )
    print(f"  diagnostics {payload['diagnostics']}")


if __name__ == "__main__":
    main()
