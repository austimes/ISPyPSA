"""Run one conditioned single-year cell of the intensity x demand map.

Each cell is a comparative-statics solve at one milestone year, conditioned on
the current-policy reference chain (`sweep_c0_d100`: $0/t carbon, Step Change
demand): the chain's saved new-build tranches and retention floors for years
BEFORE the solve year are injected read-only, exactly the state the chain's own
solve of that year saw. Cells never write back tranches or retention, so the
reference state cannot be mutated by the map.

Economics are held identical to the reference chain (carbon price 0, flat CCS
T&S adder A$89.93/t, central gas and biomass supply curves, no CCS injectivity
tranches): the only interventions are the demand trace directory, the absolute
annual CO2e cap (--cap-t) or minimum renewable share (--share-min), and the
solver. Sampling is the previous sweep's validated demand-matched 13 weeks at
30 minutes unless --full-year.

Usage:
    uv run python analysis/intensity_demand_map/scripts/run_cell.py \
        --run-id map2040_d100_i050 --year 2040 --demand-level d100 \
        --cap-t 21600000 --solver gurobi --budget-min 180
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analysis.benchmarks.output_layout import OutputLayout  # noqa: E402
from analysis.benchmarks.run_myopic import _write_period_config  # noqa: E402

BENCH = Path("analysis/benchmarks")
LAYOUT = OutputLayout()
LOGS = LAYOUT.logs
RECORDS = LAYOUT.records
CONDITIONING_CHAIN = LAYOUT.chain_dir("sweep_c0_d100")
TRACE_ROOT = Path(
    "C:/Users/van538/AppData/Local/Temp/5/claude/"
    "c--Users-van538-GitHub-ISPyPSA/c3ca439d-74e8-4532-aba1-90d19353fa8e/scratchpad"
)
WEEKS = [1, 6, 10, 14, 19, 22, 26, 32, 35, 39, 41, 45, 50]
CCS_FLAT_ADDER = 89.93
GAS_CURVE = "analysis/gas_market/gas_supply_curve_central.csv"
BIOMASS_CURVE = "analysis/bioenergy_market/biomass_supply_curve_central.csv"


def _runner_command(args: argparse.Namespace, cfg: Path) -> str:
    flags = ""
    if args.solver == "gurobi":
        # Stage 1 specification: barrier with crossover ON (default Crossover
        # auto runs it; deliberately NOT passing Crossover 0) at BarConvTol 1e-8.
        flags += f" --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol {args.gurobi_bar_conv_tol}"
        if args.gurobi_threads:
            flags += f" --gurobi-threads {args.gurobi_threads}"
    elif args.solver == "pdlp":
        flags += f" --use-pdlp --pdlp-tolerance {args.pdlp_tolerance}"
    flags += (
        f' --carried-tranches-dir "{CONDITIONING_CHAIN / "tranches"}"'
        f' --retention-floor-dir "{CONDITIONING_CHAIN / "retention"}"'
        f" --current-year {args.year}"
        " --reducible-existing --existing-fom-keeping"
    )
    if args.cap_t is not None:
        flags += f" --co2-cap-t {args.cap_t}"
    if args.share_min is not None:
        flags += f" --renewable-share-min {args.share_min}"
    log_path = LOGS / f"{args.run_id}.log"
    return (
        f'"{sys.executable}" -u "{BENCH / "instrumented_runner.py"}" '
        f'--config "{cfg}" --run-id "{args.run_id}" --archetype cost_optimal{flags} '
        f'> "{log_path}" 2>&1'
    )


def _run_with_budget(command: str, budget_min: float) -> dict:
    """Launch, poll, and kill past budget — mirrors run_myopic._run_one_period."""
    proc = subprocess.Popen(command, shell=True)
    psproc = psutil.Process(proc.pid)
    started = time.time()
    budget_s = budget_min * 60
    while True:
        rc = proc.poll()
        if rc is not None:
            return {"returncode": rc, "wall_s": time.time() - started}
        if time.time() - started > budget_s:
            for child in psproc.children(recursive=True):
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    pass
            psproc.kill()
            proc.wait(timeout=30)
            return {
                "returncode": None,
                "status": "timed_out",
                "wall_s": time.time() - started,
            }
        time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--year", type=int, required=True, choices=[2030, 2040, 2050])
    parser.add_argument(
        "--demand-level",
        required=True,
        help="d100/d105/d110/d120/d135/d150 (a built trace dir)",
    )
    parser.add_argument(
        "--cap-t",
        type=float,
        default=None,
        help="Absolute annual CO2e cap in tonnes (omit = uncapped)",
    )
    parser.add_argument(
        "--share-min",
        type=float,
        default=None,
        help="Minimum renewable share 0-1 (wedge subset)",
    )
    parser.add_argument("--solver", choices=["gurobi", "pdlp"], default="gurobi")
    parser.add_argument("--gurobi-bar-conv-tol", type=float, default=1e-8)
    parser.add_argument("--gurobi-threads", type=int, default=None)
    parser.add_argument("--pdlp-tolerance", type=float, default=3e-3)
    parser.add_argument("--budget-min", type=float, default=180)
    parser.add_argument(
        "--full-year",
        action="store_true",
        help="Full-year chronology (low-intensity tail cells)",
    )
    args = parser.parse_args()

    trace_dir = TRACE_ROOT / f"traces_{args.demand_level}"
    assert trace_dir.exists(), f"trace directory missing: {trace_dir}"

    cfg = _write_period_config(
        args.run_id,
        args.year,
        regions=None,
        rep_weeks=None if args.full_year else WEEKS,
        full_year=args.full_year,
        named_weeks=False,
        resolution_min=30,
        carbon_price=0.0,
        tns_price=CCS_FLAT_ADDER,
        gas_supply_curve_csv=GAS_CURVE,
        biomass_supply_curve_csv=BIOMASS_CURVE,
        ccs_sink_tranches_csv=None,
        ccs_transport_csv=None,
        # as_posix: the path lands inside a double-quoted YAML scalar and a
        # Windows backslash path makes "C:\Users\..." a bad unicode escape.
        parsed_traces_directory=trace_dir.as_posix(),
        dataset_year=2026,
        iasr_final=True,
    )

    LOGS.mkdir(parents=True, exist_ok=True)
    command = _runner_command(args, cfg)
    print(
        f"launching {args.run_id}: year={args.year} level={args.demand_level} "
        f"cap_t={args.cap_t} share_min={args.share_min} solver={args.solver}"
    )
    result = _run_with_budget(command, args.budget_min)
    print(f"finished {args.run_id}: {result}")

    record_path = RECORDS / f"{args.run_id}.json"
    solve_failed = False
    if record_path.exists():
        record = json.loads(record_path.read_text())
        for key in (
            "status",
            "model_status",
            "objective_value",
            "solve_s",
            "wall_clock_s",
            "co2_cap_annual_t",
            "annual_residual_co2e_t",
            "constraint_report",
        ):
            if key in record:
                print(f"  {key}: {record[key]}")
        # solve_ok=False (e.g. a license-server connection error that isn't a
        # retryable "use limit" case) leaves the pipeline returning early: the
        # process still exits 0 and the record still says status="completed",
        # with no network ever saved. model_status/objective_value both None
        # is the signature — distinct from a PDLP cell, which always sets
        # model_status (even "Unknown") when a solve actually ran.
        if (
            record.get("status") == "completed"
            and record.get("model_status") is None
            and record.get("objective_value") is None
        ):
            solve_failed = True
            print(
                f"  SOLVE FAILED SILENTLY (solve_ok=False, no network saved) "
                f"-- see logs/{args.run_id}.log for the exception"
            )
    else:
        solve_failed = True
    if (
        result.get("status") == "timed_out"
        or result.get("returncode") not in (0, None)
        or solve_failed
    ):
        sys.exit(1)


if __name__ == "__main__":
    main()
