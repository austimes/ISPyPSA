"""Stage 1 pilot: three sequential cells at (2040, d = 1.00).

1. idm_d100_u_2040     uncapped — reproduction check against the conditioning
                       chain's own 2040 solve (sweep_c0_d100_2040, PDLP 3e-3)
2. idm_d100_i100_2040  cap at the conditioned realised intensity (should be
                       non-binding or marginally binding)
3. idm_d100_i050_2040  cap at 0.5x that intensity (must bind; dual finite)

Solver per the brief: Gurobi barrier, crossover ON (auto), BarConvTol 1e-8.
Runtime gate: any cell over 180 min stops the stage.

Caps come from stage0_conditioning.csv (residual_co2e_t for 2040), so the cap
basis is exactly the conditioned state's own realised emissions.

Usage:
    uv run python analysis/intensity_demand_map/scripts/run_pilot.py [--solver gurobi]
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

SCRIPTS = Path(__file__).parent
STAGE0 = SCRIPTS.parent / "stage0_conditioning.csv"


def _cell(run_id: str, cap_t: float | None, solver: str, budget_min: int) -> int:
    command = [
        sys.executable, str(SCRIPTS / "run_cell.py"),
        "--run-id", run_id, "--year", "2040", "--demand-level", "d100",
        "--solver", solver, "--budget-min", str(budget_min),
    ]
    if cap_t is not None:
        command += ["--cap-t", str(cap_t)]
    print(f"\n=== pilot cell {run_id} (cap_t={cap_t}) ===", flush=True)
    return subprocess.run(command).returncode


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", choices=["gurobi", "pdlp"], default="gurobi")
    parser.add_argument("--budget-min", type=int, default=180)
    parser.add_argument("--cells", nargs="+", default=["u", "i100", "i050"])
    args = parser.parse_args()

    stage0 = pd.read_csv(STAGE0).set_index("year")
    e2040 = float(stage0.loc[2040, "residual_co2e_t"])
    caps = {"u": None, "i100": e2040, "i050": 0.5 * e2040}

    for key in args.cells:
        rc = _cell(f"idm_d100_{key}_2040", caps[key], args.solver, args.budget_min)
        if rc != 0:
            print(f"pilot cell {key} FAILED (rc={rc}) — stopping the stage", flush=True)
            sys.exit(1)
    print("\npilot complete", flush=True)


if __name__ == "__main__":
    main()
