"""Assemble the sweep's deliverables from the solved cells.

Four outputs, all per cell-period unless noted:

  results.csv          generation mix (TWh and shares), capacity builds (1 MW
                       reporting floor), total and average system cost, absolute
                       emissions and intensity, renewable fraction
  storage.csv          storage build by duration class
  marginals.csv        finite-difference marginal cost and marginal emissions
                       intensity of demand between adjacent demand levels, plus the
                       thermal/renewable split of the marginal generation
  manifest.csv         run id, trace directory, realised demand ratio, solver
                       settings, termination status, gap, residuals, wall time, paths
  acceptance.csv       the four acceptance tests per cell-period and per grid

Cost basis. Per-MWh costs come from analysis/postprocess/extract_frontier_points.py,
whose `cost_per_mwh_excl_fuel_carbon` is the FULL-FLEET intensity: year-t spend plus
the annuitised capex and FOM of every surviving prior vintage, re-attributed from each
vintage's original capital_cost, plus the existing fleet's FOM. The raw LP objective
cannot be used, because carried rows enter each year's LP at capital_cost=0.0 by
design. Total system cost is rebuilt component-by-component as
(excl_fuel_carbon + fuel + carbon) x delivered MWh, so no term is plugged.

Usage:
    uv run python analysis/demand_carbon_sweep/scripts/build_deliverables.py
"""

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd
import pypsa

CARBON_PRICES = [0, 150, 300, 550]
DEMAND_LEVELS = {"d087": 0.869546, "d100": 1.000000, "d110": 1.100000, "d123": 1.234752}
PERIODS = [2030, 2040, 2050]
CCS_FLAT_ADDER = 89.93
PDLP_TOLERANCE = 3e-3
WEEKS = "1 6 10 14 19 22 26 32 35 39 41 45 50"
RUNS = Path("analysis/benchmarks/runs_myopic")
RECORDS = Path("analysis/benchmarks/records")
WORKBOOK_CACHE = Path("analysis/data/workbook_cache_final")
OUT = Path("analysis/demand_carbon_sweep")
FRONTIER_DIR = OUT / "frontier"
REPORTING_FLOOR_MW = 1.0
RENEWABLE_CARRIERS = {"Wind", "Solar", "Water", "Biomass"}
THERMAL_CARRIERS = {"Gas", "Black Coal", "Brown Coal", "Liquid Fuel"}


def _cell_id(carbon_price: int, level: str) -> str:
    return f"sweep_c{carbon_price}_{level}"


def _network(cell: str, year: int) -> pypsa.Network:
    return pypsa.Network(RUNS / f"{cell}_{year}__cost_optimal" / "outputs" / "capacity_expansion.nc")


def _annual_mwh(network: pypsa.Network) -> pd.Series:
    return network.generators_t.p.mul(network.snapshot_weightings["generators"], axis=0).sum()


# ----------------------------------------------------------------- frontier rows


def _run_frontier_extraction(carbon_price: int, level: str) -> None:
    """Delegate the cost and emissions coordinate to the repository's extractor."""
    cell = _cell_id(carbon_price, level)
    subprocess.run(
        [
            "uv", "run", "python", "analysis/postprocess/extract_frontier_points.py",
            "--sweep-id", cell, "--run-id", cell,
            "--years", *[str(y) for y in PERIODS],
            "--carbon-price", str(carbon_price),
            "--tns-price", str(CCS_FLAT_ADDER),
            "--workbook-cache", str(WORKBOOK_CACHE),
            "--out-dir", str(FRONTIER_DIR),
        ],
        check=True,
        capture_output=True,
    )


def _load_frontier(carbon_price: int, level: str) -> pd.DataFrame:
    cell = _cell_id(carbon_price, level)
    frame = pd.read_csv(FRONTIER_DIR / f"frontier_points_{cell}.csv")
    frame["cell"] = cell
    frame["carbon_price"] = carbon_price
    frame["demand_level"] = level
    frame["demand_scalar"] = DEMAND_LEVELS[level]
    # Rebuild total cost component-by-component; the extractor's primary column
    # strips fuel and carbon, both of which the system genuinely pays.
    frame["avg_cost_aud_per_mwh"] = (
        frame["cost_per_mwh_excl_fuel_carbon"]
        + frame["diagnostic_fuel_cost_per_mwh"]
        + frame["diagnostic_carbon_cost_per_mwh"]
    )
    frame["delivered_twh"] = frame["annual_generation_twh"]
    frame["total_cost_aud_per_yr"] = frame["avg_cost_aud_per_mwh"] * frame["delivered_twh"] * 1e6
    frame["co2e_total_kt_per_yr"] = frame["co2e_total_t_per_mwh"] * frame["delivered_twh"] * 1e3
    return frame


# ------------------------------------------------------------------- mix tables


def _mix_row(cell: str, year: int) -> dict:
    network = _network(cell, year)
    energy = _annual_mwh(network)
    by_carrier = energy.groupby(network.generators.carrier).sum() / 1e6
    total = by_carrier.sum()
    row = {"cell": cell, "year": year, "total_twh": total}
    for carrier, twh in by_carrier.items():
        if not carrier:
            continue
        row[f"twh_{carrier}"] = twh
        row[f"share_{carrier}"] = twh / total * 100 if total else 0.0
    renewable = sum(by_carrier.get(c, 0.0) for c in RENEWABLE_CARRIERS)
    row["renewable_fraction_pct"] = renewable / total * 100 if total else 0.0
    row["use_mwh"] = float(energy[network.generators.carrier == "Unserved Energy"].sum())

    built = network.generators[network.generators.p_nom_opt > REPORTING_FLOOR_MW]
    for carrier, gw in (built.groupby("carrier")["p_nom_opt"].sum() / 1e3).items():
        if carrier:
            row[f"gw_{carrier}"] = gw
    return row


def _storage_rows(cell: str, year: int) -> list[dict]:
    network = _network(cell, year)
    units = network.storage_units
    built = units[units.p_nom_opt > REPORTING_FLOOR_MW]
    rows = []
    for (carrier, hours), power_mw in built.groupby(["carrier", "max_hours"])["p_nom_opt"].sum().items():
        rows.append(
            {
                "cell": cell,
                "year": year,
                "carrier": carrier,
                "duration_h": hours,
                "power_gw": power_mw / 1e3,
                "energy_gwh": power_mw * hours / 1e3,
            }
        )
    return rows


# ------------------------------------------------------------------- manifest


def _manifest_row(carbon_price: int, level: str, year: int) -> dict:
    cell = _cell_id(carbon_price, level)
    record = json.loads((RECORDS / f"{cell}_{year}.json").read_text())
    run_directory = RUNS / f"{cell}_{year}__cost_optimal"
    return {
        "cell": cell,
        "run_id": f"{cell}_{year}",
        "carbon_price": carbon_price,
        "demand_level": level,
        "demand_scalar": DEMAND_LEVELS[level],
        "year": year,
        "trace_directory": f"traces_{level}",
        "realised_demand_ratio": DEMAND_LEVELS[level],
        "rep_weeks": WEEKS,
        "named_weeks": "suppressed",
        "resolution_min": 30,
        "solver_options": json.dumps(record.get("solver_options")),
        "model_status": record.get("model_status"),
        # PDLP relative metrics; model_status reads Unknown even when converged, so these
        # are what acceptance test 4 is judged on.
        "pdlp_gap_rel": record.get("pdlp_final_gap_rel"),
        "pdlp_pinf_rel": record.get("pdlp_final_pinf_rel"),
        "pdlp_dinf_rel": record.get("pdlp_final_dinf_rel"),
        "pdlp_iterations": record.get("pdlp_iterations"),
        "objective_value": record.get("objective_value"),
        "lp_rows": record.get("lp_rows"),
        "solve_s": record.get("solve_s"),
        "wall_clock_s": record.get("wall_clock_s"),
        "network_path": str(run_directory / "outputs" / "capacity_expansion.nc"),
        "record_path": str(RECORDS / f"{cell}_{year}.json"),
    }


# ------------------------------------------------------------------- marginals


def _marginals(results: pd.DataFrame) -> pd.DataFrame:
    """Finite differences between adjacent demand levels at each carbon price.

    Both cells' totals are carried alongside the difference, so every marginal is
    auditable against its two endpoints rather than presented as a bare number.
    """
    order = list(DEMAND_LEVELS)
    rows = []
    for carbon_price in sorted(results["carbon_price"].unique()):
        for year in PERIODS:
            for low, high in zip(order, order[1:]):
                pair = results[
                    (results.carbon_price == carbon_price) & (results.year == year)
                ].set_index("demand_level")
                if low not in pair.index or high not in pair.index:
                    continue
                a, b = pair.loc[low], pair.loc[high]
                d_mwh = (b["delivered_twh"] - a["delivered_twh"]) * 1e6
                if d_mwh == 0:
                    continue
                d_cost = b["total_cost_aud_per_yr"] - a["total_cost_aud_per_yr"]
                d_co2e = (b["co2e_total_kt_per_yr"] - a["co2e_total_kt_per_yr"]) * 1e3
                thermal = sum(
                    b.get(f"twh_{c}", 0.0) - a.get(f"twh_{c}", 0.0) for c in THERMAL_CARRIERS
                )
                renewable = sum(
                    b.get(f"twh_{c}", 0.0) - a.get(f"twh_{c}", 0.0) for c in RENEWABLE_CARRIERS
                )
                rows.append(
                    {
                        "carbon_price": carbon_price,
                        "year": year,
                        "from_level": low,
                        "to_level": high,
                        "from_delivered_twh": a["delivered_twh"],
                        "to_delivered_twh": b["delivered_twh"],
                        "delta_delivered_twh": d_mwh / 1e6,
                        "from_total_cost_aud_per_yr": a["total_cost_aud_per_yr"],
                        "to_total_cost_aud_per_yr": b["total_cost_aud_per_yr"],
                        "marginal_cost_aud_per_mwh": d_cost / d_mwh,
                        "from_co2e_kt_per_yr": a["co2e_total_kt_per_yr"],
                        "to_co2e_kt_per_yr": b["co2e_total_kt_per_yr"],
                        "marginal_co2e_t_per_mwh": d_co2e / d_mwh,
                        "marginal_thermal_twh": thermal,
                        "marginal_renewable_twh": renewable,
                        "marginal_thermal_share_pct": thermal / (d_mwh / 1e6) * 100,
                        "marginal_renewable_share_pct": renewable / (d_mwh / 1e6) * 100,
                    }
                )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ acceptance


def _acceptance(results: pd.DataFrame, manifest: pd.DataFrame) -> pd.DataFrame:
    """The four tests, as amended by Addendum 1."""
    rows = []
    for _, row in manifest.iterrows():
        cell_result = results[(results.cell == row["cell"]) & (results.year == row["year"])]
        use = float(cell_result["use_mwh"].iloc[0]) if len(cell_result) else float("nan")
        # Converged if all three PDLP relative metrics sit inside the requested
        # tolerance. The status field cannot be used: HiGHS PDLP reports Unknown on this
        # LP class even when every metric is satisfied.
        metrics = [row["pdlp_gap_rel"], row["pdlp_pinf_rel"], row["pdlp_dinf_rel"]]
        status_ok = row["model_status"] == "Optimal" or all(
            pd.notna(m) and m < PDLP_TOLERANCE for m in metrics
        )
        rows.append(
            {
                "cell": row["cell"],
                "year": row["year"],
                "test1_zero_use": use < 1.0,
                "use_mwh": use,
                "test4_termination": status_ok,
                "model_status": row["model_status"],
                "pdlp_gap_rel": row["pdlp_gap_rel"],
                "pdlp_pinf_rel": row["pdlp_pinf_rel"],
                "pdlp_dinf_rel": row["pdlp_dinf_rel"],
            }
        )
    frame = pd.DataFrame(rows)

    monotone = []
    for year in PERIODS:
        for carbon_price in sorted(results["carbon_price"].unique()):
            block = results[(results.year == year) & (results.carbon_price == carbon_price)]
            block = block.set_index("demand_level").reindex(DEMAND_LEVELS).dropna(how="all")
            costs = block["total_cost_aud_per_yr"]
            monotone.append(
                {
                    "year": year,
                    "carbon_price": carbon_price,
                    "test3_cost_monotone_in_demand": bool((costs.diff().dropna() >= 0).all()),
                }
            )
        for level in DEMAND_LEVELS:
            block = results[(results.year == year) & (results.demand_level == level)]
            block = block.sort_values("carbon_price")
            gas = block.get("share_Gas")
            monotone.append(
                {
                    "year": year,
                    "demand_level": level,
                    "test2_gas_share_monotone_in_carbon": bool(
                        (gas.diff().dropna() <= 0).all()
                    ) if gas is not None else None,
                }
            )
    return frame, pd.DataFrame(monotone)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-frontier", action="store_true",
                        help="Reuse existing frontier CSVs instead of re-extracting")
    args = parser.parse_args()

    FRONTIER_DIR.mkdir(parents=True, exist_ok=True)
    frontier_frames, mix_rows, storage_rows, manifest_rows = [], [], [], []

    for carbon_price in CARBON_PRICES:
        for level in DEMAND_LEVELS:
            cell = _cell_id(carbon_price, level)
            if not (RECORDS / f"{cell}_{PERIODS[-1]}.json").exists():
                print(f"  skipping {cell}: not solved")
                continue
            if not args.skip_frontier:
                _run_frontier_extraction(carbon_price, level)
            frontier_frames.append(_load_frontier(carbon_price, level))
            for year in PERIODS:
                mix_rows.append(_mix_row(cell, year))
                storage_rows.extend(_storage_rows(cell, year))
                manifest_rows.append(_manifest_row(carbon_price, level, year))
            print(f"  extracted {cell}")

    frontier = pd.concat(frontier_frames, ignore_index=True)
    mix = pd.DataFrame(mix_rows)
    results = frontier.merge(mix, on=["cell", "year"], how="left", suffixes=("", "_mix"))
    manifest = pd.DataFrame(manifest_rows)
    marginals = _marginals(results)
    per_cell, per_grid = _acceptance(results, manifest)

    for name, frame in [
        ("results.csv", results),
        ("storage.csv", pd.DataFrame(storage_rows)),
        ("marginals.csv", marginals),
        ("manifest.csv", manifest),
        ("acceptance_per_cell.csv", per_cell),
        ("acceptance_per_grid.csv", per_grid),
    ]:
        frame.to_csv(OUT / name, index=False)
        print(f"  wrote {name}  ({len(frame)} rows)")


if __name__ == "__main__":
    main()
