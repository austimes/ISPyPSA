"""Drive the 4x4 carbon price x demand sweep: 16 cells, myopic over 2030/2040/2050.

Each cell is an independent recursive-dynamic chain (2030 greenfield, 2040 carrying
2030's tranche, 2050 carrying both), so cells can run concurrently. Within a cell the
three periods are sequential by construction.

Sampling is the Addendum 1 configuration: thirteen evenly spaced weeks at 30-minute
resolution, one per four-week block, with the named stress weeks suppressed so the
sample is not stress-weighted (see --no-named-weeks in run_myopic.py).

CCS is a single flat transport-and-storage adder; the tranche machinery is excluded by
passing --ccs-supply-curve none, which suppresses the whole ccs_supply_curve config
block including its spatial transport pricing (run_myopic.py:201).

Usage:
    uv run python analysis/demand_carbon_sweep/scripts/run_sweep.py --width 4
    uv run python analysis/demand_carbon_sweep/scripts/run_sweep.py --dry-run
"""

import argparse
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CARBON_PRICES = [0, 150, 300, 550]
DEMAND_LEVELS = ["d087", "d100", "d110", "d123"]
PERIODS = ["2030", "2040", "2050"]
WEEKS = ["2", "6", "10", "14", "18", "22", "26", "30", "34", "38", "42", "46", "50"]
CCS_FLAT_ADDER = "89.93"  # A$/tCO2, fleet-weighted; RETURN_MEMO.md s2.4
TRACE_ROOT = Path(
    "C:/Users/van538/AppData/Local/Temp/5/claude/"
    "c--Users-van538-GitHub-ISPyPSA/c1558bce-da07-46a1-8051-03c3ed5f9b28/scratchpad"
)
LOG_DIR = Path("analysis/benchmarks/logs")


def _cell_command(carbon_price: int, level: str, threads: int, budget_min: int) -> list[str]:
    return [
        "uv", "run", "python", "analysis/benchmarks/run_myopic.py",
        "--run-id", f"sweep_c{carbon_price}_{level}",
        "--periods", *PERIODS,
        "--recursive-dynamic",
        "--reducible-existing", "--existing-fom-keeping",
        "--carbon-price", str(carbon_price),
        "--tns-price", CCS_FLAT_ADDER,
        "--ccs-supply-curve", "none",
        "--dataset-year", "2026", "--iasr-final",
        "--parsed-traces-directory", str(TRACE_ROOT / f"traces_{level}"),
        "--rep-weeks", *WEEKS,
        "--no-named-weeks",
        "--use-gurobi", "--gurobi-method", "2", "--gurobi-crossover", "0",
        "--gurobi-bar-conv-tol", "1e-6",
        "--gurobi-threads", str(threads),
        "--budget-min", str(budget_min),
    ]


def _run_cell(carbon_price: int, level: str, threads: int, budget_min: int) -> dict:
    run_id = f"sweep_c{carbon_price}_{level}"
    command = _cell_command(carbon_price, level, threads, budget_min)
    started = time.time()
    log_path = LOG_DIR / f"{run_id}_driver.log"
    with log_path.open("w") as handle:
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT)
    return {
        "run_id": run_id,
        "returncode": completed.returncode,
        "wall_s": round(time.time() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=4, help="Cells run concurrently")
    parser.add_argument("--threads", type=int, default=26, help="Gurobi threads per cell")
    parser.add_argument("--budget-min", type=int, default=180, help="Per-period limit")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--only-carbon", type=int, nargs="+", default=None,
        help="Restrict to these carbon prices (for staged launches)",
    )
    args = parser.parse_args()

    prices = args.only_carbon if args.only_carbon else CARBON_PRICES
    cells = [(price, level) for price in prices for level in DEMAND_LEVELS]

    if args.dry_run:
        for price, level in cells:
            print(" ".join(_cell_command(price, level, args.threads, args.budget_min)))
            print()
        print(f"{len(cells)} cells, width {args.width}, {args.threads} threads each")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"launching {len(cells)} cells, width {args.width}, "
          f"{args.threads} threads each, {args.budget_min} min per period")
    with ThreadPoolExecutor(max_workers=args.width) as pool:
        futures = [
            pool.submit(_run_cell, price, level, args.threads, args.budget_min)
            for price, level in cells
        ]
        for future in futures:
            result = future.result()
            status = "ok" if result["returncode"] == 0 else f"rc={result['returncode']}"
            print(f"  {result['run_id']:<24} {status:<8} {result['wall_s']:>9.1f} s")


if __name__ == "__main__":
    main()
