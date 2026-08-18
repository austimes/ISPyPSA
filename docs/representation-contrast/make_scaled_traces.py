"""Build a parsed-trace root whose demand is scaled, leaving VRE traces untouched.

Used only for the representation-contrast demand perturbation. Nothing in the
repository is modified: the scaled root lives in the scratchpad and is passed to
run_myopic via the existing --parsed-traces-directory flag.

VRE (project/, zone/) are junctioned back to the real traces so the pair differs
in demand and nothing else.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

SRC = Path("data/trace_data_final").resolve()
DATASET = "isp_2026"
REF_YEAR = 2018
SCENARIO = "scenario=Step%20Change"


def _junction(link: Path, target: Path):
    """Windows directory junction (no admin needed), so VRE traces aren't copied."""
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=True,
        capture_output=True,
    )


def _scaled_demand(scale: float, out_dir: Path):
    src = SRC / DATASET / "demand" / SCENARIO / f"reference_year={REF_YEAR}"
    df = pd.read_parquet(src / "data_0.parquet")
    before = df["value"].sum()
    df["value"] = df["value"] * scale
    out_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_dir / "data_0.parquet", index=False)
    print(f"  demand sum {before:,.0f} -> {df['value'].sum():,.0f} MW-halfhours")


def build(scale: float, root: Path):
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    dataset_root = root / DATASET
    dataset_root.mkdir(parents=True)
    print(f"building {root} (demand x{scale})")
    _scaled_demand(scale, dataset_root / "demand" / SCENARIO / f"reference_year={REF_YEAR}")
    for vre in ("project", "zone"):
        _junction(dataset_root / vre, SRC / DATASET / vre)
        print(f"  junction {vre} -> real traces")


if __name__ == "__main__":
    scale = float(sys.argv[1])
    build(scale, Path(sys.argv[2]).resolve())
