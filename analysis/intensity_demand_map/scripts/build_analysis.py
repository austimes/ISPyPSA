"""Post-modelling analysis for the intensity x demand map.

Produces:
  duality_check.csv    the map's cap duals cross-validated against the previous
                       sweep's carbon-price instrument: at each sweep point's
                       realised intensity, the map's dual curve is interpolated
                       (log-linearly, since the curve is exponential-convex) and
                       compared with the price that produced that intensity
  dashboard_data.json  everything the presentation dashboard inlines

The duality logic: a carbon price P applied as an instrument yields realised
intensity i(P); an intensity cap at i yields dual lambda(i). If the model is
internally coherent these are inverse views of the same marginal-abatement-cost
curve, so lambda(i(P)) ~= P. The comparison is strictly clean only where the
conditioning matches: at 2030 both the sweep chain and the map cells are
greenfield-on-ECAA, so 2030 is the validation year; 2040/2050 sweep cells carry
price-specific prior fleets while map cells carry the $0-chain fleet, so those
comparisons are indicative only and are flagged as such.

Usage:
    uv run python analysis/intensity_demand_map/scripts/build_analysis.py
"""

import json
import math
from pathlib import Path

import pandas as pd

OUT = Path("analysis/intensity_demand_map")
RECORDS = Path("analysis/benchmarks/records")

DEMAND_SCALARS = {"d100": 1.00, "d105": 1.05, "d110": 1.10,
                  "d120": 1.20, "d135": 1.35, "d150": 1.50}
CAP_MULTS = {"i005": 0.05, "i010": 0.10, "i025": 0.25,
             "i045": 0.45, "i050": 0.50, "i100": 1.00, "i150": 1.50}
TECH_GROUPS = ["wind", "solar", "water", "biomass", "gas_ccs", "gas_unabated",
               "black_coal", "brown_coal", "liquid_fuel"]
YEARS = [2030, 2040, 2050]

FLOOR_PROBES = {
    # (year, level) -> [(cap_mult_or_label, record_id)]
    (2030, "d100"): [("0.02", "idm_floor_d100_i002_2030"),
                     ("0.001", "idm_floor_d100_i0001_2030"),
                     ("500t", "idm_floor_d100_i00002_2030"),
                     ("10t", "idm_floor_d100_i000001_2030")],
    (2030, "d150"): [("0.02", "idm_floor_d150_i002_2030"),
                     ("0.001", "idm_floor_d150_i0001_2030")],
    (2040, "d100"): [("0.02", "idm_floor_d100_i002_2040"),
                     ("0.001", "idm_floor_d100_i0001_2040"),
                     ("500t", "idm_floor_d100_i00002_2040")],
    (2040, "d150"): [("0.02", "idm_floor_d150_i002_2040"),
                     ("0.001", "idm_floor_d150_i0001_2040")],
    (2050, "d100"): [("0.02", "idm_floor_d100_i002_2050"),
                     ("0.005", "idm_floor_d100_i0005_2050"),
                     ("0.001", "idm_floor_d100_i0001_2050"),
                     ("500t", "idm_floor_d100_i00002_2050")],
    (2050, "d150"): [("0.02", "idm_floor_d150_i002_2050"),
                     ("0.005", "idm_floor_d150_i0005_2050"),
                     ("0.001", "idm_floor_d150_i0001_2050")],
}


def _interp_dual_loglinear(curve: pd.DataFrame, intensity: float) -> float | None:
    """Interpolate the (intensity, dual) map curve at `intensity`, linear in
    log(dual) so the exponential convexity does not bias the estimate upward.
    Only interior points with strictly positive duals participate."""
    pts = curve[curve["dual"] > 0].sort_values("intensity")
    if pts.empty or not (pts["intensity"].min() <= intensity <= pts["intensity"].max()):
        return None
    xs, ys = pts["intensity"].to_numpy(), pts["dual"].to_numpy()
    for j in range(len(xs) - 1):
        if xs[j] <= intensity <= xs[j + 1]:
            w = (intensity - xs[j]) / (xs[j + 1] - xs[j])
            return math.exp(
                (1 - w) * math.log(ys[j]) + w * math.log(ys[j + 1])
            )
    return None


def duality_check(results: pd.DataFrame, sweep: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in YEARS:
        curve = results[
            (results.year == year)
            & (results.demand_level == "d100")
            & (results.cap_key.str.startswith("i"))
        ][["intensity_delivered_t_per_mwh", "implied_carbon_price_aud_per_t"]]
        curve.columns = ["intensity", "dual"]
        for _, point in sweep[
            (sweep.demand_level == "d100")
            & (sweep.year == year)
            & (sweep.carbon_price > 0)
        ].iterrows():
            interpolated = _interp_dual_loglinear(
                curve, point["co2e_total_t_per_mwh"]
            )
            rows.append({
                "year": year,
                "sweep_price_aud_per_t": point["carbon_price"],
                "sweep_realised_intensity": point["co2e_total_t_per_mwh"],
                "map_dual_at_that_intensity": interpolated,
                "ratio_dual_over_price": (
                    interpolated / point["carbon_price"] if interpolated else None
                ),
                "conditioning_matched": year == 2030,
            })
    return pd.DataFrame(rows)


def _tech_mix(results: pd.DataFrame, year: int, level: str) -> list[dict]:
    block = results[
        (results.year == year)
        & (results.demand_level == level)
        & (results.cap_key.str.startswith("i"))
        & (results.cap_key != "i045")
    ].sort_values("cap_mult")
    out = []
    for _, row in block.iterrows():
        entry = {"cap_key": row.cap_key, "cap_mult": row.cap_mult}
        for group in TECH_GROUPS:
            entry[group] = round(float(row.get(f"twh_{group}", 0) or 0), 3)
        out.append(entry)
    return out


def main() -> None:
    results = pd.read_csv(OUT / "map_results.csv")
    sweep = pd.read_csv("analysis/demand_carbon_sweep/results.csv")

    duality = duality_check(results, sweep)
    duality.to_csv(OUT / "duality_check.csv", index=False)
    print(duality.round(4).to_string(index=False))

    ladder = results[results.cap_key.str.startswith("i")].copy()
    payload = {
        "meta": {
            "conditioning": "sweep_c0_d100 ($0/t, Step Change)",
            "iota_planned": {2030: 0.395398, 2040: 0.181717, 2050: 0.095404},
            "solver": "Gurobi barrier crossover-on 1e-8 (1 cell PDLP 3e-3)",
        },
        "cells": ladder[[
            "run_id", "year", "demand_level", "demand_scalar", "cap_key",
            "cap_mult", "intensity_delivered_t_per_mwh",
            "implied_carbon_price_aud_per_t", "demand_marginal_aud_per_mwh",
            "avg_cost_aud_per_mwh", "total_cost_aud_per_yr", "delivered_twh",
            "r_total_pct", "r_vre_pct", "residual_co2e_t",
        ]].round(6).to_dict(orient="records"),
        "duality": duality.round(4).to_dict(orient="records"),
        "tech_mix_d100": {
            str(year): _tech_mix(results, year, "d100") for year in YEARS
        },
        "wedge": [],
        "floors": [],
    }

    for year in YEARS:
        for cap_key in ("i100", "i025", "i005"):
            i_cell = results[(results.year == year) & (results.demand_level == "d100")
                             & (results.cap_key == cap_key)]
            s_cell = results[(results.year == year) & (results.demand_level == "d100")
                             & (results.cap_key == "s" + cap_key[1:])]
            if i_cell.empty or s_cell.empty:
                continue
            i_cell, s_cell = i_cell.iloc[0], s_cell.iloc[0]
            payload["wedge"].append({
                "year": year, "cap_key": cap_key,
                "r_total": round(i_cell.r_total_pct, 2),
                "i_cost": round(i_cell.avg_cost_aud_per_mwh, 2),
                "s_cost": round(s_cell.avg_cost_aud_per_mwh, 2),
                "i_intensity": round(i_cell.intensity_delivered_t_per_mwh, 4),
                "s_intensity": round(s_cell.intensity_delivered_t_per_mwh, 4),
                "i_gas_ccs_twh": round(float(i_cell.get("twh_gas_ccs", 0) or 0), 2),
                "s_gas_ccs_twh": round(float(s_cell.get("twh_gas_ccs", 0) or 0), 2),
            })

    for (year, level), probes in FLOOR_PROBES.items():
        for label, record_id in probes:
            record = json.loads((RECORDS / f"{record_id}.json").read_text())
            report = record.get("constraint_report", {})
            payload["floors"].append({
                "year": year, "demand_level": level, "probe": label,
                "cap_t": record.get("co2_cap_annual_t"),
                "dual": round(abs(report.get("co2_cap_annual_t_dual") or 0), 1),
            })

    (OUT / "dashboard_data.json").write_text(json.dumps(payload, indent=1))
    print(f"\nwrote {OUT / 'duality_check.csv'} and {OUT / 'dashboard_data.json'}")


if __name__ == "__main__":
    main()
