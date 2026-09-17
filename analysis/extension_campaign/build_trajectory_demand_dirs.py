"""Build one rewritten parsed-demand trace directory per (trajectory, milestone year) for the extension campaign.

The campaign varies electricity demand entirely through the parsed-traces route: no model code, schema or committed data
changes. Each output directory is a complete parsed trace store whose demand values are multiplied by a single scalar
chosen so the directory's milestone financial year delivers the trajectory's target source NEM load.

Two design rules carry over from the intensity-demand-map builder:

* Every scalar, including 1.0, goes through the identical read-scale-write round trip, so the round trip itself cannot
  masquerade as a demand signal.
* VRE traces (``project/``, ``zone/``) are symlinked to one shared source store, so wind and solar are bit-identical
  between trajectories.

The 2060 milestone sits past the end of the parsed store, so it is built by relabelling: the FY2050 rows are copied
forward exactly ten years and appended. Demand gets the 2060 scalar applied to the relabelled rows; VRE is relabelled
once into a shared ``_vre_2060`` store and left unscaled.

Outputs under ``--out-root``:

* ``<trajectory>_<year>/isp_<dataset year>/`` - the trace directories themselves.
* ``tracedirs/<trajectory>.txt`` - the ``YEAR:DIR`` tokens for ``run_myopic.py --parsed-traces-directory-schedule``.
* ``annual_demand_series.csv`` - the yearly source-TWh path behind each trajectory.
* ``manifest_demand_dirs.csv`` - the scalar and the energies behind every directory.

Usage:
    uv run python analysis/extension_campaign/build_trajectory_demand_dirs.py \\
        --source data/trace_data_final/isp_2026 \\
        --out-root /scratch/extension_campaign_traces \\
        --plan analysis/extension_campaign/next-sweep-demand-plan.json
"""

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ANCHOR_YEAR = 2025
ANCHOR_KIND = "anchor_customer_delivered"
EXTENSION_YEAR = 2060
EXTENSION_SOURCE_FY = 2050
EXTENSION_SHIFT_YEARS = 10
EXTENDED_VRE_DIR = "_vre_2060"
LINKED_SUBDIRS = ("project", "zone")
DEMAND_SUBDIR = "demand"
HOURS_PER_INTERVAL = 0.5
MWH_PER_TWH = 1e6
MATCH_TOLERANCE = 1e-6
MANIFEST_COLUMNS = [
    "trajectory",
    "year",
    "scalar",
    "source_fy_mwh",
    "realised_fy_mwh",
    "plan_version",
    "authored_horizon_extension",
]


@dataclass(frozen=True)
class TraceStores:
    """Paths and pre-measured source energies shared by every output directory in one build.

    :param source: Root of the read-only parsed trace store, for example ``data/trace_data_final/isp_2026``.
    :param out_root: Directory the rewritten trace directories and their reports are written under.
    :param reference_year: Weather reference year partition that is rewritten.
    :param source_fy_mwh: Source-store demand energy in MWh behind each milestone year.
    :param extended_vre: Shared VRE store carrying a relabelled FY2060, or None when no milestone needs one.
    """

    source: Path
    out_root: Path
    reference_year: int
    source_fy_mwh: dict[int, float]
    extended_vre: Path | None

    @property
    def dataset_dir(self) -> str:
        """Name of the dataset folder ISPyPSA appends to a parsed-traces directory, for example ``isp_2026``."""
        return self.source.name


def _parquets(store: Path, subdir: str, reference_year: int) -> list[Path]:
    """Every parquet under one parsed-store subdirectory for one weather reference year."""
    return sorted(
        (store / subdir).glob(f"**/reference_year={reference_year}/*.parquet")
    )


def _financial_year(timestamps: pd.Series) -> pd.Series:
    """Financial year each timestamp belongs to, matching ISPyPSA's ``year_type: fy`` rule that July rolls into the next year."""
    return timestamps.dt.year + (timestamps.dt.month >= 7)


def _financial_year_mwh(frame: pd.DataFrame, financial_year: int) -> float:
    """Energy in MWh of the half-hourly MW values belonging to one financial year."""
    rows = frame[_financial_year(frame["datetime"]) == financial_year]
    return float(rows["value"].sum()) * HOURS_PER_INTERVAL


def _measure_demand_energy(
    store: Path, reference_year: int, financial_year: int
) -> float:
    """Demand energy in MWh for one financial year, summed over every partition and sub-region of a parsed store."""
    frames = (
        pd.read_parquet(path, columns=["datetime", "value"])
        for path in _parquets(store, DEMAND_SUBDIR, reference_year)
    )
    return float(sum(_financial_year_mwh(frame, financial_year) for frame in frames))


def _source_financial_year(milestone_year: int) -> int:
    """Source financial year that supplies a milestone; 2060 is built from the last modelled year, FY2050."""
    return EXTENSION_SOURCE_FY if milestone_year == EXTENSION_YEAR else milestone_year


def _measure_source_energy(
    source: Path, reference_year: int, milestone_years: list[int]
) -> dict[int, float]:
    """Source-store energy in MWh behind each milestone, measured once and reused by every trajectory."""
    return {
        year: _measure_demand_energy(
            source, reference_year, _source_financial_year(year)
        )
        for year in milestone_years
    }


def _relabel_to_extension_year(frame: pd.DataFrame) -> pd.DataFrame:
    """FY2050 rows copied forward ten years, so a store that stops before 2060 gains an FY2060."""
    rows = frame[_financial_year(frame["datetime"]) == EXTENSION_SOURCE_FY].copy()
    rows["datetime"] = rows["datetime"] + pd.DateOffset(years=EXTENSION_SHIFT_YEARS)
    return rows


def _reset_dataset_dir(base_dir: Path, dataset_dir: str) -> Path:
    """Empty output directory for one build, returning the ``isp_<dataset year>`` level that ISPyPSA reads."""
    if base_dir.exists():
        shutil.rmtree(base_dir)
    dataset = base_dir / dataset_dir
    dataset.mkdir(parents=True)
    return dataset


def _write_scaled_demand(
    stores: TraceStores, dataset_dir: Path, scalar: float, extend_horizon: bool
) -> None:
    """Rewrite every source demand parquet with its values multiplied by one scalar, appending a relabelled FY2060 on request."""
    for parquet in _parquets(stores.source, DEMAND_SUBDIR, stores.reference_year):
        target = (
            dataset_dir
            / DEMAND_SUBDIR
            / parquet.relative_to(stores.source / DEMAND_SUBDIR)
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.read_parquet(parquet)
        frame["value"] = frame["value"] * scalar
        if extend_horizon:
            frame = pd.concat(
                [frame, _relabel_to_extension_year(frame)], ignore_index=True
            )
        frame.to_parquet(target, index=False)


def _append_relabelled_vre(
    source: Path, dataset_dir: Path, subdir: str, reference_year: int
) -> None:
    """Copy one VRE subdirectory unscaled, appending its FY2050 rows relabelled to FY2060."""
    for parquet in _parquets(source, subdir, reference_year):
        target = dataset_dir / subdir / parquet.relative_to(source / subdir)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.read_parquet(parquet)
        pd.concat(
            [frame, _relabel_to_extension_year(frame)], ignore_index=True
        ).to_parquet(target, index=False)


def _build_extended_vre_store(
    source: Path, out_root: Path, reference_year: int, milestone_years: list[int]
) -> Path | None:
    """One shared VRE store carrying a relabelled FY2060, or None when no milestone reaches past the parsed store."""
    if EXTENSION_YEAR not in milestone_years:
        return None
    dataset_dir = _reset_dataset_dir(out_root / EXTENDED_VRE_DIR, source.name)
    for subdir in LINKED_SUBDIRS:
        _append_relabelled_vre(source, dataset_dir, subdir, reference_year)
    return dataset_dir


def _link_vre(stores: TraceStores, dataset_dir: Path, milestone_year: int) -> None:
    """Symlink ``project/`` and ``zone/`` to one shared store, so wind and solar are bit-identical across trajectories."""
    vre_store = (
        stores.extended_vre if milestone_year == EXTENSION_YEAR else stores.source
    )
    for subdir in LINKED_SUBDIRS:
        os.symlink(
            (vre_store / subdir).resolve(),
            dataset_dir / subdir,
            target_is_directory=True,
        )


def _build_demand_dir(
    stores: TraceStores, trajectory: str, milestone_year: int, target_twh: float
) -> dict:
    """Write one (trajectory, milestone year) trace directory and report how its realised financial-year energy landed."""
    dataset_dir = _reset_dataset_dir(
        stores.out_root / f"{trajectory}_{milestone_year}", stores.dataset_dir
    )
    source_fy_mwh = stores.source_fy_mwh[milestone_year]
    scalar = target_twh * MWH_PER_TWH / source_fy_mwh
    _write_scaled_demand(stores, dataset_dir, scalar, milestone_year == EXTENSION_YEAR)
    _link_vre(stores, dataset_dir, milestone_year)
    return {
        "trajectory": trajectory,
        "year": milestone_year,
        "target_twh": target_twh,
        "scalar": scalar,
        "source_fy_mwh": source_fy_mwh,
        "realised_fy_mwh": _measure_demand_energy(
            dataset_dir, stores.reference_year, milestone_year
        ),
        "authored_horizon_extension": milestone_year == EXTENSION_YEAR,
    }


def _build_trajectory_dirs(
    stores: TraceStores,
    trajectory: str,
    targets: dict[str, float],
    milestone_years: list[int],
) -> list[dict]:
    """Every milestone directory for one trajectory, plus the schedule-token file that points a run at them."""
    records = [
        _build_demand_dir(stores, trajectory, year, targets[str(year)])
        for year in sorted(milestone_years)
    ]
    _write_tracedirs_file(stores.out_root, trajectory, milestone_years)
    return records


def _write_tracedirs_file(
    out_root: Path, trajectory: str, milestone_years: list[int]
) -> None:
    """Schedule tokens for ``run_myopic.py --parsed-traces-directory-schedule``, one line in year order."""
    tokens = [
        f"{year}:{(out_root / f'{trajectory}_{year}').resolve().as_posix()}"
        for year in sorted(milestone_years)
    ]
    path = out_root / "tracedirs" / f"{trajectory}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(" ".join(tokens) + "\n", encoding="utf-8")


def _annual_demand_series(
    trajectory: str, targets: dict[str, float], anchor_twh: float
) -> pd.DataFrame:
    """One trajectory's yearly source-TWh path.

    Authored knots are carried through untouched and the years between them are interpolated linearly in absolute TWh.
    The series starts at the trajectory's first authored year: the 2025 anchor is on the customer-delivered basis rather
    than the source-load basis, so it is reported as its own row and never interpolated from.

    :param trajectory: Name of the demand trajectory.
    :param targets: Authored source TWh keyed by financial year as a string.
    :param anchor_twh: Common 2025 customer-delivered anchor in TWh.
    :return: Rows of trajectory, financial year, source TWh and the kind of each value.
    """
    knot_years = sorted(int(year) for year in targets)
    knot_twh = [targets[str(year)] for year in knot_years]
    years = list(range(knot_years[0], knot_years[-1] + 1))
    kinds = ["authored" if year in knot_years else "interpolated" for year in years]
    return pd.DataFrame(
        {
            "trajectory": trajectory,
            "financial_year": [ANCHOR_YEAR, *years],
            "source_twh": [anchor_twh, *np.interp(years, knot_years, knot_twh)],
            "kind": [ANCHOR_KIND, *kinds],
        }
    )


def _write_annual_demand_series(out_root: Path, plan: dict) -> None:
    """Yearly demand path for every trajectory in the plan, written once per build."""
    anchor_twh = plan["anchor_2025_customer_delivered_twh"]
    series = [
        _annual_demand_series(name, targets, anchor_twh)
        for name, targets in plan["demand_paths_source_twh"].items()
    ]
    pd.concat(series, ignore_index=True).to_csv(
        out_root / "annual_demand_series.csv", index=False
    )


def _write_manifest(out_root: Path, records: list[dict], plan_version: str) -> None:
    """One manifest row per output directory, recording the scalar and the energies behind it."""
    manifest = pd.DataFrame(records).assign(plan_version=plan_version)
    manifest[MANIFEST_COLUMNS].to_csv(
        out_root / "manifest_demand_dirs.csv", index=False
    )


def _print_summary(records: list[dict]) -> None:
    """Table of how each directory's realised financial-year energy compares with the target it was scaled to."""
    print(
        f"{'trajectory':<20}{'year':>6}{'target TWh':>14}{'realised TWh':>14}{'ratio':>12}  status"
    )
    for record in records:
        realised_twh = record["realised_fy_mwh"] / MWH_PER_TWH
        ratio = realised_twh / record["target_twh"]
        status = "OK" if abs(ratio - 1.0) <= MATCH_TOLERANCE else "MISMATCH"
        print(
            f"{record['trajectory']:<20}{record['year']:>6}{record['target_twh']:>14.4f}"
            f"{realised_twh:>14.4f}{ratio:>12.6f}  {status}"
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Command-line arguments: the store to read, where to write, the plan to follow and the weather reference year."""
    parser = argparse.ArgumentParser(
        description="Build the extension campaign's per-trajectory demand trace directories."
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="parsed trace store root, e.g. data/trace_data_final/isp_2026",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        required=True,
        help="directory the rewritten trace directories are written under",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        required=True,
        help="demand plan JSON holding milestone_years and demand_paths_source_twh",
    )
    parser.add_argument(
        "--reference-year",
        type=int,
        default=2018,
        help="weather reference year partition to rewrite",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Build every campaign trace directory, its schedule-token file, the annual demand series and the manifest."""
    args = _parse_args(argv)
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    args.out_root.mkdir(parents=True, exist_ok=True)
    _write_annual_demand_series(args.out_root, plan)
    stores = TraceStores(
        source=args.source,
        out_root=args.out_root,
        reference_year=args.reference_year,
        source_fy_mwh=_measure_source_energy(
            args.source, args.reference_year, plan["milestone_years"]
        ),
        extended_vre=_build_extended_vre_store(
            args.source, args.out_root, args.reference_year, plan["milestone_years"]
        ),
    )
    records = []
    for trajectory, targets in plan["demand_paths_source_twh"].items():
        records += _build_trajectory_dirs(
            stores, trajectory, targets, plan["milestone_years"]
        )
    _write_manifest(args.out_root, records, plan["version"])
    _print_summary(records)


if __name__ == "__main__":
    main()
