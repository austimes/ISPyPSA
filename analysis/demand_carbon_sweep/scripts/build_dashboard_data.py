"""Emit the sweep's deliverable tables as one compact JSON for the dashboard.

The dashboard is a single self-contained HTML file with no network access, so every
number it draws has to be inlined. This keeps the shaping in Python (where the CSVs
already live) rather than in the page.

Usage:
    uv run python analysis/demand_carbon_sweep/scripts/build_dashboard_data.py
"""

import json
from pathlib import Path

import pandas as pd

OUT = Path("analysis/demand_carbon_sweep")
CARRIERS = ["Wind", "Solar", "Gas", "Water", "Biomass", "Black Coal", "Brown Coal", "Liquid Fuel"]
DEMAND_ORDER = ["d087", "d100", "d110", "d123"]
DEMAND_LABEL = {"d087": "0.87", "d100": "1.00", "d110": "1.10", "d123": "1.23"}
DEMAND_SCENARIO = {
    "d087": "Slower Growth",
    "d100": "Step Change",
    "d110": "interpolated",
    "d123": "Accelerated Transition",
}


def _round(value, digits=3):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def _cells(results: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in results.iterrows():
        mix = {}
        for carrier in CARRIERS:
            share = r.get(f"share_{carrier}")
            twh = r.get(f"twh_{carrier}")
            if share is not None and not pd.isna(share) and abs(float(share)) > 1e-9:
                mix[carrier] = {"share": _round(share), "twh": _round(twh)}
        thermal = sum(
            float(r.get(f"share_{c}", 0) or 0)
            for c in ["Gas", "Black Coal", "Brown Coal", "Liquid Fuel"]
        )
        rows.append(
            {
                "carbon": int(r["carbon_price"]),
                "demand": r["demand_level"],
                "year": int(r["year"]),
                "delivered_twh": _round(r["delivered_twh"]),
                "avg_cost": _round(r["avg_cost_aud_per_mwh"], 2),
                "cost_excl": _round(r["cost_per_mwh_excl_fuel_carbon"], 2),
                "cost_fuel": _round(r["diagnostic_fuel_cost_per_mwh"], 2),
                "cost_carbon": _round(r["diagnostic_carbon_cost_per_mwh"], 2),
                "total_cost_bn": _round(r["total_cost_aud_per_yr"] / 1e9, 3),
                "co2e_intensity": _round(r["co2e_total_t_per_mwh"], 5),
                "co2e_mt": _round(r["co2e_total_kt_per_yr"] / 1e3, 3),
                "renewable_pct": _round(r["renewable_fraction_pct"], 2),
                "thermal_pct": _round(thermal),
                "use_mwh": _round(r["use_mwh"], 3),
                "carried_gw": _round(r.get("carried_gw"), 2),
                "mix": mix,
            }
        )
    return rows


def _marginals(marginals: pd.DataFrame) -> list[dict]:
    return [
        {
            "carbon": int(r["carbon_price"]),
            "year": int(r["year"]),
            "from": r["from_level"],
            "to": r["to_level"],
            "from_twh": _round(r["from_delivered_twh"]),
            "to_twh": _round(r["to_delivered_twh"]),
            "d_twh": _round(r["delta_delivered_twh"]),
            "from_cost_bn": _round(r["from_total_cost_aud_per_yr"] / 1e9, 3),
            "to_cost_bn": _round(r["to_total_cost_aud_per_yr"] / 1e9, 3),
            "mc": _round(r["marginal_cost_aud_per_mwh"], 2),
            "mco2e": _round(r["marginal_co2e_t_per_mwh"], 5),
            "thermal_pct": _round(r["marginal_thermal_pct_of_generation"], 2),
            "renewable_pct": _round(r["marginal_renewable_pct_of_generation"], 2),
        }
        for _, r in marginals.iterrows()
    ]


def _storage(storage: pd.DataFrame) -> list[dict]:
    storage = storage.copy()
    storage["carbon"] = storage["cell"].str.extract(r"sweep_c(\d+)_").astype(int)
    storage["demand"] = storage["cell"].str.extract(r"_(d\d+)$")
    grouped = storage.groupby(["carbon", "demand", "year", "carrier", "duration_class"]).agg(
        power_gw=("power_gw", "sum"), energy_gwh=("energy_gwh", "sum")
    ).reset_index()
    return [
        {
            "carbon": int(r["carbon"]),
            "demand": r["demand"],
            "year": int(r["year"]),
            "carrier": r["carrier"],
            "cls": r["duration_class"],
            "gw": _round(r["power_gw"]),
            "gwh": _round(r["energy_gwh"], 1),
        }
        for _, r in grouped.iterrows()
    ]


def _diagnostics(manifest: pd.DataFrame) -> dict:
    return {
        "solves": int(len(manifest)),
        "gap_max": _round(manifest["pdlp_gap_rel"].max(), 6),
        "pinf_max": _round(manifest["pdlp_pinf_rel"].max(), 6),
        "wall_min_min": _round(manifest["wall_clock_s"].min() / 60, 0),
        "wall_max_min": _round(manifest["wall_clock_s"].max() / 60, 0),
        "wall_mean_min": _round(manifest["wall_clock_s"].mean() / 60, 0),
        "wall_total_h": _round(manifest["wall_clock_s"].sum() / 3600, 1),
        "rows_max": int(manifest["lp_rows"].max()),
        "iters_max": int(manifest["pdlp_iterations"].max()),
    }


def main() -> None:
    results = pd.read_csv(OUT / "results.csv")
    marginals = pd.read_csv(OUT / "marginals.csv")
    storage = pd.read_csv(OUT / "storage.csv")
    manifest = pd.read_csv(OUT / "manifest.csv")

    payload = {
        "meta": {
            "carbons": sorted(int(c) for c in results.carbon_price.unique()),
            "demands": DEMAND_ORDER,
            "demand_label": DEMAND_LABEL,
            "demand_scenario": DEMAND_SCENARIO,
            "years": sorted(int(y) for y in results.year.unique()),
            "carriers": CARRIERS,
            "cells": int(results.cell.nunique()),
        },
        "cells": _cells(results),
        "marginals": _marginals(marginals),
        "storage": _storage(storage),
        "diagnostics": _diagnostics(manifest),
    }

    blob = json.dumps(payload, separators=(",", ":"))
    path = OUT / "dashboard_data.json"
    path.write_text(blob)
    print(f"wrote {path}  ({path.stat().st_size / 1024:.1f} KiB)")
    print(f"  cells {len(payload['cells'])}  marginals {len(payload['marginals'])}"
          f"  storage {len(payload['storage'])}")
    print(f"  diagnostics {payload['diagnostics']}")

    # The dashboard is published as a single self-contained page with no network
    # access, so the data is inlined at the marker rather than fetched.
    template = (OUT / "dashboard_template.html").read_text(encoding="utf-8")
    marker = "/*__SWEEP_DATA__*/null"
    assert marker in template, "data marker missing from dashboard_template.html"
    rendered = OUT / "dashboard.html"
    rendered.write_text(template.replace(marker, blob), encoding="utf-8")
    print(f"wrote {rendered}  ({rendered.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
