"""Fraction-comparison (wedge) subset: intensity cap vs minimum renewable share.

Matching rule: at each matched coordinate (year, d = 1.00, cap mult in
{1.0, 0.25, 0.05}) the share-constrained cell's minimum share r is set to the
r_total REALISED by the already-solved intensity-capped cell at that
coordinate. The two solves are then comparable at the coordinate: one hits an
emissions target, the other hits the renewable share that emissions target
happened to produce. The difference between them (cost, mix, realised
intensity) measures the CCS-plus-abatement wedge — what a renewables-share
representation forgoes against an intensity-based one. Unabated-gas + coal
substitution inside the non-renewable remainder shows up as the share cell's
higher realised intensity.

Runs cells sequentially (each needs the matched grid cell solved first, and
Gurobi has two licence seats shared with the grid).

Usage:
    uv run python analysis/intensity_demand_map/scripts/run_wedge.py --years 2040
"""

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analysis.intensity_demand_map.scripts.extract_cell import (
    extract_cell,  # noqa: E402
)

RECORDS = Path("outputs/records")
SCRIPTS = Path(__file__).parent
MATCHED_CAP_KEYS = ["i100", "i025", "i005"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", default=[2030, 2040, 2050])
    parser.add_argument("--budget-min", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    for year in args.years:
        for cap_key in MATCHED_CAP_KEYS:
            matched_id = f"idm_d100_{cap_key}_{year}"
            wedge_id = f"idm_d100_s{cap_key[1:]}_{year}"
            if not (RECORDS / f"{matched_id}.json").exists():
                print(f"skip {wedge_id}: matched cell {matched_id} not solved")
                continue
            if (RECORDS / f"{wedge_id}.json").exists():
                print(f"skip {wedge_id}: already solved")
                continue
            r_total = extract_cell(matched_id)["r_total_pct"] / 100.0
            command = [
                sys.executable,
                str(SCRIPTS / "run_cell.py"),
                "--run-id",
                wedge_id,
                "--year",
                str(year),
                "--demand-level",
                "d100",
                "--share-min",
                f"{r_total:.6f}",
                "--solver",
                "gurobi",
                "--budget-min",
                str(args.budget_min),
            ]
            print(f"wedge {wedge_id}: share_min={r_total:.4f} (from {matched_id})")
            if args.dry_run:
                continue
            rc = subprocess.run(command).returncode
            print(f"  -> rc={rc}")


if __name__ == "__main__":
    main()
