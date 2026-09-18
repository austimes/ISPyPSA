"""Assemble the extension campaign's deliverables from the solved chains.

Same six tables as the demand x carbon sweep, over the campaign's grid of five demand
trajectories by ten pressure settings, at the milestones 2030/2040/2050/2060:

  results.csv          generation mix (TWh and shares), capacity builds (1 MW
                       reporting floor), total and average system cost, absolute
                       emissions and intensity, renewable fraction, load shedding
  storage.csv          storage build by duration class
  marginals.csv        finite-difference marginal cost and marginal emissions
                       intensity of demand between adjacent trajectories, plus the
                       thermal/renewable split of the marginal generation
  manifest.csv         run id, pressure setting, cap tonnage and shadow price, solver
                       settings, termination status, residuals, wall time, paths
  acceptance_*.csv     the campaign's acceptance tests, per cell-period and per grid

Two rules the sweep did not need.

  Load shedding. Deep caps can leave demand unserved at the A$10,000/MWh emergency
  price. A cell shedding more than `BOUNDARY_USE_PCT` of its demand is a BOUNDARY: it
  marks where the pressure setting stops being feasible on this fleet, so it is
  reported but never treated as a menu member, and it is dropped before the marginals
  are differenced. The unserved-energy generators carry no capital cost and are
  excluded from dispatch, marginal cost and capex everywhere in the post-processor, so
  the A$10,000/MWh penalty never enters a cost column.

  Implied carbon price. A cap chain prices carbon at zero and exerts its pressure
  through the constraint, so its price signal is the cap's shadow price, read from the
  solve's constraint_duals.json and negated. A price chain's implied price is the
  price it was run at.

Cost basis is the sweep's: per-MWh costs come from
analysis/postprocess/extract_frontier_points.py, whose `cost_per_mwh_excl_fuel_carbon`
is the full-fleet intensity, and total system cost is rebuilt component-by-component
as (excl_fuel_carbon + fuel + carbon) x delivered MWh so no term is plugged.

The extract stage is one chain per process so the 41 chains can run concurrently; the
assemble stage reads the per-chain CSVs back and needs no networks.

Usage:
    uv run isp deliverables --only ext_low_c0 --stage extract
    uv run isp deliverables --stage assemble
"""

import json
from pathlib import Path
from typing import Literal

import pandas as pd

from analysis.benchmarks.output_layout import DEFAULT_OUTPUT_ROOT, OutputLayout
from analysis.demand_carbon_sweep.scripts.build_deliverables import (
    _marginals,
    _mix_row,
    _storage_rows,
)
from analysis.extension_campaign.campaign_grid import (
    CAP_KIND,
    Pressure,
    Trajectory,
    order_pressures,
    parse_pressure,
    split_chain_id,
    trajectories_from_plan,
)
from analysis.postprocess.extract_frontier_points import extract_chain

DEFAULT_PLAN = Path("analysis/extension_campaign/next-sweep-demand-plan.json")
DEFAULT_WORKBOOK_CACHE = Path("analysis/data/workbook_cache_final")
ARCHETYPE = "cost_optimal"
# Flat transport-and-storage adder on captured CO2, common to every chain.
TNS_PRICE_AUD_PER_TCO2 = 89.93
# Above this share of demand left unserved, a cell is a boundary rather than a menu
# member. A tenth of a percent is far above the rounding noise of a converged solve
# and far below any shedding that would change the reported mix.
BOUNDARY_USE_PCT = 0.1
# Shed energy is not a generation technology; leaving it in the mix would show up as a
# carrier share and contaminate the renewable fraction of every deep-cap cell.
EXCLUDED_MIX_CARRIERS = frozenset({"Unserved Energy"})
# Carriers that burn a priced fuel, used to detect a milestone the IASR price tables do
# not reach.
FUEL_BURNING_CARRIERS = ["Gas", "Black Coal", "Brown Coal", "Liquid Fuel", "Biomass"]
# Below this share of generation, a zero fuel cost is the honest answer rather than a
# missing price.
FUEL_BURNING_FLOOR_PCT = 0.5


# ------------------------------------------------------------------ chain products


def _solved_years(layout: OutputLayout, run_id: str, years: list[int]) -> list[int]:
    """Milestones of one chain that have both a solver record and a solved network.

    A campaign chain still in flight has its later milestones missing; those years are
    dropped rather than failing the extraction, so the deliverables can be built while
    the last chains finish.
    """
    return [
        year
        for year in years
        if layout.record(f"{run_id}_{year}").exists()
        and layout.network(f"{run_id}_{year}", ARCHETYPE).exists()
    ]


def _frontier_frame(
    run_id: str,
    pressure: Pressure,
    trajectory: str,
    years: list[int],
    layout: OutputLayout,
    workbook_cache: Path,
) -> pd.DataFrame:
    """Frontier coordinates for one chain, with the campaign's axis columns attached."""
    frame, _ = extract_chain(
        sweep_id=run_id,
        run_id=run_id,
        years=years,
        carbon_price=pressure.carbon_price,
        tns_price=TNS_PRICE_AUD_PER_TCO2,
        runs_dir=layout.runs,
        records_dir=layout.records,
        workbook_cache=workbook_cache,
        archetype=ARCHETYPE,
    )
    frame.insert(0, "cell", run_id)
    frame["pressure"] = pressure.key
    frame["trajectory"] = trajectory
    # The extractor strips fuel and carbon from its primary column; both are costs the
    # system genuinely pays, so the reported average rebuilds them.
    frame["avg_cost_aud_per_mwh"] = (
        frame["cost_per_mwh_excl_fuel_carbon"]
        + frame["diagnostic_fuel_cost_per_mwh"]
        + frame["diagnostic_carbon_cost_per_mwh"]
    )
    frame["delivered_twh"] = frame["annual_generation_twh"]
    frame["total_cost_aud_per_yr"] = (
        frame["avg_cost_aud_per_mwh"] * frame["delivered_twh"] * 1e6
    )
    frame["co2e_total_kt_per_yr"] = (
        frame["co2e_total_t_per_mwh"] * frame["delivered_twh"] * 1e3
    )
    return frame


def _cap_shadow_price(layout: OutputLayout, run_id: str, year: int) -> float | None:
    """Implied carbon price of a cap, A$/t, from the solve's constraint duals.

    The dual of a tightening cap is negative, so the price the cap implies is its
    negation. A solve with no cap constraint writes no duals file.
    """
    duals_path = (
        layout.run_dir(f"{run_id}_{year}", ARCHETYPE)
        / "outputs"
        / "constraint_duals.json"
    )
    if not duals_path.exists():
        return None
    return -json.loads(duals_path.read_text())["co2_cap_annual_t_dual"]


def _implied_carbon_price(
    layout: OutputLayout, run_id: str, year: int, pressure: Pressure
) -> float | None:
    """The price signal the cell actually faced: the cap's shadow price, or the price."""
    if pressure.kind == CAP_KIND:
        return _cap_shadow_price(layout, run_id, year)
    return pressure.value


def _manifest_row(
    run_id: str,
    pressure: Pressure,
    trajectory: Trajectory,
    year: int,
    layout: OutputLayout,
) -> dict:
    """Provenance and solver diagnostics for one solved milestone."""
    record = json.loads(layout.record(f"{run_id}_{year}").read_text())
    return {
        "cell": run_id,
        "run_id": f"{run_id}_{year}",
        "pressure": pressure.key,
        "trajectory": trajectory.key,
        "year": year,
        "source_twh": trajectory.source_twh.get(year),
        "carbon_price": pressure.carbon_price,
        "tns_price": TNS_PRICE_AUD_PER_TCO2,
        "co2_cap_annual_t": record.get("co2_cap_annual_t"),
        "annual_residual_co2e_t": record.get("annual_residual_co2e_t"),
        "implied_carbon_price_aud_per_t": _implied_carbon_price(
            layout, run_id, year, pressure
        ),
        "solver_options": json.dumps(record.get("solver_options")),
        "model_status": record.get("model_status"),
        # Gurobi barrier reports absolute primal/dual infeasibility and a
        # complementarity gap, not PDLP's relative metrics.
        "ipm_final_gap": record.get("ipm_final_gap"),
        "ipm_final_pinf": record.get("ipm_final_pinf"),
        "ipm_final_dinf": record.get("ipm_final_dinf"),
        "barrier_iterations": record.get("gurobi_barrier_iterations"),
        "objective_value": record.get("objective_value"),
        "lp_rows": record.get("lp_rows"),
        "solve_s": record.get("solve_s"),
        "wall_clock_s": record.get("wall_clock_s"),
        "peak_rss_gib": record.get("peak_rss_gib"),
        "network_path": str(layout.network(f"{run_id}_{year}", ARCHETYPE)),
        "record_path": str(layout.record(f"{run_id}_{year}")),
    }


def extract_chain_products(
    run_id: str,
    trajectory: Trajectory,
    pressure: Pressure,
    years: list[int],
    layout: OutputLayout,
    workbook_cache: Path,
    per_chain_dir: Path,
) -> list[int]:
    """Write one chain's frontier, mix, storage and manifest CSVs.

    This is the parallel unit of the pipeline: it opens every network the chain needs
    and writes only small CSVs, so the assemble stage never touches a network.

    :return: The milestone years actually extracted.
    """
    solved = _solved_years(layout, run_id, years)
    per_chain_dir.mkdir(parents=True, exist_ok=True)
    frontier = _frontier_frame(
        run_id, pressure, trajectory.key, solved, layout, workbook_cache
    )
    mix = pd.DataFrame(
        [_mix_row(run_id, year, layout.runs, EXCLUDED_MIX_CARRIERS) for year in solved]
    )
    storage = pd.DataFrame(
        [row for year in solved for row in _storage_rows(run_id, year, layout.runs)]
    )
    manifest = pd.DataFrame(
        [_manifest_row(run_id, pressure, trajectory, year, layout) for year in solved]
    )
    for name, frame in [
        ("frontier", frontier),
        ("mix", mix),
        ("storage", storage),
        ("manifest", manifest),
    ]:
        frame.to_csv(per_chain_dir / f"{name}_{run_id}.csv", index=False)
    return solved


# ---------------------------------------------------------------------- assembly


def _read_per_chain(per_chain_dir: Path, name: str) -> pd.DataFrame:
    """Concatenate one per-chain CSV family back into a single frame."""
    frames = [pd.read_csv(path) for path in sorted(per_chain_dir.glob(f"{name}_*.csv"))]
    return pd.concat(frames, ignore_index=True)


def _merge_results(frontier: pd.DataFrame, mix: pd.DataFrame) -> pd.DataFrame:
    """Join the mix onto the frontier coordinates and zero the absent carriers.

    A carrier absent from one cell-year (no Brown Coal left by 2050, say) leaves NaN
    rather than the zero it means, which would poison the marginal differences.
    """
    results = frontier.merge(
        mix, on=["cell", "year"], how="left", suffixes=("", "_mix")
    )
    absent = [c for c in results.columns if c.startswith(("twh_", "share_", "gw_"))]
    results[absent] = results[absent].fillna(0.0)
    return results


def _add_load_shedding(results: pd.DataFrame) -> pd.DataFrame:
    """Flag the cells where the pressure setting outran the fleet.

    Shedding is measured against demand, not generation, because demand is the
    denominator every cost and emissions intensity on the page is quoted per.
    """
    results = results.copy()
    results["use_pct_of_demand"] = (
        results["use_mwh"] / (results["delivered_twh"] * 1e6) * 100
    )
    results["served_twh"] = results["delivered_twh"] - results["use_mwh"] / 1e6
    results["boundary"] = results["use_pct_of_demand"] > BOUNDARY_USE_PCT
    return results


def _add_pressure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Expand the pressure key into its family and value.

    Derived here rather than in the per-chain extraction so the exported tables have
    one authoritative source for what a pressure key means.
    """
    parsed = frame["pressure"].map(parse_pressure)
    return frame.assign(
        pressure_kind=parsed.map(lambda p: p.kind),
        pressure_value=parsed.map(lambda p: p.value),
    )


def _add_unpriced_fuel(results: pd.DataFrame) -> pd.DataFrame:
    """Flag cells charged nothing for fuel while fuel-burning plant ran.

    The IASR fuel-price tables end at financial year 2054-55, so the campaign's 2060
    milestone finds no price column and the post-processor's lookup returns zero. A
    cell that burns fuel but pays nothing for it understates its average cost by the
    whole fuel term, which is tens of AUD/MWh wherever gas still runs, so it is marked
    rather than quietly reported.
    """
    results = results.copy()
    burning = sum(results.get(f"share_{c}", 0.0) for c in FUEL_BURNING_CARRIERS)
    results["fuel_unpriced"] = (results["diagnostic_fuel_cost_per_mwh"] <= 0) & (
        burning > FUEL_BURNING_FLOOR_PCT
    )
    return results


def _acceptance_per_cell(results: pd.DataFrame) -> pd.DataFrame:
    """Per cell-period: did it serve its demand, and did the solver certify it?

    Termination reuses the frontier extractor's own `tolerance_robust` verdict, so the
    acceptance table and the cost coordinates are judged against one convergence rule.
    """
    return pd.DataFrame(
        {
            "cell": results["cell"],
            "year": results["year"],
            "test1_serves_demand": ~results["boundary"],
            "use_mwh": results["use_mwh"],
            "use_pct_of_demand": results["use_pct_of_demand"],
            "test4_termination": results["tolerance_robust"],
            "model_status": results["solve_model_status"],
            "solve_gap": results["solve_gap_rel"],
            "solve_pinf": results["solve_pinf_rel"],
            "solve_dinf": results["solve_dinf_rel"],
        }
    )


def _cost_monotone_rows(
    results: pd.DataFrame, years: list[int], pressures: list[Pressure], order: list[str]
) -> list[dict]:
    """Does total system cost rise with demand, at each (year, pressure)?

    Pass served cells only. A boundary cell's total is the cost of a system that did
    not meet its demand, so comparing it against a neighbour that did tests nothing.
    `trajectories_compared` records how much of the ladder each verdict rests on.
    """
    rows = []
    for year in years:
        for pressure in pressures:
            block = results[(results.year == year) & (results.pressure == pressure.key)]
            costs = block.set_index("trajectory").reindex(order).dropna(how="all")
            rows.append(
                {
                    "year": year,
                    "pressure": pressure.key,
                    "test3_cost_monotone_in_demand": bool(
                        (costs["total_cost_aud_per_yr"].diff().dropna() >= 0).all()
                    ),
                    "trajectories_compared": len(costs),
                }
            )
    return rows


def _intensity_monotone_rows(
    results: pd.DataFrame, years: list[int], caps: list[Pressure], order: list[str]
) -> list[dict]:
    """Does emissions intensity fall as the cap deepens, at each (year, trajectory)?

    Only the cap family is tested. Cap and price chains are not commensurable, so a
    ladder mixing them has no expected direction.
    """
    cap_keys = [pressure.key for pressure in caps]
    rows = []
    for year in years:
        for trajectory in order:
            block = results[(results.year == year) & (results.trajectory == trajectory)]
            block = block.set_index("pressure").reindex(cap_keys).dropna(how="all")
            rows.append(
                {
                    "year": year,
                    "trajectory": trajectory,
                    "test2_intensity_monotone_in_cap": bool(
                        (block["co2e_total_t_per_mwh"].diff().dropna() <= 0).all()
                    ),
                }
            )
    return rows


def assemble(
    per_chain_dir: Path,
    exports_dir: Path,
    years: list[int],
    trajectories: list[Trajectory],
) -> dict[str, pd.DataFrame]:
    """Read the per-chain CSVs back and build the six campaign deliverables."""
    merged = _merge_results(
        _read_per_chain(per_chain_dir, "frontier"),
        _read_per_chain(per_chain_dir, "mix"),
    )
    results = _add_pressure_columns(_add_unpriced_fuel(_add_load_shedding(merged)))
    pressures = order_pressures(list(results["pressure"]))
    order = [trajectory.key for trajectory in trajectories]
    # A boundary cell's cost is quoted per MWh of demand it did not fully serve, so
    # differencing it against a neighbour would price the shortfall as if it were supply.
    marginals = _marginals(
        results[~results["boundary"]],
        level_order=order,
        periods=years,
        series_column="pressure",
        level_column="trajectory",
    )
    per_grid = pd.DataFrame(
        _cost_monotone_rows(results[~results["boundary"]], years, pressures, order)
        + _intensity_monotone_rows(
            results, years, [p for p in pressures if p.kind == CAP_KIND], order
        )
    )
    return {
        "results.csv": results,
        "storage.csv": _read_per_chain(per_chain_dir, "storage"),
        "marginals.csv": marginals,
        "manifest.csv": _add_pressure_columns(
            _read_per_chain(per_chain_dir, "manifest")
        ),
        "acceptance_per_cell.csv": _acceptance_per_cell(results),
        "acceptance_per_grid.csv": per_grid,
    }


# --------------------------------------------------------------------------- cli


def _chain_ids(chains_path: Path) -> list[str]:
    """Run ids of the campaign, in manifest order, from the Slurm chains table."""
    chains = pd.read_csv(
        chains_path, sep="\t", header=None, names=["run_id", "trajectory", "args"]
    )
    return list(chains["run_id"])


def _run_extract(
    layout: OutputLayout,
    plan: dict,
    run_ids: list[str],
    workbook_cache: Path,
    exports: Path,
) -> None:
    """Extract one chain's products, or every chain's in sequence."""
    trajectories = {t.key: t for t in trajectories_from_plan(plan)}
    years = plan["milestone_years"]
    for run_id in run_ids:
        trajectory_key, pressure_key = split_chain_id(run_id)
        solved = extract_chain_products(
            run_id,
            trajectories[trajectory_key],
            parse_pressure(pressure_key),
            years,
            layout,
            workbook_cache,
            exports / "per_chain",
        )
        print(f"  extracted {run_id}  ({len(solved)} milestones: {solved})")


def _run_assemble(plan: dict, exports: Path) -> None:
    """Build and write the six deliverable tables."""
    tables = assemble(
        exports / "per_chain",
        exports,
        plan["milestone_years"],
        trajectories_from_plan(plan),
    )
    exports.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(exports / name, index=False)
        print(f"  wrote {name}  ({len(frame)} rows)")
    results = tables["results.csv"]
    print(
        f"  boundary cells (load shedding above {BOUNDARY_USE_PCT}% of demand): "
        f"{results['boundary'].sum()}"
    )
    print(
        "  cells with unpriced fuel (milestone beyond the IASR price tables): "
        f"{results['fuel_unpriced'].sum()}"
    )


def main(
    stage: Literal["extract", "assemble", "all"] = "all",
    only: str | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    plan: Path = DEFAULT_PLAN,
    workbook_cache: Path = DEFAULT_WORKBOOK_CACHE,
    chains: Path | None = None,
    exports: Path | None = None,
) -> None:
    """Build the extension campaign deliverables.

    :param stage: Which half to run: per-chain extraction, assembly, or both.
    :param only: Extract just this chain, for parallel extraction.
    :param output_root: Campaign output root holding the runs.
    :param plan: Demand plan JSON.
    :param workbook_cache: Parsed IASR workbook cache the fuel prices come from.
    :param chains: Slurm chains table (default ``<output-root>/campaign/chains.tsv``).
    :param exports: Directory the deliverables are written to (default ``<output-root>/exports``).
    """
    chains = chains or output_root / "campaign" / "chains.tsv"
    exports = exports or output_root / "exports"
    layout = OutputLayout(output_root)
    plan_data = json.loads(plan.read_text(encoding="utf-8"))
    if stage in ("extract", "all"):
        run_ids = [only] if only else _chain_ids(chains)
        _run_extract(layout, plan_data, run_ids, workbook_cache, exports)
    if stage in ("assemble", "all"):
        _run_assemble(plan_data, exports)
