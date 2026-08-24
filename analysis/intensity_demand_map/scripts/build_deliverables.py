"""Assemble the intensity x demand map deliverables from solved cells.

Outputs (all under analysis/intensity_demand_map/):

  map_results.csv          one row per cell: coordinates, cost, both duals,
                           technology detail (abated/unabated gas separate),
                           realised intensity, r_total / r_VRE, capacity
  marginals_intensity.csv  chordal marginals between adjacent intensity rungs at
                           fixed (year, demand), with the cap dual comparison
  marginals_demand.csv     chordal marginals between adjacent demand levels at
                           fixed (year, intensity rung), with the demand-balance
                           dual comparison
  acceptance_per_cell.csv  zero-USE, termination, cap-tracking (realised vs cap)
  acceptance_per_grid.csv  monotonicity in both axes; dual-vs-chordal agreement
  manifest.csv             run id, trace dir, cap, solver settings, status, gap,
                           wall time, paths

Cost basis: as the previous sweep — extract_frontier_points' full-fleet
intensity (carried capex re-attributed from the CONDITIONING chain's prior
networks, since that is where the carried vintages were built), rebuilt as
(excl_fuel_carbon + fuel + carbon) x delivered. The LP objective is carried
alongside because the dual-vs-chordal check is an LP-internal identity; carried
capex is constant within a year and cancels in chordal differences.

Usage:
    uv run python analysis/intensity_demand_map/scripts/build_deliverables.py
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analysis.intensity_demand_map.scripts.extract_cell import extract_cell, run_root  # noqa: E402
from analysis.postprocess.extract_frontier_points import extract_frontier_point  # noqa: E402

OUT = Path("analysis/intensity_demand_map")
RUNS = Path("analysis/benchmarks/runs_myopic")
RECORDS = Path("analysis/benchmarks/records")
WORKBOOK_CACHE = Path("analysis/data/workbook_cache_final")
CONDITIONING = "sweep_c0_d100"
CCS_FLAT_ADDER = 89.93
PDLP_TOLERANCE = 3e-3

DEMAND_ORDER = ["d100", "d105", "d110", "d120", "d135", "d150"]
DEMAND_SCALARS = {"d100": 1.00, "d105": 1.05, "d110": 1.10,
                  "d120": 1.20, "d135": 1.35, "d150": 1.50}
CAP_ORDER = ["i005", "i010", "i025", "i050", "i100", "i150"]  # tight -> loose
CAP_MULTS = {"i005": 0.05, "i010": 0.10, "i025": 0.25,
             "i050": 0.50, "i100": 1.00, "i150": 1.50}
YEARS = [2030, 2040, 2050]
DUAL_CHORDAL_TOLERANCE = 0.25


def _parse_run_id(run_id: str) -> dict | None:
    """idm_<level>_<capkey>_<year>; capkey 'u' is the uncapped pilot cell."""
    parts = run_id.split("_")
    if len(parts) != 4 or parts[0] != "idm":
        return None
    return {"demand_level": parts[1], "cap_key": parts[2], "year": int(parts[3])}


def _solved_cells() -> list[str]:
    ids = []
    for record_path in sorted(RECORDS.glob("idm_*.json")):
        run_id = record_path.stem
        if _parse_run_id(run_id) is None:
            continue
        record = json.loads(record_path.read_text())
        if record.get("status") == "completed":
            ids.append(run_id)
    return ids


def _frontier_row(run_id: str, year: int) -> dict:
    """Cost coordinate via the committed extractor, conditioned prior networks."""
    prior_ncs = {
        y: RUNS / f"{CONDITIONING}_{y}__cost_optimal" / "outputs" / "capacity_expansion.nc"
        for y in YEARS if y < year
    }
    root = run_root(run_id)
    row, _composition = extract_frontier_point(
        run_id, year, prior_ncs,
        network_path=root / "outputs" / "capacity_expansion.nc",
        pypsa_friendly_dir=root / "pypsa_friendly",
        ispypsa_inputs_dir=root / "ispypsa_inputs",
        workbook_cache=WORKBOOK_CACHE,
        record_path=RECORDS / f"{run_id}.json",
        carbon_price=0.0, tns_price=CCS_FLAT_ADDER,
    )
    keep = {
        "cost_per_mwh_excl_fuel_carbon", "diagnostic_fuel_cost_per_mwh",
        "diagnostic_carbon_cost_per_mwh", "diagnostic_bundled_cost_per_mwh",
        "annual_generation_twh", "carried_capex_aud_per_yr",
        "existing_fleet_fom_aud_per_yr", "tolerance_robust",
    }
    return {k: row[k] for k in keep if k in row}


def build_results(run_ids: list[str]) -> pd.DataFrame:
    rows = []
    for run_id in run_ids:
        coords = _parse_run_id(run_id)
        row = {**coords, **extract_cell(run_id)}
        row.update(_frontier_row(run_id, coords["year"]))
        row["demand_scalar"] = DEMAND_SCALARS[coords["demand_level"]]
        row["cap_mult"] = CAP_MULTS.get(coords["cap_key"])
        row["avg_cost_aud_per_mwh"] = (
            row["cost_per_mwh_excl_fuel_carbon"]
            + row["diagnostic_fuel_cost_per_mwh"]
            + row["diagnostic_carbon_cost_per_mwh"]
        )
        row["total_cost_aud_per_yr"] = (
            row["avg_cost_aud_per_mwh"] * row["delivered_twh"] * 1e6
        )
        rows.append(row)
        print(f"  extracted {run_id}")
    frame = pd.DataFrame(rows)
    detail = [c for c in frame.columns if c.startswith(("twh_", "share_", "gw_"))]
    frame[detail] = frame[detail].fillna(0.0)
    return frame


def marginals_intensity(results: pd.DataFrame) -> pd.DataFrame:
    """Chordal marginal (AUD/tCO2e) between adjacent ladder rungs, vs cap duals."""
    rows = []
    capped = results[results["cap_key"].isin(CAP_ORDER)]
    for (year, level), block in capped.groupby(["year", "demand_level"]):
        block = block.set_index("cap_key").reindex(CAP_ORDER).dropna(how="all")
        keys = list(block.index)
        for tight, loose in zip(keys, keys[1:]):
            a, b = block.loc[tight], block.loc[loose]
            d_t = b["residual_co2e_t"] - a["residual_co2e_t"]
            if d_t == 0:
                continue
            chordal = -(b["total_cost_aud_per_yr"] - a["total_cost_aud_per_yr"]) / d_t
            chordal_obj = None
            if pd.notna(a.get("rec_objective_value")) and pd.notna(b.get("rec_objective_value")):
                chordal_obj = -(b["rec_objective_value"] - a["rec_objective_value"]) / d_t
            rows.append({
                "year": year, "demand_level": level,
                "tight_cell": tight, "loose_cell": loose,
                "delta_co2e_t": d_t,
                "chordal_aud_per_t": chordal,
                "chordal_objective_aud_per_t": chordal_obj,
                "dual_tight_aud_per_t": a.get("implied_carbon_price_aud_per_t"),
                "dual_loose_aud_per_t": b.get("implied_carbon_price_aud_per_t"),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    # Agreement: the chordal between two rungs should straddle (or approximate)
    # the two endpoint duals; per the brief the tight cell's dual is compared.
    frame["dual_vs_chordal_ratio"] = (
        frame["dual_tight_aud_per_t"] / frame["chordal_aud_per_t"]
    )
    frame["within_bracket"] = (
        (frame[["dual_tight_aud_per_t", "dual_loose_aud_per_t"]].min(axis=1)
         <= frame["chordal_aud_per_t"])
        & (frame["chordal_aud_per_t"]
           <= frame[["dual_tight_aud_per_t", "dual_loose_aud_per_t"]].max(axis=1))
    )
    return frame


def marginals_demand(results: pd.DataFrame) -> pd.DataFrame:
    """Chordal marginal (AUD/MWh) between adjacent demand levels, vs bus duals."""
    rows = []
    for (year, cap_key), block in results.groupby(["year", "cap_key"]):
        block = block.set_index("demand_level").reindex(DEMAND_ORDER).dropna(how="all")
        keys = list(block.index)
        for low, high in zip(keys, keys[1:]):
            a, b = block.loc[low], block.loc[high]
            d_mwh = (b["delivered_twh"] - a["delivered_twh"]) * 1e6
            if d_mwh == 0:
                continue
            chordal = (b["total_cost_aud_per_yr"] - a["total_cost_aud_per_yr"]) / d_mwh
            rows.append({
                "year": year, "cap_key": cap_key,
                "from_level": low, "to_level": high,
                "delta_delivered_twh": d_mwh / 1e6,
                "chordal_aud_per_mwh": chordal,
                "demand_dual_from": a.get("demand_marginal_aud_per_mwh"),
                "demand_dual_to": b.get("demand_marginal_aud_per_mwh"),
            })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["dual_vs_chordal_ratio_from"] = (
        frame["demand_dual_from"] / frame["chordal_aud_per_mwh"]
    )
    return frame


def acceptance(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    per_cell = []
    for _, row in results.iterrows():
        cap = row.get("rec_co2_cap_annual_t")
        binding = (
            pd.notna(cap) and row["residual_co2e_t"] >= 0.99 * cap
        )
        realised_vs_cap = row["residual_co2e_t"] / cap if pd.notna(cap) else None
        status_ok = row.get("rec_model_status") == "Optimal" or all(
            pd.notna(row.get(k)) and row.get(k) <= PDLP_TOLERANCE
            for k in ("rec_pdlp_final_gap_rel", "rec_pdlp_final_pinf_rel",
                      "rec_pdlp_final_dinf_rel")
        )
        per_cell.append({
            "run_id": row["run_id"],
            "test1_zero_use": row["use_mwh"] < 1.0,
            "use_mwh": row["use_mwh"],
            "test3_dual_finite": pd.notna(row.get("co2_cap_dual_raw"))
            if pd.notna(cap) else None,
            "test4_cap_tracking": (0.99 <= realised_vs_cap <= 1.01)
            if binding else None,
            "realised_over_cap": realised_vs_cap,
            "cap_binding": binding if pd.notna(cap) else None,
            "termination_ok": status_ok,
            "model_status": row.get("rec_model_status"),
        })

    per_grid = []
    for (year, cap_key), block in results.groupby(["year", "cap_key"]):
        block = block.set_index("demand_level").reindex(DEMAND_ORDER).dropna(how="all")
        costs = block["total_cost_aud_per_yr"]
        if len(costs) > 1:
            per_grid.append({
                "year": year, "axis": "demand", "at": cap_key,
                "test2_cost_monotone": bool((costs.diff().dropna() >= 0).all()),
            })
    for (year, level), block in results[results["cap_key"].isin(CAP_ORDER)].groupby(
        ["year", "demand_level"]
    ):
        block = block.set_index("cap_key").reindex(CAP_ORDER).dropna(how="all")
        costs = block["total_cost_aud_per_yr"]  # tight -> loose: must not increase
        if len(costs) > 1:
            per_grid.append({
                "year": year, "axis": "intensity", "at": level,
                "test2_cost_monotone": bool((costs.diff().dropna() <= 0).all()),
            })
    return pd.DataFrame(per_cell), pd.DataFrame(per_grid)


def manifest(run_ids: list[str]) -> pd.DataFrame:
    rows = []
    for run_id in run_ids:
        record = json.loads((RECORDS / f"{run_id}.json").read_text())
        coords = _parse_run_id(run_id)
        rows.append({
            "run_id": run_id, **coords,
            "trace_directory": f"traces_{coords['demand_level']}",
            "cap_t": record.get("co2_cap_annual_t"),
            "share_min": record.get("renewable_share_min"),
            "solver_options": json.dumps(record.get("solver_options")),
            "model_status": record.get("model_status"),
            "objective_value": record.get("objective_value"),
            "pdlp_gap_rel": record.get("pdlp_final_gap_rel"),
            "lp_rows": record.get("lp_rows"),
            "solve_s": record.get("solve_s"),
            "wall_clock_s": record.get("wall_clock_s"),
            "network_path": str(run_root(run_id) / "outputs" / "capacity_expansion.nc"),
            "record_path": str(RECORDS / f"{run_id}.json"),
        })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-ids", nargs="+", default=None,
                        help="Explicit cell list (default: every completed idm_*)")
    args = parser.parse_args()

    run_ids = args.run_ids if args.run_ids else _solved_cells()
    print(f"assembling {len(run_ids)} cells")
    results = build_results(run_ids)

    outputs = [
        ("map_results.csv", results),
        ("marginals_intensity.csv", marginals_intensity(results)),
        ("marginals_demand.csv", marginals_demand(results)),
        ("manifest.csv", manifest(run_ids)),
    ]
    per_cell, per_grid = acceptance(results)
    outputs += [("acceptance_per_cell.csv", per_cell),
                ("acceptance_per_grid.csv", per_grid)]
    for name, frame in outputs:
        frame.to_csv(OUT / name, index=False)
        print(f"  wrote {name}  ({len(frame)} rows)")


if __name__ == "__main__":
    main()
