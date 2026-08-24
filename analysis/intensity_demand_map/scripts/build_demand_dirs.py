"""Build one rewritten parsed-demand trace directory per map demand level.

Same design as the previous sweep's builder (demand_carbon_sweep): the demand
axis is implemented entirely via the --parsed-traces-directory route — no model
code, schema or committed data changes. Every level INCLUDING 1.0 goes through
the identical read-scale-write round trip so the round trip cannot masquerade
as a demand signal. VRE traces (project/, zone/) are symlinked to the single
source store so wind and solar are bit-identical between levels.

The map's levels are uniform multiples of the conditioned demand (Step Change /
POE50 / OPSO_MODELLING), per the brief: {1.00, 1.05, 1.10, 1.20, 1.35, 1.50}.
Unlike the previous sweep these are presentation levels, not ISP scenarios.

Usage:
    uv run python analysis/intensity_demand_map/scripts/build_demand_dirs.py
"""

import os
import shutil
from pathlib import Path

import pandas as pd

SOURCE = Path("data/trace_data_final/isp_2026")
OUT_ROOT = Path(
    "C:/Users/van538/AppData/Local/Temp/5/claude/"
    "c--Users-van538-GitHub-ISPyPSA/c3ca439d-74e8-4532-aba1-90d19353fa8e/scratchpad"
)
REF_YEAR = 2018
LINKED_SUBDIRS = ("project", "zone")

LEVELS = {
    "d100": 1.00,
    "d105": 1.05,
    "d110": 1.10,
    "d120": 1.20,
    "d135": 1.35,
    "d150": 1.50,
}


def _demand_partitions() -> list[Path]:
    return sorted((SOURCE / "demand").glob(f"*/reference_year={REF_YEAR}"))


def _write_scaled_demand(out_dir: Path, scalar: float) -> tuple[float, float]:
    source_mwh = 0.0
    scaled_mwh = 0.0
    for partition in _demand_partitions():
        target = out_dir / "demand" / partition.relative_to(SOURCE / "demand")
        target.mkdir(parents=True, exist_ok=True)
        for parquet in sorted(partition.glob("*.parquet")):
            frame = pd.read_parquet(parquet)
            source_mwh += frame["value"].sum() * 0.5
            frame["value"] = frame["value"] * scalar
            scaled_mwh += frame["value"].sum() * 0.5
            frame.to_parquet(target / parquet.name, index=False)
    return source_mwh, scaled_mwh


def _link_vre(out_dir: Path) -> None:
    for subdir in LINKED_SUBDIRS:
        link = out_dir / subdir
        if link.is_symlink() or link.exists():
            continue
        os.symlink(SOURCE.resolve() / subdir, link, target_is_directory=True)


def main() -> None:
    print(f"{'level':<8}{'target':>12}{'realised':>12}  status")
    for level, scalar in LEVELS.items():
        out_dir = OUT_ROOT / f"traces_{level}" / "isp_2026"
        if out_dir.exists():
            shutil.rmtree(out_dir.parent)
        out_dir.mkdir(parents=True)
        source_mwh, scaled_mwh = _write_scaled_demand(out_dir, scalar)
        _link_vre(out_dir)
        realised = scaled_mwh / source_mwh
        ok = "OK" if round(realised, 6) == round(scalar, 6) else "MISMATCH"
        print(f"{level:<8}{scalar:>12.6f}{realised:>12.6f}  {ok}")


if __name__ == "__main__":
    main()
