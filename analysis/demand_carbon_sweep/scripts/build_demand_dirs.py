"""Build one rewritten parsed-demand trace directory per demand scalar.

The demand dimension of the sweep is implemented entirely here, via the
--parsed-traces-directory route: no model code, schema or committed data changes.

Every level -- including 1.0 -- goes through the same read-scale-write round trip,
so the round trip itself cannot masquerade as a demand signal. VRE traces
(project/, zone/) are symlinked to the single source store, identically across all
four directories, so wind and solar are bit-identical between levels.

Only reference_year=2018 is written, which is the reference_year_cycle every cell in
the sweep uses. Requesting any other year from these directories will fail loudly.

Prints the realised energy ratio of each directory against its target scalar.
"""

import os
import shutil
from pathlib import Path

import pandas as pd

SOURCE = Path("data/trace_data_final/isp_2026")
OUT_ROOT = Path(
    "C:/Users/van538/AppData/Local/Temp/5/claude/"
    "c--Users-van538-GitHub-ISPyPSA/c1558bce-da07-46a1-8051-03c3ed5f9b28/scratchpad"
)
REF_YEAR = 2018
LINKED_SUBDIRS = ("project", "zone")

# Provenance: ratios of AEMO 2026 ISP Final FY2050 NEM demand energy (POE50,
# OPSO_MODELLING, RefYear 2018, 15 sub-regions) to Step Change, per
# derive_demand_scalars.py. Slower Growth and Accelerated Transition are the
# 2026-ISP successors of the 2024-ISP "Progressive Change" and "Green Energy
# Exports" (src/ispypsa/iasr_table_caching/schema_normalisation.py:681-682).
LEVELS = {
    "d087": 0.869546,  # Slower Growth / Step Change
    "d100": 1.000000,  # Step Change as parsed
    "d110": 1.100000,  # interpolated presentation level
    "d123": 1.234752,  # Accelerated Transition / Step Change
}


def _demand_partitions() -> list[Path]:
    """Every reference_year=2018 demand partition directory in the source store."""
    return sorted((SOURCE / "demand").glob(f"*/reference_year={REF_YEAR}"))


def _write_scaled_demand(out_dir: Path, scalar: float) -> tuple[float, float]:
    """Mirror the demand partitions with `value` scaled. Returns (source, scaled) MWh."""
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
    """Point project/ and zone/ at the one source store, identically for every level."""
    for subdir in LINKED_SUBDIRS:
        link = out_dir / subdir
        if link.is_symlink() or link.exists():
            continue
        os.symlink(SOURCE.resolve() / subdir, link, target_is_directory=True)


def main() -> None:
    print(f"{'level':<8}{'target':>12}{'realised':>12}{'ratio':>12}  status")
    for level, scalar in LEVELS.items():
        out_dir = OUT_ROOT / f"traces_{level}" / "isp_2026"
        if out_dir.exists():
            shutil.rmtree(out_dir.parent)
        out_dir.mkdir(parents=True)
        source_mwh, scaled_mwh = _write_scaled_demand(out_dir, scalar)
        _link_vre(out_dir)
        realised = scaled_mwh / source_mwh
        ok = "OK" if round(realised, 4) == round(scalar, 4) else "MISMATCH"
        print(f"{level:<8}{scalar:>12.6f}{realised:>12.6f}{realised:>12.4f}  {ok}")


if __name__ == "__main__":
    main()
