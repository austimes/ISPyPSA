"""Instrumented ISPyPSA runner for compute-envelope characterisation.

Wraps the standard run_workflow pipeline with:
  - per-stage wall-clock timing
  - peak RSS memory tracked via a sibling psutil poller
  - HiGHS log parsing for LP problem size and convergence status

Writes a JSON record summarising the run to <output-root>/records/<run_id>.json and
the solver log to <output-root>/logs/<run_id>.log.

This is an internal entry point: `msm solve` launches it as a subprocess, one per
period, and is its only caller. Its flags are therefore argparse rather than cyclopts,
and they carry only what `msm solve` passes.

Usage:
    uv run python -m analysis.hpc.instrumented_runner \
        --config <run dir>/configs/<run_id>.yaml \
        --run-id nem_3period \
        --output-root outputs
"""

import argparse
import hashlib
import json
import os
import random
import re
import socket
import subprocess
import threading
import time
import traceback
from pathlib import Path

import psutil

from analysis.env import RUN_DIR_SUFFIX, OutputLayout

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ----- Gurobi license-retry ----------------------------------------------

# The CSIRO Gurobi token server carries thousands of seats, so every chain of a
# campaign runs concurrently. A seat can still be refused ("use limit exceeded")
# when the server is saturated or briefly unreachable, so a bounded retry lets a
# chain wait for a seat instead of halting. Kept under `msm solve`'s --budget-min
# wall-clock cap.
_LICENSE_RETRY_MAX_WAIT_S = 36000  # 10 h


def extract_fuel_supply_curve_usage(network, fuel_supply_curve, carrier):
    """Reads solved tranche purchases into a tidy per-period usage table (PJ).

    The tranche variables live only in the in-process linopy model (not the
    saved NetCDF), so this must run in the same process as the solve.
    """
    import pandas as pd

    rows = []
    for period in network.investment_periods:
        variable_name = f"{carrier.lower()}_supply_purchases_tj_{period}"
        if variable_name not in network.model.variables:
            continue
        solution = network.model.variables[variable_name].solution
        tranches = fuel_supply_curve[fuel_supply_curve["investment_period"] == period]
        for _, tranche in tranches.iterrows():
            used_pj = (
                float(solution.sel({f"{carrier.lower()}_tranche": tranche["tranche"]}))
                / 1.0e3
            )
            rows.append(
                {
                    "investment_period": period,
                    "tranche": tranche["tranche"],
                    "adder_$/gj": tranche["adder_$/gj"],
                    "cap_pj": tranche["cap_pj"],
                    "used_pj": used_pj,
                    "premium_cost_$m": used_pj * tranche["adder_$/gj"],
                }
            )
    return pd.DataFrame(rows)


def _solve_with_license_retry(network, kwargs) -> bool:
    """Solve, retrying only while the token server reports no free seat.

    Returns True on success, False on a genuine solve failure or once the retry
    budget (`_LICENSE_RETRY_MAX_WAIT_S`) is exhausted. Any non-license exception
    is reported and returned as a failure immediately - never retried.
    """
    deadline = time.perf_counter() + _LICENSE_RETRY_MAX_WAIT_S
    while True:
        try:
            network.optimize.solve_model(**kwargs)
            return True
        except Exception as e:
            seat_busy = "use limit" in str(e).lower()
            if not (seat_busy and time.perf_counter() < deadline):
                print(f"\n=== SOLVE EXCEPTION === {type(e).__name__}: {e}", flush=True)
                traceback.print_exc()
                return False
            wait = 60 + random.uniform(0, 30)  # jitter avoids a thundering herd
            print(f"\n=== LICENSE BUSY (retry in {wait:.0f}s) === {e}", flush=True)
            time.sleep(wait)


# ----- memory poller -----------------------------------------------------


class MemoryPoller(threading.Thread):
    """Polls current process RSS at fixed interval, keeps peak."""

    def __init__(self, interval_s: float = 1.0):
        super().__init__(daemon=True)
        self.interval = interval_s
        self.peak_rss_bytes = 0
        self.samples = []
        self._stop_event = threading.Event()
        self._proc = psutil.Process(os.getpid())

    def run(self):
        while not self._stop_event.wait(self.interval):
            try:
                rss = self._proc.memory_info().rss
                # Also include child Python processes if any
                for child in self._proc.children(recursive=True):
                    try:
                        rss += child.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                self.peak_rss_bytes = max(self.peak_rss_bytes, rss)
                self.samples.append((time.time(), rss))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

    def stop(self):
        self._stop_event.set()
        self.join(timeout=2.0)


# ----- HiGHS log parser --------------------------------------------------

_LP_SIZE_RE = re.compile(
    r"has\s+(\d+)\s+rows;\s+(\d+)\s+cols;\s+(\d+)\s+nonzeros",
)
# Gurobi: "Optimize a model with 100 rows, 200 columns and 20000 nonzeros"
_GUROBI_LP_SIZE_RE = re.compile(
    r"Optimize a model with\s+(\d+)\s+rows?,\s+(\d+)\s+columns?\s+and\s+(\d+)\s+nonzeros",
)
_MODEL_STATUS_RE = re.compile(r"Model status\s*:\s*(\S.*?)\s*$", re.MULTILINE)
_HIGHS_RUN_TIME_RE = re.compile(r"HiGHS run time\s*:\s*([\d.]+)")
# Gurobi solve-time lines (one of):
#   "Solved in 148 iterations and 0.02 seconds (0.02 work units)"           [simplex]
#   "Barrier solved model in 12 iterations and 5.31 seconds (3.20 work units)" [barrier]
#   "Concurrent spin time: 0.00s"                                            [concurrent]
_GUROBI_SIMPLEX_TIME_RE = re.compile(
    r"Solved in\s+(\d+)\s+iterations? and\s+([\d.]+)\s+seconds"
)
_GUROBI_BARRIER_TIME_RE = re.compile(
    r"Barrier solved model in\s+(\d+)\s+iterations? and\s+([\d.]+)\s+seconds"
)
# Gurobi status: "Optimal objective <value>" or terminal status line
_GUROBI_OPTIMAL_OBJ_RE = re.compile(r"Optimal objective\s+([-\d.eE+]+)")
_GUROBI_STATUS_RE = re.compile(
    r"^\s*(Optimal|Infeasible|Unbounded|Sub-?optimal|Time limit|Iteration limit|"
    r"Numerical trouble)\s+(?:solution|reached|encountered)?",
    re.MULTILINE,
)
_HIGHS_SIMPLEX_ITER_RE = re.compile(r"Simplex\s+iterations:\s*(\d+)")
_HIGHS_IPM_ITER_RE = re.compile(r"IPM\s+iterations:\s*(\d+)")
_HIGHS_PDLP_ITER_RE = re.compile(r"PDLP\s+iterations:\s*(\d+)")
# PDLP summary lines:
#   Primal infeas (abs/rel): 1.98e-07 / 3.99e-10
#   Dual infeas (abs/rel): 0.00e+00 / 0.00e+00
#   Duality gap (abs/rel): 1.20e-05 / 6.28e-08
_PDLP_PINF_RE = re.compile(
    r"Primal infeas \(abs/rel\):\s*([\d.eE+-]+)\s*/\s*([\d.eE+-]+)"
)
_PDLP_DINF_RE = re.compile(
    r"Dual infeas \(abs/rel\):\s*([\d.eE+-]+)\s*/\s*([\d.eE+-]+)"
)
_PDLP_GAP_RE = re.compile(r"Duality gap \(abs/rel\):\s*([\d.eE+-]+)\s*/\s*([\d.eE+-]+)")
_HIGHS_OBJ_RE = re.compile(r"Objective value\s*:\s*([-\d.eE+]+)")
# Per-iteration IPX line: "   42    8.56205215e+11  -1.39610557e+16   8.70e-02   4.24e-02  2.00e+00      10s"
# Columns: iter, primal_obj, dual_obj, pinf, dinf, gap, time
_IPM_ITER_LINE_RE = re.compile(
    r"^\s*(\d+)\s+"
    r"([-\d.eE+]+)\s+"
    r"([-\d.eE+]+)\s+"
    r"([\d.eE+-]+)\s+"
    r"([\d.eE+-]+)\s+"
    r"([\d.eE+-]+)\s+"
    r"(\d+)s\s*$",
    re.MULTILINE,
)


def _parse_highs_log(log_text: str) -> dict:
    """Pull out LP size and convergence info from a captured HiGHS log."""
    out = {
        "lp_rows": None,
        "lp_cols": None,
        "lp_nonzeros": None,
        "model_status": None,
        "highs_run_time_s": None,
        "simplex_iterations": None,
        "ipm_iterations": None,
        "ipm_final_pinf": None,
        "ipm_final_dinf": None,
        "ipm_final_gap": None,
        "objective_value": None,
    }
    m = _LP_SIZE_RE.search(log_text)
    if m:
        out["lp_rows"] = int(m.group(1))
        out["lp_cols"] = int(m.group(2))
        out["lp_nonzeros"] = int(m.group(3))
    else:
        m = _GUROBI_LP_SIZE_RE.search(log_text)
        if m:
            out["lp_rows"] = int(m.group(1))
            out["lp_cols"] = int(m.group(2))
            out["lp_nonzeros"] = int(m.group(3))
    m = _GUROBI_SIMPLEX_TIME_RE.search(log_text)
    if m:
        out["gurobi_iterations"] = int(m.group(1))
        out["gurobi_solver_time_s"] = float(m.group(2))
    m = _GUROBI_BARRIER_TIME_RE.search(log_text)
    if m:
        out["gurobi_barrier_iterations"] = int(m.group(1))
        out["gurobi_barrier_time_s"] = float(m.group(2))
    m = _GUROBI_OPTIMAL_OBJ_RE.search(log_text)
    if m:
        out["objective_value"] = float(m.group(1))
        out["model_status"] = out.get("model_status") or "Optimal"
    m = _GUROBI_STATUS_RE.search(log_text)
    if m and not out.get("model_status"):
        out["model_status"] = m.group(1).strip()
    m = _MODEL_STATUS_RE.search(log_text)
    if m:
        out["model_status"] = m.group(1).strip()
    m = _HIGHS_RUN_TIME_RE.search(log_text)
    if m:
        out["highs_run_time_s"] = float(m.group(1))
    m = _HIGHS_SIMPLEX_ITER_RE.search(log_text)
    if m:
        out["simplex_iterations"] = int(m.group(1))
    m = _HIGHS_IPM_ITER_RE.search(log_text)
    if m:
        out["ipm_iterations"] = int(m.group(1))
    m = _HIGHS_PDLP_ITER_RE.search(log_text)
    if m:
        out["pdlp_iterations"] = int(m.group(1))
    m = _PDLP_PINF_RE.search(log_text)
    if m:
        out["pdlp_final_pinf_abs"] = float(m.group(1))
        out["pdlp_final_pinf_rel"] = float(m.group(2))
    m = _PDLP_DINF_RE.search(log_text)
    if m:
        out["pdlp_final_dinf_abs"] = float(m.group(1))
        out["pdlp_final_dinf_rel"] = float(m.group(2))
    m = _PDLP_GAP_RE.search(log_text)
    if m:
        out["pdlp_final_gap_abs"] = float(m.group(1))
        out["pdlp_final_gap_rel"] = float(m.group(2))
    # Last IPM-style iteration row: extract final pinf, dinf, gap.
    ipm_lines = list(_IPM_ITER_LINE_RE.finditer(log_text))
    if ipm_lines:
        last = ipm_lines[-1]
        out["ipm_iterations_observed"] = int(last.group(1))
        out["ipm_final_pinf"] = float(last.group(4))
        out["ipm_final_dinf"] = float(last.group(5))
        out["ipm_final_gap"] = float(last.group(6))
    m = _HIGHS_OBJ_RE.search(log_text)
    if m:
        out["objective_value"] = float(m.group(1))
    return out


# ----- staged pipeline runner --------------------------------------------


def _run_staged_pipeline(
    config_path: Path,
    solver_options: dict | None = None,
    solver_name_override: str | None = None,
    carried_tranches_dir: Path | None = None,
    current_year: int | None = None,
    reducible_existing: bool = False,
    retention_floor_dir: Path | None = None,
    existing_fom_keeping: bool = False,
    co2_cap_t: float | None = None,
) -> dict:
    """Run the ISPyPSA pipeline with per-stage timing. Returns timings dict.

    If `carried_tranches_dir` is set, recursive-dynamic mode loads all
    surviving prior tranches (build_year < current_year, retirement-filtered)
    and injects them into the in-memory pypsa_friendly dict between
    translation and timeseries generation. This makes year-(t+1)'s solve see
    the accumulated brownfield stock built across the chain.
    """

    from analysis.model import apply_model_patches
    from analysis.model.flagged_exclusions_2026 import (
        exclude_ecaa_without_trace,
        exclude_flagged_new_entrants,
        normalize_2026_rez_ids,
    )
    from ispypsa.config import load_config
    from ispypsa.data_fetch import read_csvs, write_csvs
    from ispypsa.iasr_table_caching import build_local_cache
    from ispypsa.logging import configure_logging
    from ispypsa.pypsa_build import build_pypsa_network, save_pypsa_network
    from ispypsa.results import (
        extract_regions_and_zones_mapping,
        extract_tabular_results,
    )
    from ispypsa.templater import (
        create_ispypsa_inputs_template,
        load_manually_extracted_tables,
    )
    from ispypsa.translator import (
        create_pypsa_friendly_inputs,
        create_pypsa_friendly_timeseries_inputs,
    )

    configure_logging()
    config = load_config(config_path)

    run_root = Path(config.paths.run_directory) / (
        f"{config.paths.ispypsa_run_name}__{RUN_DIR_SUFFIX}"
    )
    ispypsa_inputs_dir = run_root / "ispypsa_inputs"
    pypsa_inputs_dir = run_root / "pypsa_friendly"
    ce_ts_dir = pypsa_inputs_dir / "capacity_expansion_timeseries"
    outputs_dir = run_root / "outputs"
    tables_dir = outputs_dir / "capacity_expansion_tables"
    for d in (ispypsa_inputs_dir, pypsa_inputs_dir, ce_ts_dir, outputs_dir, tables_dir):
        d.mkdir(parents=True, exist_ok=True)

    parsed_workbook_cache = Path(config.paths.parsed_workbook_cache)
    parsed_traces_directory = (
        Path(config.paths.parsed_traces_directory)
        / f"isp_{config.trace_data.dataset_year}"
    )
    workbook_path = Path(config.paths.workbook_path)
    parsed_workbook_cache.mkdir(parents=True, exist_ok=True)

    timings = {}

    t = time.perf_counter()
    # Cache sentinel uses the v7.4 canonical name; schema normalisation
    # produces this file for both v6.0 and v7.4 source workbooks.
    cache_sentinel = (
        parsed_workbook_cache
        / "existing_committed_anticipated_additional_generator_summary.csv"
    )
    if not cache_sentinel.exists():
        build_local_cache(
            parsed_workbook_cache,
            workbook_path,
            config.iasr_workbook_version,
            trace_directory=Path(config.paths.parsed_traces_directory),
        )
    iasr_tables = read_csvs(parsed_workbook_cache)
    manually_extracted_tables = load_manually_extracted_tables(
        config.iasr_workbook_version
    )
    timings["iasr_load_s"] = time.perf_counter() - t

    t = time.perf_counter()
    ispypsa_tables = create_ispypsa_inputs_template(
        config.scenario,
        config.network.nodes.regional_granularity,
        iasr_tables,
        manually_extracted_tables,
        config.filter_by_nem_regions,
        config.filter_by_isp_sub_regions,
    )
    ispypsa_tables = apply_model_patches(ispypsa_tables, config)
    # REQUIRED for the Draft 2026 trace store: drop VRE new entrants whose
    # (rez_id, isp_resource_type) has no 2026 trace (Q8 split; N10/N11 fixed
    # offshore). Left in, each crashes create_pypsa_friendly_timeseries at
    # _check_time_series. Gated on the 2026 dataset so it can't wrongly fire on
    # the 2024 store. See flagged_exclusions_2026 and isp_2026/TRACE_BASIS.md.
    if config.trace_data.dataset_year == 2026:
        # Normalize component rez_ids to 2026 REZ codes + connect the split Q8
        # sub-zones (data-determined), THEN drop only the genuinely-no-trace
        # candidates. Order matters: normalization maps Q8->Q8a (which has traces),
        # so the exclusion is left with only the N10/N11 fixed-offshore gap.
        ispypsa_tables = normalize_2026_rez_ids(ispypsa_tables)
        ispypsa_tables["new_entrant_generators"] = exclude_flagged_new_entrants(
            ispypsa_tables["new_entrant_generators"]
        )
        # ECAA VRE trace-coverage filter. The upstream filter_v74_ecaa_to_trace_coverage
        # is hardcoded to isp_2024 and no-ops for the 2026 traces, so 2026 ECAA VRE
        # trace filtering lives here. Runs AFTER normalize_2026_rez_ids (which applies
        # GENERATOR_NAME_2026_NORMALIZATION, e.g. Goyder North Wind Farm 1 -> Goyder
        # North Wind Farm) so name-mismatched generators are matched, not dropped.
        ispypsa_tables["ecaa_generators"] = exclude_ecaa_without_trace(
            ispypsa_tables["ecaa_generators"], parsed_traces_directory
        )
    write_csvs(ispypsa_tables, ispypsa_inputs_dir)
    timings["templating_s"] = time.perf_counter() - t

    t = time.perf_counter()
    pypsa_friendly = create_pypsa_friendly_inputs(config, ispypsa_tables)

    # Endogenous-retirement seam. Makes existing (ECAA) generators a
    # downward-only continuous capacity decision BEFORE carried tranches enter,
    # so it targets only the templated existing fleet (carried new-build
    # vintages, also non-extendable, stay fixed and are managed by
    # recursive_dynamic). keeping_cost=0 gives a strict mechanism with no
    # economics; the monotone retention floor caps this period at the prior
    # period's retained level. Runs before timeseries so the extendable rows
    # still get their p_max_pu / marginal_cost wiring downstream unchanged.
    if reducible_existing:
        from analysis.model.retirement import (
            load_retention_floor,
            make_existing_reducible,
        )

        floor = {}
        if retention_floor_dir is not None and current_year is not None:
            floor = load_retention_floor(retention_floor_dir, current_year)
        ecaa = ispypsa_tables["ecaa_generators"]
        existing_names = ecaa["generator"].tolist()
        if existing_fom_keeping:
            # Per-unit FOM ($/kW/yr -> $/MW/yr) becomes capital_cost on the
            # reducible existing units: the recurring keeping cost retirement
            # saves. Coal units run idle at low prices, so the keeping cost --
            # not operating savings -- is what makes shedding pay.
            keeping_cost = (
                ecaa.set_index("generator")["fom_$/kw/annum"] * 1000.0
            ).to_dict()
        else:
            keeping_cost = 0.0
        timings["retirement"] = make_existing_reducible(
            pypsa_friendly["generators"], existing_names, floor, keeping_cost
        )
        print(f"\n=== REDUCIBLE EXISTING === {timings['retirement']}", flush=True)

    # Recursive-dynamic injection seam. Carried rows must enter pypsa_friendly
    # BEFORE timeseries generation so marginal_cost parquets cover any carrier
    # that exists only in carried tranches, and so the parquet generated for
    # the base-tech mapping is computed at the CURRENT year's carbon price
    # (not the vintage year's). The carried row references the base mapping
    # by sharing the original new-entrant's marginal_cost field value.
    if carried_tranches_dir is not None and current_year is not None:
        from analysis.model.recursive_dynamic import (
            adjust_capacity_caps_for_carried,
            adjust_phes_build_limits_for_carried,
            inject_carried_tranches,
            load_tranches,
        )

        carried = load_tranches(carried_tranches_dir, before_year=current_year)
        timings["recursive_dynamic"] = inject_carried_tranches(pypsa_friendly, carried)
        # Net the carried capacity off any per-period capacity cap/floor RHS so the
        # constraint bounds the cumulative active fleet (carried + new), not just
        # the current vintage - fixes the recursive-dynamic x per-period-cap leak
        # (biomass cap reaching ~2x its ceiling; the storage/nuclear/gas floors).
        timings["capacity_cap_carried_adjust"] = adjust_capacity_caps_for_carried(
            pypsa_friendly, current_year
        )
        # Same cumulative-scope fix for the PHES menu's per-candidate workbook
        # build limits (p_nom_max columns, invisible to the RHS netting above).
        timings["phes_build_limit_carried_adjust"] = (
            adjust_phes_build_limits_for_carried(pypsa_friendly, current_year)
        )
        # Carried rows are aligned to whatever columns existed when their tranche
        # parquet was written, so vintages predating the CCS supply curve arrive
        # with no transport adder. Re-apply it by bus now that they are in, or
        # every carried CCS unit would dispose of its CO2 for free. The sink
        # grouping for the injectivity constraint is derived from bus at
        # constraint time and so is already immune to this.
        if "ccs_transport_adders" in pypsa_friendly:
            from ispypsa.translator.ccs_supply_curve import _add_ccs_transport_columns

            pypsa_friendly["generators"] = _add_ccs_transport_columns(
                pypsa_friendly["generators"], pypsa_friendly["ccs_transport_adders"]
            )

        print(
            f"\n=== RECURSIVE-DYNAMIC INJECTION === {timings['recursive_dynamic']} "
            f"| capacity-cap carried adjust: {timings['capacity_cap_carried_adjust']} "
            f"| PHES build-limit carried adjust: "
            f"{timings['phes_build_limit_carried_adjust']}",
            flush=True,
        )

    # Capacity-expansion modelling choice: zero p_min_pu so AEMO's
    # min-stable-level (a unit-commitment concept = the floor WHEN a unit is on)
    # is NOT enforced as a hard floor in this no-unit-commitment investment LP.
    # Applied to fresh AND carried generators. Without it, must-run floors (e.g.
    # new-entrant OCGT at 0.5) force overgeneration at high-solar low-demand hours
    # in the VRE-rich out-years -> infeasible (2045 IIS: SA/VIC summer-midday,
    # Generator-fix/ext-p-lower). Min-load belongs in the operational stage; the
    # AEMO values remain in the data, just not enforced as a hard LP floor here.
    pypsa_friendly["generators"]["p_min_pu"] = 0.0

    pypsa_friendly["snapshots"] = create_pypsa_friendly_timeseries_inputs(
        config,
        "capacity_expansion",
        ispypsa_tables,
        pypsa_friendly["generators"],
        parsed_traces_directory,
        ce_ts_dir,
    )
    write_csvs(pypsa_friendly, pypsa_inputs_dir)
    timings["translation_s"] = time.perf_counter() - t

    t = time.perf_counter()
    network = build_pypsa_network(
        pypsa_friendly,
        ce_ts_dir,
        config.filter_by_nem_regions or config.filter_by_isp_sub_regions,
    )
    timings["pypsa_build_s"] = time.perf_counter() - t

    # Intensity-x-demand map constraint, added straight to the linopy model built
    # by build_pypsa_network - the same seam the fuel supply curve uses - so no
    # model code changes. Coefficient construction mirrors
    # _constrain_fuel_burn_to_purchases (outer product of snapshot weights and
    # per-generator coefficients, built on the variable's own coords so xarray
    # aligns with linopy's snapshot MultiIndex).
    if co2_cap_t is not None:
        # Absolute annual CO2e cap on generation combustion. Coefficients are the
        # translator's isp_residual_co2_t_per_mwh (carrier total Scope-1 CO2e
        # factor x heat rate x (1 - capture_rate)), so CCS residual emissions at
        # the configured capture rate are INSIDE the cap and captured CO2 is not.
        import numpy as np
        import pandas as pd
        import xarray as xr

        weights = network.snapshot_weightings["generators"].to_numpy()
        gens_pf = pypsa_friendly["generators"].set_index("name")
        resid = pd.to_numeric(
            gens_pf["isp_residual_co2_t_per_mwh"], errors="coerce"
        ).fillna(0.0)
        resid = resid.reindex(network.generators.index).fillna(0.0)
        emitting = resid[resid > 0]
        p = network.model.variables.Generator_p.loc[:, emitting.index.to_list()]
        t_per_mw = xr.DataArray(
            np.outer(weights, emitting.to_numpy()), coords=p.coords, dims=p.dims
        )
        network.model.add_constraints(
            (p * t_per_mw).sum() <= float(co2_cap_t), name="co2_cap_annual_t"
        )
        timings["co2_cap_annual_t"] = float(co2_cap_t)
        print(
            f"\n=== CO2 CAP === {co2_cap_t:.1f} t CO2e/yr over "
            f"{len(emitting)} emitting generators",
            flush=True,
        )

    # HiGHS C++ writes directly to OS fd 1. When this runner is launched by
    # `msm solve`, fd 1 is the per-run log file - so HiGHS output is captured
    # without any in-process redirect. When run standalone, HiGHS output goes
    # to the terminal and the log parser will simply not find an LP-size line.
    print("\n=== SOLVE START ===", flush=True)
    if solver_options:
        print(f"solver_options: {solver_options}", flush=True)
    t = time.perf_counter()
    kwargs = {"solver_name": solver_name_override or config.solver}
    if solver_options:
        kwargs["solver_options"] = solver_options
    solve_ok = _solve_with_license_retry(network, kwargs)
    print("\n=== SOLVE END ===", flush=True)
    timings["solve_s"] = time.perf_counter() - t
    timings["solve_ok"] = solve_ok

    if not solve_ok:
        return timings

    t = time.perf_counter()
    save_pypsa_network(network, outputs_dir, "capacity_expansion")
    timings["save_network_s"] = time.perf_counter() - t

    # Realised residual CO2e and the cap dual. The linopy model is not persisted
    # with the NetCDF, so the dual must be read here, in-process, and written both
    # into the record and outputs/ for extraction.
    import pandas as pd

    pf_gens = pypsa_friendly["generators"].set_index("name")
    resid_full = (
        pd.to_numeric(pf_gens["isp_residual_co2_t_per_mwh"], errors="coerce")
        .fillna(0.0)
        .reindex(network.generators.index)
        .fillna(0.0)
    )
    dispatch_mwh = (
        network.generators_t.p.clip(lower=0)
        .mul(network.snapshot_weightings["generators"], axis=0)
        .sum()
    )
    timings["annual_residual_co2e_t"] = float((dispatch_mwh * resid_full).sum())

    if co2_cap_t is not None:
        constraint_report = {
            "objective_weight": float(
                network.investment_period_weightings["objective"].iloc[0]
            ),
            "annual_residual_co2e_t": timings["annual_residual_co2e_t"],
        }
        cname = "co2_cap_annual_t"
        try:
            constraint_report[f"{cname}_dual"] = float(
                network.model.constraints[cname].dual
            )
        except Exception as e:  # dual genuinely unavailable - report, not drop
            constraint_report[f"{cname}_dual"] = None
            constraint_report[f"{cname}_dual_error"] = f"{type(e).__name__}: {e}"
        timings["constraint_report"] = constraint_report
        (outputs_dir / "constraint_duals.json").write_text(
            json.dumps(constraint_report, indent=2, default=str)
        )
        print(f"\n=== CONSTRAINT DUALS === {constraint_report}", flush=True)

    t = time.perf_counter()
    results = extract_tabular_results(network, ispypsa_tables)
    results["regions_and_zones_mapping"] = extract_regions_and_zones_mapping(
        ispypsa_tables
    )
    for curve_table, carrier in [
        ("gas_supply_curve", "Gas"),
        ("biomass_supply_curve", "Biomass"),
    ]:
        if curve_table not in pypsa_friendly:
            continue
        usage = extract_fuel_supply_curve_usage(
            network, pypsa_friendly[curve_table], carrier
        )
        results[f"{curve_table}_usage"] = usage
        print(
            f"\n=== {carrier.upper()} SUPPLY CURVE USAGE (PJ by tranche) ===",
            flush=True,
        )
        print(usage.to_string(index=False), flush=True)
    write_csvs(results, tables_dir)
    timings["extract_results_s"] = time.perf_counter() - t

    # Sanity check: total annual generation per period (MWh).
    gen_dispatch = results["generator_dispatch"]
    weightings = network.snapshot_weightings["generators"]
    by_period = {}
    for period in network.investment_periods:
        period_snaps = [s for s in network.snapshots if s[0] == period]
        if not period_snaps:
            continue
        # Weight each dispatch_mw by snapshot weighting (h/snapshot)
        gen_t = network.generators_t.p
        period_p = gen_t.loc[period_snaps].clip(lower=0).sum(axis=1)
        weighted_mwh = (period_p * weightings.loc[period_snaps]).sum()
        by_period[int(period)] = float(weighted_mwh)
    timings["annual_generation_mwh_by_period"] = by_period

    return timings


def _host_provenance(threads: int | None) -> dict:
    """Where and how wide this solve ran, for the run record.

    Solve times are only comparable across records that name their host and thread
    count, and a Slurm job id ties the record back to the scheduler's own log.
    """
    return {
        "host": socket.gethostname(),
        "cpu_count": psutil.cpu_count(logical=True),
        "threads": threads,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
    }


def _git_provenance(repo_root: Path = PROJECT_ROOT) -> dict:
    """Record the exact checked-out source revision and whether it was modified.

    Git metadata may be unavailable in an exported source tree or a damaged
    checkout. The run record states that explicitly rather than inventing a
    revision or treating an unknown worktree as clean.
    """
    provenance = {
        "source_git_status": "available",
        "source_git_commit": None,
        "source_git_dirty": None,
    }
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if not commit:
            raise RuntimeError("git rev-parse HEAD returned an empty commit")
        provenance["source_git_commit"] = commit

        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=normal"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        provenance["source_git_dirty"] = bool(status.strip())
    except (OSError, subprocess.CalledProcessError, RuntimeError) as error:
        provenance["source_git_status"] = "unavailable"
        stderr = getattr(error, "stderr", None)
        detail = (
            stderr.strip() if isinstance(stderr, str) and stderr.strip() else str(error)
        )
        provenance["source_git_error"] = f"{type(error).__name__}: {detail}"
    return provenance


def _config_provenance(config_path: Path) -> dict:
    """Hash the exact input YAML without reading or hashing external trace data."""
    try:
        digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
    except OSError as error:
        return {
            "input_config_sha256_status": "unavailable",
            "input_config_sha256": None,
            "input_config_sha256_error": f"{type(error).__name__}: {error}",
        }
    return {
        "input_config_sha256_status": "available",
        "input_config_sha256": digest,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--run-id", required=True)
    ap.add_argument(
        "--use-pdlp",
        action="store_true",
        help="Use HiGHS PDLP (primal-dual hybrid gradient) solver",
    )
    ap.add_argument(
        "--pdlp-tolerance",
        type=float,
        default=None,
        help="Set pdlp_optimality_tolerance + primal/dual feasibility "
        "tolerances all to this value (default uses HiGHS defaults)",
    )
    ap.add_argument(
        "--use-gurobi",
        action="store_true",
        help="Use Gurobi (overrides config.solver = highs); default Gurobi settings",
    )
    ap.add_argument(
        "--gurobi-bar-conv-tol",
        type=float,
        default=None,
        help="Set Gurobi BarConvTol (default 1e-8); e.g. 1e-3 for relaxed run",
    )
    ap.add_argument(
        "--gurobi-threads",
        type=int,
        default=None,
        help="Set Gurobi Threads (cores per solve). Cap when running multiple "
        "trajectories concurrently so concurrent x threads <= cores with "
        "headroom; default (unset) lets Gurobi use all cores (right for a "
        "single solve).",
    )
    ap.add_argument(
        "--highs-threads",
        type=int,
        default=None,
        help="Set the HiGHS 'threads' option for simplex, IPM and PDLP. Pin to the "
        "job's core allocation on a shared node; ignored with --use-gurobi.",
    )
    ap.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Directory for the solver log and JSON record (logs/, records/); "
        "the config's paths.run_directory should sit under the same root.",
    )
    ap.add_argument(
        "--gurobi-method",
        type=int,
        default=None,
        help="Set Gurobi Method (0=primal simplex, 1=dual simplex, 2=barrier, "
        "3=concurrent, 4=det concurrent).",
    )
    ap.add_argument(
        "--carried-tranches-dir",
        type=Path,
        default=None,
        help="Recursive-dynamic mode: directory holding per-year tranche "
        "parquets from prior solves in this chain. Requires --current-year.",
    )
    ap.add_argument(
        "--current-year",
        type=int,
        default=None,
        help="The investment year being solved. Used by recursive-dynamic "
        "mode to retirement-filter carried tranches, and by "
        "reducible-existing mode to load the prior-period retention floor.",
    )
    ap.add_argument(
        "--reducible-existing",
        action="store_true",
        help="Endogenous retirement: make existing (ECAA) generators a "
        "downward-only continuous capacity decision (extendable, "
        "p_nom_min=0, p_nom_max=installed, capital_cost=keeping-cost). "
        "p_nom_opt < installed is economic retirement. LP, not MIP.",
    )
    ap.add_argument(
        "--retention-floor-dir",
        type=Path,
        default=None,
        help="Directory holding per-year retained-existing floors from prior "
        "solves in this chain; caps this period's existing capacity at the "
        "prior retained level (monotone retirement). Requires --current-year.",
    )
    ap.add_argument(
        "--existing-fom-keeping",
        action="store_true",
        help="Route each existing unit's OWN FOM (ecaa fom_$/kw/annum "
        "-> $/MW/yr) as its capital_cost keeping-cost, instead of keeping the "
        "unit for free. This is the recurring cost retirement saves.",
    )
    ap.add_argument(
        "--co2-cap-t",
        type=float,
        default=None,
        help="Absolute annual CO2e cap (tonnes) on generation combustion, added "
        "as a linear constraint over Generator_p with the translator's "
        "isp_residual_co2_t_per_mwh coefficients (CCS residual inside the cap, "
        "captured CO2 outside). The constraint's dual is recorded in the run "
        "record and outputs/constraint_duals.json. Default: no cap.",
    )
    args = ap.parse_args()
    if args.carried_tranches_dir is not None and args.current_year is None:
        ap.error("--carried-tranches-dir requires --current-year.")
    if args.retention_floor_dir is not None and args.current_year is None:
        ap.error("--retention-floor-dir requires --current-year.")
    solver_options = None
    solver_name_override = None
    if args.use_pdlp:
        solver_options = {"solver": "pdlp"}
        if args.pdlp_tolerance is not None:
            solver_options["pdlp_optimality_tolerance"] = args.pdlp_tolerance
            solver_options["primal_feasibility_tolerance"] = args.pdlp_tolerance
            solver_options["dual_feasibility_tolerance"] = args.pdlp_tolerance
    elif args.use_gurobi:
        solver_name_override = "gurobi"
        gurobi_opts = {}
        if args.gurobi_bar_conv_tol is not None:
            gurobi_opts["BarConvTol"] = args.gurobi_bar_conv_tol
        if args.gurobi_threads is not None:
            gurobi_opts["Threads"] = args.gurobi_threads
        if args.gurobi_method is not None:
            gurobi_opts["Method"] = args.gurobi_method
        if gurobi_opts:
            solver_options = gurobi_opts
    if args.highs_threads is not None and not args.use_gurobi:
        solver_options = solver_options or {}
        solver_options["threads"] = args.highs_threads

    layout = OutputLayout(args.output_root)
    log_path = layout.log(args.run_id)
    record_path = layout.record(args.run_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.parent.mkdir(parents=True, exist_ok=True)
    # `msm solve` opened this log and redirected this process's stdout into it, so
    # the file is never opened here for writing; it is only read back after the
    # solve to parse the solver's own lines out of it.

    poller = MemoryPoller(interval_s=2.0)
    poller.start()

    record = {
        "run_id": args.run_id,
        "config": str(args.config),
        "solver_options": solver_options,
        "started_at": time.time(),
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **_git_provenance(),
        **_config_provenance(args.config),
        **_host_provenance(
            args.gurobi_threads if args.use_gurobi else args.highs_threads
        ),
    }

    t_total = time.perf_counter()
    try:
        timings = _run_staged_pipeline(
            args.config,
            solver_options=solver_options,
            solver_name_override=solver_name_override,
            carried_tranches_dir=args.carried_tranches_dir,
            current_year=args.current_year,
            reducible_existing=args.reducible_existing,
            retention_floor_dir=args.retention_floor_dir,
            existing_fom_keeping=args.existing_fom_keeping,
            co2_cap_t=args.co2_cap_t,
        )
        record.update(timings)
        record["wall_clock_s"] = time.perf_counter() - t_total
        record["status"] = "completed"
    except Exception as e:
        record["status"] = "failed"
        record["exception"] = f"{type(e).__name__}: {e}"
        record["traceback"] = traceback.format_exc()
        record["wall_clock_s"] = time.perf_counter() - t_total
    finally:
        poller.stop()
        record["peak_rss_bytes"] = poller.peak_rss_bytes
        record["peak_rss_gib"] = poller.peak_rss_bytes / (1024**3)

    if log_path.exists():
        log_text = log_path.read_text(errors="replace")
        record.update(_parse_highs_log(log_text))

    record_path.write_text(json.dumps(record, indent=2, default=str))
    print(
        json.dumps(
            {k: v for k, v in record.items() if k != "traceback"}, indent=2, default=str
        )
    )


if __name__ == "__main__":
    main()
