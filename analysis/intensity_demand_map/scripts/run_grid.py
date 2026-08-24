"""Launch the intensity x demand map grid (Stage 2).

Realised cell list per year (27 planned coordinates, 26 solves):

  full intensity ladder  {1.5, 1.0, 0.5, 0.25, 0.10, 0.05} x iota_planned
                         at d in {1.00, 1.10, 1.50}
  reduced ladder         {1.0, 0.25, 0.05} x iota_planned
                         at d in {1.05, 1.20, 1.35}

The 1.5x overflow rung runs at the three full-ladder demand levels. At d = 1.00
the 1.5x cap is provably slack (the uncapped conditioned solve realises exactly
iota_planned), so that coordinate is reported from the pilot's uncapped cell
rather than re-solved; at higher demand the cap may bind and is solved.

Cap arithmetic: cap_t(year, mult, level) = iota_planned(year) x mult x
delivered_MWh(year, d100) x level, where iota_planned and the conditioned
delivered energy come from stage0_conditioning.csv. Demand scaling is linear on
a fixed week set, so delivered energy scales exactly with the level.

Cells run through run_cell.py (conditioned single-year solves) with a bounded
worker pool. Gurobi runs are capped at width 2 (CSIRO token server seats).

Usage:
    uv run python analysis/intensity_demand_map/scripts/run_grid.py --year 2040
    uv run python analysis/intensity_demand_map/scripts/run_grid.py --dry-run
"""

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).parent
STAGE0 = SCRIPTS.parent / "stage0_conditioning.csv"
RECORDS = Path("analysis/benchmarks/records")

FULL_LADDER = {"i150": 1.5, "i100": 1.0, "i050": 0.5, "i025": 0.25,
               "i010": 0.10, "i005": 0.05}
REDUCED_LADDER = {"i100": 1.0, "i025": 0.25, "i005": 0.05}
FULL_DEMANDS = {"d100": 1.00, "d110": 1.10, "d150": 1.50}
REDUCED_DEMANDS = {"d105": 1.05, "d120": 1.20, "d135": 1.35}
YEARS = [2030, 2040, 2050]


def cell_list(years: list[int]) -> list[dict]:
    stage0 = pd.read_csv(STAGE0).set_index("year")
    cells = []
    for year in years:
        base_emissions_t = float(stage0.loc[year, "residual_co2e_t"])
        for demands, ladder in (
            (FULL_DEMANDS, FULL_LADDER),
            (REDUCED_DEMANDS, REDUCED_LADDER),
        ):
            for level_key, level in demands.items():
                for cap_key, mult in ladder.items():
                    if level_key == "d100" and cap_key == "i150":
                        continue  # provably slack; reported from the uncapped pilot
                    cells.append(
                        {
                            "run_id": f"idm_{level_key}_{cap_key}_{year}",
                            "year": year,
                            "demand_level": level_key,
                            "cap_key": cap_key,
                            "cap_t": base_emissions_t * mult * level,
                        }
                    )
    return cells


def _run_cell(cell: dict, solver: str, budget_min: int) -> dict:
    command = [
        sys.executable, str(SCRIPTS / "run_cell.py"),
        "--run-id", cell["run_id"],
        "--year", str(cell["year"]),
        "--demand-level", cell["demand_level"],
        "--cap-t", str(cell["cap_t"]),
        "--solver", solver,
        "--budget-min", str(budget_min),
    ]
    started = time.time()
    completed = subprocess.run(command, capture_output=True, text=True)
    return {
        "run_id": cell["run_id"],
        "returncode": completed.returncode,
        "wall_s": round(time.time() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", default=YEARS)
    parser.add_argument("--solver", choices=["gurobi", "pdlp"], default="gurobi")
    parser.add_argument("--width", type=int, default=2,
                        help="Concurrent cells (Gurobi: <= 2 licence seats)")
    parser.add_argument("--budget-min", type=int, default=300)
    parser.add_argument("--skip-solved", action="store_true",
                        help="Skip cells whose record already reports completed")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cells = cell_list(args.years)
    if args.skip_solved:
        def _done(cell):
            path = RECORDS / f"{cell['run_id']}.json"
            return path.exists() and '"completed"' in path.read_text()
        cells = [c for c in cells if not _done(c)]

    if args.dry_run:
        for cell in cells:
            print(f"{cell['run_id']:<24} cap {cell['cap_t'] / 1e6:10.3f} Mt")
        print(f"{len(cells)} cells, width {args.width}, solver {args.solver}")
        return

    print(f"launching {len(cells)} cells, width {args.width}, solver {args.solver}")
    with ThreadPoolExecutor(max_workers=args.width) as pool:
        futures = [
            pool.submit(_run_cell, cell, args.solver, args.budget_min)
            for cell in cells
        ]
        for future in futures:
            result = future.result()
            status = "ok" if result["returncode"] == 0 else f"rc={result['returncode']}"
            print(f"  {result['run_id']:<24} {status:<8} {result['wall_s']:>9.1f} s",
                  flush=True)


if __name__ == "__main__":
    main()
