"""Myopic period-decomposition driver for ISPyPSA.

Runs N sequential single-period ISPyPSA capacity-expansion solves. Two modes:

  default (independent-static): each year is a greenfield-on-IASR-baseline
  solve with no memory of prior years. Cheap and parallelisable, but the
  greenfield trajectories are not realisable (persistence probe established
  ~17% emissions / -7.7 pp renewable-share shift when 2040 capacity is
  forced into 2045).

  --recursive-dynamic: each year's new-build tranche is extracted after the
  solve and accumulated into a per-chain tranche directory. The next year's
  solve loads all surviving prior tranches and threads them into the
  in-memory pypsa_friendly dict between translation and timeseries
  generation (recursive_dynamic.inject_carried_tranches). The chain
  accumulates vintages — a 2050 solve carries 2030's + 2035's + 2040's +
  2045's surviving stock, each named after the originating new-entrant row
  so the same base tech built in different years yields distinct carried
  rows. Retirement is enforced by PyPSA's active-assets check
  (build_year + lifetime > period). See recursive_dynamic.py for the three
  correctness traps the design clears.

Per-period the script builds an ISPyPSA workflow at year T as the single
investment period, optionally injects carried tranches (if
--recursive-dynamic), solves, extracts dispatch + capacity + (in RD mode)
the newly-built tranche, then moves to the next period.

Per-period settings that vary along a chain (the absolute CO2e cap and the parsed
trace directory) are given as ``YEAR:VALUE`` schedules, one entry per period:

    --co2-cap-t-schedule 2030:19984000 2040:2672000 2050:332000 2060:392000
    --parsed-traces-directory-schedule 2030:/traces/central_2030 2040:/traces/central_2040 ...

All run products go under ``--output-root`` (default ``outputs/``); see
output_layout.OutputLayout for the directory shape.

Usage:
    uv run python analysis/benchmarks/run_myopic.py \\
        --run-id nsw_6p_myopic \\
        --filter NSW \\
        --periods 2025 2030 2035 2040 2045 2050 \\
        --archetype cost_optimal \\
        --budget-min 600 \\
        --recursive-dynamic
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pandas as pd
import psutil

# Add the project root to sys.path so `from analysis.benchmarks.recursive_dynamic
# import ...` resolves at runtime. `uv run python analysis/benchmarks/run_myopic.py`
# only puts the script's directory (analysis/benchmarks/) on sys.path; without this
# the recursive-dynamic tranche extraction silently fails with ImportError caught by
# the try/except below, and the chain proceeds as a no-op carrying nothing forward.
# instrumented_runner.py:30 and probe_persistence.py:43 use the same idiom.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.benchmarks.output_layout import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    OutputLayout,
)

BENCH = Path(__file__).parent

T = TypeVar("T")


def _parse_year_schedule(tokens: list[str], cast: Callable[[str], T]) -> dict[int, T]:
    """Parse ``YEAR:VALUE`` tokens into a per-year mapping.

    ``["2030:1.5", "2040:2"]`` with ``cast=float`` gives ``{2030: 1.5, 2040: 2.0}``.
    Each year may appear once; a malformed token raises ``ValueError``.
    """
    schedule: dict[int, T] = {}
    for token in tokens:
        year_text, sep, value_text = token.partition(":")
        if not sep or not year_text.isdigit():
            raise ValueError(f"Schedule entry must look like YEAR:VALUE, got {token!r}")
        year = int(year_text)
        if year in schedule:
            raise ValueError(f"Year {year} appears twice in schedule {tokens}")
        schedule[year] = cast(value_text)
    return schedule


def _require_schedule_covers_periods(
    schedule: dict[int, T], periods: list[int], flag: str
) -> None:
    """Raise early if a schedule leaves any period of the chain unspecified."""
    missing = sorted(set(periods) - set(schedule))
    if missing:
        raise ValueError(f"{flag} has no entry for periods {missing}")


def _write_period_config(
    run_id: str,
    year: int,
    regions: list[str] | None,
    rep_weeks: list[int] | None = None,
    full_year: bool = False,
    named_weeks: bool = True,
    resolution_min: int = 30,
    carbon_price: float = 0.0,
    tns_price: float = 0.0,
    gas_supply_curve_csv: str | None = None,
    biomass_supply_curve_csv: str | None = None,
    ccs_sink_tranches_csv: str | None = None,
    ccs_transport_csv: str | None = None,
    parsed_traces_directory: str = "analysis/data/traces",
    dataset_year: int = 2024,
    iasr_final: bool = False,
    unserved_energy_cost: float = 10000.0,
    reference_years: list[int] | None = None,
    gas_unblended: bool = False,
    layout: OutputLayout = OutputLayout(DEFAULT_OUTPUT_ROOT),
) -> Path:
    """Synthesise a single-period config for this milestone year.

    Callers pass `run_id` already containing the year suffix (sub_run_id from
    main()). We do NOT append the year again — earlier versions did, producing
    paths like `..._gas_fleet_maintained_2025_2025__gas_fleet_maintained/...`
    which exceeded Windows' 260-char MAX_PATH on the longer archetype names
    (gas_fleet_maintained / rapid_coal_phaseout) when written under
    `pypsa_friendly/capacity_expansion_timeseries/marginal_cost_timeseries/`
    with the longest generator parquet name in the cache
    (`morgan_to_whyalla_pipeline_no_1_ps_and_water_filtration_plant.parquet`,
    66 chars).
    """
    ref_years = reference_years if reference_years is not None else [2018]
    cfg_path = layout.config(run_id)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    filter_line = f"filter_by_nem_regions: {regions}\n" if regions else "# Full NEM\n"
    # Vintage wiring: dataset_year 2026 -> Draft 2026 ISP economics (v7.5 cache +
    # the Draft 2026 workbook + the 7.5/ manual tables); otherwise 2025 IASR
    # (v7.4). Keyed on dataset_year so the trace vintage and economics vintage
    # stay coherent.
    if iasr_final:
        # FINAL 2026 ISP economics: v7.8 cache (workbook_cache_final, built via the
        # repo-tracked 7.8 parser-config override) + the final workbook. Pair with
        # --parsed-traces-directory data/trace_data_final (the FINAL traces +
        # appended 10 draft-vintage solar). dataset_year stays 2026 so the
        # flagged-exclusion gate + isp_<year> trace-subdir convention hold.
        workbook_path = (
            "iasr inputs/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm"
        )
        workbook_cache = "analysis/data/workbook_cache_final"
        iasr_version = "7.8"
    elif dataset_year == 2026:
        workbook_path = (
            "iasr inputs/Draft 2026 ISP Inputs and Assumptions workbook.xlsx"
        )
        workbook_cache = "analysis/data/workbook_cache_v75"
        iasr_version = "7.5"
    else:
        workbook_path = "iasr inputs/2025-inputs-and-assumptions-workbook.xlsm"
        workbook_cache = "analysis/data/workbook_cache"
        iasr_version = "7.4"
    cfg_text = f"""# Auto-generated myopic config for {run_id} year {year}
paths:
  run_directory: "{layout.runs.as_posix()}"
  ispypsa_run_name: {run_id}
  parsed_traces_directory: "{parsed_traces_directory}"
  workbook_path: "{workbook_path}"
  parsed_workbook_cache: "{workbook_cache}"
trace_data:
  dataset_type: example
  dataset_year: {dataset_year}
iasr_workbook_version: "{iasr_version}"
scenario: Step Change
wacc: 0.07
discount_rate: 0.05
unserved_energy:
  cost: {unserved_energy_cost}
  max_per_node: 100000.0
{filter_line}network:
  transmission_expansion: True
  rez_transmission_expansion: True
  annuitisation_lifetime: 30
  nodes:
    regional_granularity: sub_regions
    rezs: discrete_nodes
  rez_to_sub_region_transmission_default_limit: 1e5
temporal:
  year_type: fy
  range:
    start_year: {year}
    end_year: {year}
  capacity_expansion:
    resolution_min: {resolution_min}
    reference_year_cycle: {ref_years}
    investment_periods: [{year}]
    aggregation:
      # Phase 7.2 (revised): 3-week sampling. Reduced from 4 to 3 weeks
      # after the 4-week smoke landed PDLP duality gap at 1.5e-3
      # (asymptoting above the 1e-3 tolerance target). 3-week LP is
      # ~25 % smaller in nonzeros, which should improve PDLP gap
      # convergence while still providing seasonal coverage. Off-peak
      # week dropped as least informative (largely a scaled-down
      # shoulder).
      #
      # Selection:
      #   peak winter (named residual-peak-demand): mid-June for 2018
      #     reference data — heating-driven evening residual peak, low
      #     solar resource. Team's existing single-rep-week pattern.
      #   peak summer (named peak-demand): data-driven highest
      #     instantaneous demand — Australia's summer afternoon cooling
      #     peak with high solar resource.
      #   spring shoulder (numbered week 42): mid-October — rising
      #     solar resource, moderate demand. Captures the VRE-favouring
      #     economic regime that single-rep-week sampling misses.
      representative_weeks: {"~" if full_year else (rep_weeks if rep_weeks is not None else [42])}
      named_representative_weeks: {"~" if full_year or not named_weeks else "[residual-peak-demand, peak-demand]"}
  operational:
    resolution_min: 30
    reference_year_cycle: {ref_years}
    horizon: 336
    overlap: 48
    aggregation:
      representative_weeks: ~
      named_representative_weeks: [residual-peak-demand]
solver: highs
create_plots: False
carbon_pricing:
  carbon_price: {carbon_price}
  tns_price: {tns_price}
"""
    if gas_unblended:
        cfg_text += "fuel_pricing:\n  blend_biomethane_into_gas: false\n"
    if gas_supply_curve_csv is not None:
        cfg_text += f'gas_supply_curve:\n  curve_csv: "{gas_supply_curve_csv}"\n'
    if biomass_supply_curve_csv is not None:
        cfg_text += (
            f'biomass_supply_curve:\n  curve_csv: "{biomass_supply_curve_csv}"\n'
        )
    if ccs_sink_tranches_csv is not None:
        cfg_text += (
            f"ccs_supply_curve:\n"
            f'  sink_tranches_csv: "{ccs_sink_tranches_csv}"\n'
            f'  transport_csv: "{ccs_transport_csv}"\n'
        )
    cfg_path.write_text(cfg_text)
    return cfg_path


def _run_one_period(
    cfg: Path,
    run_id: str,
    budget_min: float,
    archetype: str,
    use_pdlp: bool = False,
    pdlp_tolerance: float | None = None,
    use_gurobi: bool = False,
    gurobi_bar_conv_tol: float | None = None,
    gurobi_opt_tol: float | None = None,
    gurobi_feas_tol: float | None = None,
    gurobi_method: int | None = None,
    gurobi_crossover: int | None = None,
    gurobi_threads: int | None = None,
    gurobi_numeric_focus: int | None = None,
    gurobi_bar_homogeneous: int | None = None,
    carried_tranches_dir: Path | None = None,
    current_year: int | None = None,
    reducible_existing: bool = False,
    retention_floor_dir: Path | None = None,
    existing_keeping_cost: float = 0.0,
    existing_fom_keeping: bool = False,
    span_weight_years: int | None = None,
    disestablishment_cost: float = 0.0,
    co2_cap_t: float | None = None,
    highs_threads: int | None = None,
    layout: OutputLayout = OutputLayout(DEFAULT_OUTPUT_ROOT),
) -> dict:
    """Run a single period via the instrumented runner and return its record."""
    log_path = layout.log(run_id)
    record_path = layout.record(run_id)
    if record_path.exists():
        record_path.unlink()
    if log_path.exists():
        log_path.unlink()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    solver_flags = f' --output-root "{layout.root.as_posix()}"'
    if highs_threads is not None:
        solver_flags += f" --highs-threads {highs_threads}"
    if use_pdlp:
        solver_flags += " --use-pdlp"
        if pdlp_tolerance is not None:
            solver_flags += f" --pdlp-tolerance {pdlp_tolerance}"
    elif use_gurobi:
        solver_flags += " --use-gurobi"
        if gurobi_bar_conv_tol is not None:
            solver_flags += f" --gurobi-bar-conv-tol {gurobi_bar_conv_tol}"
        if gurobi_opt_tol is not None:
            solver_flags += f" --gurobi-opt-tol {gurobi_opt_tol}"
        if gurobi_feas_tol is not None:
            solver_flags += f" --gurobi-feas-tol {gurobi_feas_tol}"
        if gurobi_threads is not None:
            solver_flags += f" --gurobi-threads {gurobi_threads}"
        if gurobi_method is not None:
            solver_flags += f" --gurobi-method {gurobi_method}"
        if gurobi_crossover is not None:
            solver_flags += f" --gurobi-crossover {gurobi_crossover}"
        if gurobi_numeric_focus is not None:
            solver_flags += f" --gurobi-numeric-focus {gurobi_numeric_focus}"
        if gurobi_bar_homogeneous is not None:
            solver_flags += f" --gurobi-bar-homogeneous {gurobi_bar_homogeneous}"
    if carried_tranches_dir is not None:
        solver_flags += f' --carried-tranches-dir "{carried_tranches_dir}"'
    if reducible_existing:
        solver_flags += " --reducible-existing"
        if existing_keeping_cost:
            solver_flags += f" --existing-keeping-cost {existing_keeping_cost}"
        if existing_fom_keeping:
            solver_flags += " --existing-fom-keeping"
        if span_weight_years is not None:
            solver_flags += f" --span-weight-years {span_weight_years}"
        if disestablishment_cost:
            solver_flags += f" --disestablishment-cost {disestablishment_cost}"
        if retention_floor_dir is not None:
            solver_flags += f' --retention-floor-dir "{retention_floor_dir}"'
    # --current-year is needed by either roll-forward mechanism; add it once.
    if current_year is not None and (
        carried_tranches_dir is not None or retention_floor_dir is not None
    ):
        solver_flags += f" --current-year {current_year}"
    if co2_cap_t is not None:
        solver_flags += f" --co2-cap-t {co2_cap_t}"

    cmd_str = (
        f'"{sys.executable}" -u "{BENCH / "instrumented_runner.py"}" '
        f'--config "{cfg}" --run-id "{run_id}" --archetype {archetype}{solver_flags} '
        f'> "{log_path}" 2>&1'
    )
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd_str, shell=True, env=env)
    psproc = psutil.Process(proc.pid)
    started = time.time()
    peak_rss = 0
    budget_s = budget_min * 60
    while True:
        rc = proc.poll()
        try:
            rss = psproc.memory_info().rss
            for ch in psproc.children(recursive=True):
                try:
                    rss += ch.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    pass
            peak_rss = max(peak_rss, rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        if rc is not None:
            break
        if time.time() - started > budget_s:
            for ch in psproc.children(recursive=True):
                try:
                    ch.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    pass
            psproc.kill()
            proc.wait(timeout=30)
            return {
                "status": "timed_out",
                "wall_clock_s": time.time() - started,
                "peak_rss_gib": peak_rss / (1024**3),
            }
        time.sleep(5)

    if record_path.exists():
        rec = json.loads(record_path.read_text())
        rec["peak_rss_gib"] = peak_rss / (1024**3)
        return rec
    return {
        "status": "failed",
        "wall_clock_s": time.time() - started,
        "peak_rss_gib": peak_rss / (1024**3),
    }


def _completed_record(layout: OutputLayout, run_id: str, archetype: str) -> dict | None:
    """The saved record for a period that already solved, or None if it must be run.

    Used by ``--resume`` so a requeued chain skips periods whose record reports
    ``completed`` and whose solved network is on disk.
    """
    record_path = layout.record(run_id)
    if not record_path.exists() or not layout.network(run_id, archetype).exists():
        return None
    record = json.loads(record_path.read_text())
    return record if record.get("status") == "completed" else None


def _extract_built_capacities(
    layout: OutputLayout, run_id: str, year: int, archetype: str
) -> pd.DataFrame:
    """Extract capacity built in this period — generators with build_year=year."""
    import pypsa

    nc_path = layout.network(f"{run_id}_{year}", archetype)
    if not nc_path.exists():
        return pd.DataFrame()
    n = pypsa.Network(nc_path)
    gens = n.generators[
        ["bus", "carrier", "p_nom_opt", "build_year", "lifetime"]
    ].copy()
    gens = gens[gens["bus"] != "bus_for_custom_constraint_gens"]
    # Filter to new entrants that were built this period
    built = gens[(gens["build_year"] == year) & (gens["p_nom_opt"] > 1.0)]
    return built


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument(
        "--filter",
        default=None,
        help="NEM region filter (e.g. 'NSW'); omit for full NEM",
    )
    ap.add_argument(
        "--periods", type=int, nargs="+", default=[2025, 2030, 2035, 2040, 2045, 2050]
    )
    ap.add_argument(
        "--archetype",
        default="cost_optimal",
        help="Archetype id to apply (default: cost_optimal)",
    )
    ap.add_argument(
        "--budget-min",
        type=float,
        default=720,
        help="Per-period wall-clock budget (default 12h)",
    )
    ap.add_argument(
        "--use-pdlp",
        action="store_true",
        help="Solve with HiGHS PDLP instead of default simplex.",
    )
    ap.add_argument(
        "--pdlp-tolerance",
        type=float,
        default=None,
        help="Set pdlp_optimality_tolerance + primal/dual feasibility "
        "tolerances; only used with --use-pdlp.",
    )
    ap.add_argument(
        "--use-gurobi",
        action="store_true",
        help="Solve with Gurobi instead of HiGHS (overrides config.solver).",
    )
    ap.add_argument(
        "--gurobi-bar-conv-tol",
        type=float,
        default=None,
        help="Set Gurobi BarConvTol; only used with --use-gurobi. PRODUCTION "
        "FRONTIER MUST PIN 1e-4 (the new-artifact menu's quality choice). "
        "If omitted, Gurobi falls back to its 1e-8 default -- tighter than "
        "intended and materially slower; do NOT rely on the default for "
        "production runs.",
    )
    ap.add_argument(
        "--gurobi-opt-tol",
        type=float,
        default=None,
        help="Set Gurobi OptimalityTol (default 1e-6); only used with --use-gurobi.",
    )
    ap.add_argument(
        "--gurobi-feas-tol",
        type=float,
        default=None,
        help="Set Gurobi FeasibilityTol (default 1e-6); only used with --use-gurobi.",
    )
    ap.add_argument(
        "--gurobi-threads",
        type=int,
        default=None,
        help="Set Gurobi Threads (cores per solve); only used with --use-gurobi. "
        "Cap for concurrent trajectories so concurrent x threads <= cores "
        "with headroom; default (unset) uses all cores (single-solve default).",
    )
    ap.add_argument(
        "--highs-threads",
        type=int,
        default=None,
        help="Set the HiGHS 'threads' option (simplex, IPM and PDLP). Pin to the "
        "job's core allocation on a shared node; default (unset) lets HiGHS "
        "use every core it sees.",
    )
    ap.add_argument(
        "--gurobi-method",
        type=int,
        default=None,
        help="Set Gurobi Method (2=barrier); only used with --use-gurobi.",
    )
    ap.add_argument(
        "--gurobi-crossover",
        type=int,
        default=None,
        help="Set Gurobi Crossover (0=off -> interior solution, fast); only used with --use-gurobi.",
    )
    ap.add_argument(
        "--gurobi-numeric-focus",
        type=int,
        default=None,
        help="Set Gurobi NumericFocus (0=auto, 1-3=increasing numerical care); "
        "only used with --use-gurobi. Needed once buildable storage widens "
        "the objective coefficient range (~[1, 1e7]) enough that the barrier "
        "terminates sub-optimal; 2-3 trades speed for numerical robustness.",
    )
    ap.add_argument(
        "--gurobi-bar-homogeneous",
        type=int,
        default=None,
        help="Set Gurobi BarHomogeneous (-1=auto, 0=off, 1=on); only used with "
        "--use-gurobi. The homogeneous barrier is more robust on ill-"
        "conditioned / heavily-coupled LPs (e.g. storage SOC inter-temporal "
        "coupling); try 1 when the default barrier stalls Sub-optimal.",
    )
    ap.add_argument(
        "--rep-weeks",
        type=int,
        nargs="+",
        default=None,
        help="Override representative_weeks list (default [42]). "
        "Named weeks (residual-peak-demand, peak-demand) remain unless "
        "--no-named-weeks is passed. E.g. --rep-weeks 42 33 gives 4-week sampling.",
    )
    ap.add_argument(
        "--no-named-weeks",
        action="store_true",
        help="Drop the named stress weeks (residual-peak-demand, peak-demand) "
        "from capacity_expansion sampling, leaving only --rep-weeks. The "
        "numbered and named sets are unioned (temporal_filters.py:145), so "
        "without this flag an evenly-spaced N-week sample is really N+2 weeks "
        "with the two stress weeks carrying 2/(N+2) of the sample against an "
        "annual frequency of 2/52 -- the overweighting that biased three-week "
        "sampling's gas share +36.7% against the full-year anchor. Use for "
        "even-sampling designs; omit to keep the established stress-weighted "
        "behaviour.",
    )
    ap.add_argument(
        "--full-year",
        action="store_true",
        help="Disable all rep-week sampling (numbered AND named) so the LP "
        "covers the full reference year. Default resolution_min=60 (hourly); "
        "override with --resolution-min.",
    )
    ap.add_argument(
        "--resolution-min",
        type=int,
        default=None,
        help="Override temporal resolution in minutes (default 30 for "
        "rep-week modes; default 60 for --full-year).",
    )
    ap.add_argument(
        "--recursive-dynamic",
        action="store_true",
        help="Enable recursive-dynamic capacity roll-forward: after each "
        "year's solve, extract the new-build tranche and inject all "
        "surviving prior tranches into subsequent solves. Default "
        "(independent-static) is unchanged when this flag is absent.",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Resume a partially-completed chain: keep the tranches/ and "
        "retention/ dirs, and skip any period whose record already reports "
        "completed and whose solved network is on disk, so a requeued job "
        "continues from the first unsolved period. Pass a solver change "
        "together with --periods limited to the remaining years to apply a "
        "per-period fallback. Default (fresh chain, wipe) when absent.",
    )
    ap.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for every run product: configs/, logs/, records/, runs/ "
        "(see output_layout.OutputLayout). Default 'outputs' at the repo root.",
    )
    ap.add_argument(
        "--co2-cap-t-schedule",
        nargs="+",
        default=None,
        metavar="YEAR:TONNES",
        help="Absolute annual CO2e cap per period, e.g. 2030:19984000 "
        "2040:2672000. Every period in --periods needs an entry. Passed to the "
        "runner as --co2-cap-t for that period; the cap's dual is recorded.",
    )
    ap.add_argument(
        "--parsed-traces-directory-schedule",
        nargs="+",
        default=None,
        metavar="YEAR:DIR",
        help="Parsed-traces base directory per period, e.g. 2030:/scratch/central_2030 "
        "2040:/scratch/central_2040 (isp_<dataset_year> is appended). Every "
        "period in --periods needs an entry. Overrides --parsed-traces-directory.",
    )
    ap.add_argument(
        "--reducible-existing",
        action="store_true",
        help="Enable endogenous economic retirement: make existing (ECAA) "
        "generators a downward-only continuous capacity decision each "
        "period, with the retained level carried forward as a monotone "
        "non-increasing floor. Default (fixed existing fleet) is "
        "unchanged when this flag is absent. Composes with "
        "--recursive-dynamic.",
    )
    ap.add_argument(
        "--existing-keeping-cost",
        type=float,
        default=0.0,
        help="Per-MW per-period cost of keeping existing capacity (capital_cost "
        "on the reducible existing generators). 0 = Phase-1 strict; "
        "Phase-2 passes the AEMO fixed-OPEX so idle units are shed.",
    )
    ap.add_argument(
        "--existing-fom-keeping",
        action="store_true",
        help="Phase-2: route each existing unit's own FOM (ecaa fom_$/kw/annum) "
        "as its keeping-cost (capital_cost), instead of --existing-keeping-cost.",
    )
    ap.add_argument(
        "--span-weight-years",
        type=int,
        default=None,
        help="Phase-2 accounting fix: weight each myopic milestone period as an "
        "N-year span, so recurring FOM counts over the span vs the one-off "
        "disestablishment. Default: off (1-year, as the committed menu).",
    )
    ap.add_argument(
        "--disestablishment-cost",
        type=float,
        default=0.0,
        help="Phase-2b: one-off disestablishment/decommissioning cost ($/MW) on "
        "retired existing capacity. A unit sheds only when FOM*span > D. "
        "Default 0 (off).",
    )
    ap.add_argument(
        "--carbon-price",
        type=float,
        default=0.0,
        help="AUD/tCO2e adder on residual emissions, threaded into "
        "config.carbon_pricing.carbon_price for every period in the "
        "chain. Default 0 (no carbon adder).",
    )
    ap.add_argument(
        "--tns-price",
        type=float,
        default=0.0,
        help="AUD/tCO2 T&S cost on captured tonnes for CCS plants. "
        "Threaded into config.carbon_pricing.tns_price. Default 0.",
    )
    ap.add_argument(
        "--gas-supply-curve",
        default="analysis/gas_market/gas_supply_curve_central.csv",
        help="Path to a gas supply curve CSV (tranche, financial_year, "
        "cap_pj, adder_$/gj), threaded into config.gas_supply_curve."
        "curve_csv for every period. Prices gas consumption above "
        "each tranche boundary at an adder over the IASR baseline "
        "gas price. PRODUCTION DEFAULT: the sourced central curve "
        "(full-year validated, GAS_SUPPLY_CURVE.md incl. 5a). Pass "
        "'none' for the pre-curve behaviour (unlimited gas at IASR "
        "prices).",
    )
    ap.add_argument(
        "--gas-unblended",
        action="store_true",
        help="Price the Gas carrier from the IASR gas price table alone, writing "
        "fuel_pricing.blend_biomethane_into_gas: false into every period "
        "config. By default AEMO's mandated biomethane blend is folded into "
        "the gas price trajectory; switching it off isolates the blend's cost "
        "effect and leaves biomethane to a separate bioenergy model.",
    )
    ap.add_argument(
        "--biomass-supply-curve",
        default="analysis/bioenergy_market/biomass_supply_curve_central.csv",
        help="Path to a biomass feedstock supply curve CSV (tranche, "
        "financial_year, cap_pj, adder_$/gj), threaded into "
        "config.biomass_supply_curve.curve_csv for every period. Prices "
        "biomass feedstock consumption above each tranche boundary at an "
        "adder over the IASR baseline biomass price, and disables the flat "
        "$6/GJ feedstock re-price pre-pass. PRODUCTION DEFAULT: the "
        "sourced central curve (BIOMASS_SUPPLY_CURVE.md). Pass 'none' "
        "for the flat re-priced feedstock with unlimited volume.",
    )
    ap.add_argument(
        "--ccs-supply-curve",
        default="analysis/ccs_market/ccs_sink_tranches_conservative.csv",
        help="Path to a CO2 sink injectivity tranche CSV (sink, "
        "financial_year, cap_kt, storage_$/t), threaded into "
        "config.ccs_supply_curve.sink_tranches_csv for every period. Limits "
        "annual captured CO2 per storage sink and prices injection. "
        "PRODUCTION DEFAULT: the conservative variant, in which every cap is "
        "zero because no NEM-reachable sink with spare capacity is connected "
        "to any CCS bus (CCS_SUPPLY_CURVE.md). Pass the optimistic variant "
        "for the branch in which every live proposal is realised at "
        "nameplate, or 'none' for the pre-curve behaviour (free unlimited "
        "disposal, which is also AEMO's own ISP treatment).",
    )
    ap.add_argument(
        "--ccs-transport-adders",
        default="analysis/ccs_market/ccs_transport_adders.csv",
        help="Path to the CO2 transport adder CSV (isp_sub_region_id, sink, "
        "distance_km, transport_$/t), threaded into "
        "config.ccs_supply_curve.transport_csv. Assigns each sub-region its "
        "nearest permitted sink and prices the pipeline per tonne captured.",
    )
    ap.add_argument(
        "--parsed-traces-directory",
        default="analysis/data/traces",
        help="Base parsed-traces dir (isp_<dataset_year> is appended). Use "
        "'data/trace_data' with --dataset-year 2026 for the Draft 2026 store.",
    )
    ap.add_argument(
        "--dataset-year",
        type=int,
        default=2024,
        help="Trace dataset year; selects isp_<year> and (==2026) triggers the "
        "flagged-new-entrant exclusion in instrumented_runner. Default 2024.",
    )
    ap.add_argument(
        "--iasr-final",
        action="store_true",
        help="Use FINAL 2026 ISP economics: v7.8 cache (workbook_cache_final) + "
        "final workbook. Pair with --dataset-year 2026 + "
        "--parsed-traces-directory data/trace_data_final.",
    )
    ap.add_argument(
        "--reference-years",
        type=int,
        nargs="+",
        default=None,
        help="Weather reference-year cycle for BOTH demand and VRE traces "
        "(config temporal.*.reference_year_cycle). Default [2018] — note "
        "that under the FINAL 2026 store this label holds AEMO's synthetic "
        "RefYear5000 sequence, not historical 2018. Real historical years "
        "2011-2017 and 2019-2025 are available as of the 2026-08 per-year "
        "trace ingestion. One year gives a single-weather-year solve; "
        "multiple years cycle across the model years in range.",
    )
    ap.add_argument(
        "--unserved-energy-cost",
        type=float,
        default=10000.0,
        help="AUD/MWh value-of-lost-load penalty on the Unserved Energy slack "
        "generator (config unserved_energy.cost). Default 10000.0, matching "
        "every committed frontier run. Lower to test how much of the model's "
        "firm-gas build is driven by this penalty's strictness vs the "
        "single-2018-year reliability standard itself (USE-penalty test).",
    )
    args = ap.parse_args()

    # 'none' sentinel opts out of the production-default supply curves.
    if args.gas_supply_curve and args.gas_supply_curve.lower() == "none":
        args.gas_supply_curve = None
    if args.biomass_supply_curve and args.biomass_supply_curve.lower() == "none":
        args.biomass_supply_curve = None
    if args.ccs_supply_curve and args.ccs_supply_curve.lower() == "none":
        args.ccs_supply_curve = None

    layout = OutputLayout(args.output_root)
    cap_schedule = (
        _parse_year_schedule(args.co2_cap_t_schedule, float)
        if args.co2_cap_t_schedule
        else {}
    )
    if cap_schedule:
        _require_schedule_covers_periods(
            cap_schedule, args.periods, "--co2-cap-t-schedule"
        )
    traces_schedule = (
        _parse_year_schedule(args.parsed_traces_directory_schedule, str)
        if args.parsed_traces_directory_schedule
        else {}
    )
    if traces_schedule:
        _require_schedule_covers_periods(
            traces_schedule, args.periods, "--parsed-traces-directory-schedule"
        )

    regions = [args.filter] if args.filter else None
    # Per-chain tranche directory: independent-static runs never touch it
    # (carried_tranches_dir stays None), so default behaviour is bit-identical
    # to the pre-recursive-dynamic code path.
    tranches_dir = (
        layout.chain_dir(args.run_id) / "tranches" if args.recursive_dynamic else None
    )
    if tranches_dir is not None:
        # Fresh chain → empty tranche directory. A re-run that wants to resume
        # from a partially-completed chain should preserve prior tranches; the
        # explicit `--recursive-dynamic` invocation starts clean here so a
        # rerun does not accidentally inherit stale state from a different
        # configuration.
        if tranches_dir.exists() and not args.resume:
            shutil.rmtree(tranches_dir)
        tranches_dir.mkdir(parents=True, exist_ok=True)

    # Parallel retention floor for endogenous existing-fleet retirement. Like
    # tranches_dir, a fresh chain starts clean so a rerun does not inherit stale
    # retained levels from a different configuration.
    retention_dir = (
        layout.chain_dir(args.run_id) / "retention" if args.reducible_existing else None
    )
    if retention_dir is not None:
        if retention_dir.exists() and not args.resume:
            shutil.rmtree(retention_dir)
        retention_dir.mkdir(parents=True, exist_ok=True)

    seq_record = {
        "run_id": args.run_id,
        "kind": "myopic_sequential",
        "archetype": args.archetype,
        "regions_filter": regions,
        "periods": args.periods,
        "recursive_dynamic": args.recursive_dynamic,
        "tranches_dir": str(tranches_dir) if tranches_dir else None,
        "output_root": str(layout.root),
        "carbon_price": args.carbon_price,
        "co2_cap_t_schedule": cap_schedule or None,
        "parsed_traces_directory_schedule": traces_schedule or None,
        "tns_price": args.tns_price,
        "gas_supply_curve": args.gas_supply_curve,
        "gas_unblended": args.gas_unblended,
        "biomass_supply_curve": args.biomass_supply_curve,
        "ccs_supply_curve": args.ccs_supply_curve,
        "unserved_energy_cost": args.unserved_energy_cost,
        "reference_years": args.reference_years if args.reference_years else [2018],
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "per_period": {},
        "cumulative_wall_clock_s": 0.0,
        "peak_rss_gib_observed": 0.0,
    }

    seq_started = time.time()
    for year in args.periods:
        sub_run_id = f"{args.run_id}_{year}"
        print(
            f"\n=== Myopic period {year} ({sub_run_id}) archetype={args.archetype} ==="
        )
        # capacity_expansion.resolution_min must match operational.resolution_min
        # (validator constraint in src/ispypsa/config/validators.py). Operational
        # is fixed at 30 in the template, so capacity_expansion stays 30 unless
        # the caller knows what they are doing.
        resolution_min = args.resolution_min if args.resolution_min is not None else 30
        # A schedule path is normalised to POSIX form because it lands inside a
        # double-quoted YAML scalar, where a Windows backslash path is a bad escape.
        traces_dir = (
            Path(traces_schedule[year]).as_posix()
            if traces_schedule
            else args.parsed_traces_directory
        )
        cfg = _write_period_config(
            sub_run_id,
            year,
            regions,
            rep_weeks=args.rep_weeks,
            full_year=args.full_year,
            named_weeks=not args.no_named_weeks,
            resolution_min=resolution_min,
            carbon_price=args.carbon_price,
            tns_price=args.tns_price,
            gas_supply_curve_csv=args.gas_supply_curve,
            gas_unblended=args.gas_unblended,
            biomass_supply_curve_csv=args.biomass_supply_curve,
            ccs_sink_tranches_csv=args.ccs_supply_curve,
            ccs_transport_csv=args.ccs_transport_adders,
            parsed_traces_directory=traces_dir,
            dataset_year=args.dataset_year,
            iasr_final=args.iasr_final,
            unserved_energy_cost=args.unserved_energy_cost,
            reference_years=args.reference_years,
            layout=layout,
        )
        per_started = time.time()
        already_solved = (
            _completed_record(layout, sub_run_id, args.archetype)
            if args.resume
            else None
        )
        if already_solved is not None:
            print(f"  Period {year} already completed; skipping solve (--resume)")
        rec = already_solved or _run_one_period(
            cfg,
            sub_run_id,
            args.budget_min,
            args.archetype,
            use_pdlp=args.use_pdlp,
            pdlp_tolerance=args.pdlp_tolerance,
            use_gurobi=args.use_gurobi,
            gurobi_bar_conv_tol=args.gurobi_bar_conv_tol,
            gurobi_opt_tol=args.gurobi_opt_tol,
            gurobi_feas_tol=args.gurobi_feas_tol,
            gurobi_method=args.gurobi_method,
            gurobi_crossover=args.gurobi_crossover,
            gurobi_threads=args.gurobi_threads,
            gurobi_numeric_focus=args.gurobi_numeric_focus,
            gurobi_bar_homogeneous=args.gurobi_bar_homogeneous,
            carried_tranches_dir=tranches_dir,
            current_year=year
            if (tranches_dir is not None or retention_dir is not None)
            else None,
            reducible_existing=args.reducible_existing,
            retention_floor_dir=retention_dir,
            existing_keeping_cost=args.existing_keeping_cost,
            existing_fom_keeping=args.existing_fom_keeping,
            span_weight_years=args.span_weight_years,
            disestablishment_cost=args.disestablishment_cost,
            co2_cap_t=cap_schedule.get(year),
            highs_threads=args.highs_threads,
            layout=layout,
        )
        per_wall = time.time() - per_started
        rec["per_period_wall_s"] = per_wall
        rec["per_period_peak_gib"] = rec.get("peak_rss_gib", 0)
        # capacity_built per fuel_type
        try:
            built = _extract_built_capacities(layout, args.run_id, year, args.archetype)
            by_fuel_gw = (
                built.groupby("carrier")["p_nom_opt"].sum() / 1000.0
            ).to_dict()
            rec["capacity_built_gw_by_fuel"] = by_fuel_gw
            rec["total_capacity_built_gw"] = float(built["p_nom_opt"].sum() / 1000.0)
        except Exception as e:
            rec["capacity_extract_error"] = str(e)
        if tranches_dir is not None and rec.get("status") == "completed":
            try:
                from analysis.benchmarks.recursive_dynamic import (
                    extract_new_built_tranche,
                    save_tranche,
                )

                nc_path = layout.network(sub_run_id, args.archetype)
                tranche = extract_new_built_tranche(nc_path, year)
                save_tranche(tranche, tranches_dir, year)
                rec["tranche_extracted"] = {
                    "generators_rows": int(len(tranche["generators"])),
                    "batteries_rows": int(len(tranche["batteries"])),
                    "generator_mw": float(
                        tranche["generators"]["p_nom"].sum()
                        if not tranche["generators"].empty
                        else 0.0
                    ),
                    "battery_mw": float(
                        tranche["batteries"]["p_nom"].sum()
                        if not tranche["batteries"].empty
                        else 0.0
                    ),
                }
            except Exception as e:
                rec["tranche_extract_error"] = str(e)
        if retention_dir is not None and rec.get("status") == "completed":
            try:
                from analysis.benchmarks.retirement import (
                    extract_retained_existing,
                    save_retention_floor,
                )

                run_root = layout.run_dir(sub_run_id, args.archetype)
                floor = extract_retained_existing(run_root, year)
                save_retention_floor(floor, retention_dir, year)
                rec["retention_floor"] = {
                    "existing_units": int(len(floor)),
                    "retained_mw": float(sum(floor.values())),
                }
            except Exception as e:
                rec["retention_extract_error"] = str(e)
        seq_record["per_period"][year] = rec
        seq_record["cumulative_wall_clock_s"] = time.time() - seq_started
        seq_record["peak_rss_gib_observed"] = max(
            seq_record["peak_rss_gib_observed"], rec.get("peak_rss_gib", 0)
        )
        # Save partial after each period in case we die early.
        layout.record(args.run_id).write_text(
            json.dumps(seq_record, indent=2, default=str)
        )
        if rec.get("status") != "completed":
            print(f"  Period {year} status: {rec.get('status')}; aborting sequence")
            break
        # Recursive-dynamic-specific halt: a tranche extraction failure means the
        # next year would inherit an empty floor and run as bit-identical to a
        # greenfield standalone — corrupting the chain silently. The pre-fix bug
        # at step3_chain_p200_8760 logged `tranche_extract_error: "No module named
        # 'analysis'"` and the chain proceeded anyway because the solve
        # itself succeeded; here we halt instead so a failed write-back surfaces
        # immediately rather than poisoning the downstream chain.
        if tranches_dir is not None and rec.get("tranche_extract_error"):
            print(
                f"  Period {year} tranche extraction FAILED: "
                f"{rec.get('tranche_extract_error')}; halting recursive-dynamic "
                f"chain (next year would carry no floor and run as no-op)."
            )
            break
        if retention_dir is not None and rec.get("retention_extract_error"):
            print(
                f"  Period {year} retention extraction FAILED: "
                f"{rec.get('retention_extract_error')}; halting reducible-existing "
                f"chain (next year would lose the monotone retirement floor)."
            )
            break

    seq_record["ended_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    seq_record["cumulative_wall_clock_s"] = time.time() - seq_started
    layout.record(args.run_id).write_text(json.dumps(seq_record, indent=2, default=str))
    print(
        f"\n=== Done. Cumulative wall: {seq_record['cumulative_wall_clock_s']:.0f}s ==="
    )


if __name__ == "__main__":
    main()
