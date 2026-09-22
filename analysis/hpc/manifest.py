"""Build the Slurm manifest for the Step Change base chain and its increment grid.

One launch is two stages, both written into the same manifest so a resume or a stage-by-stage
submission always reads a complete picture:

* the ``base`` stage, one recursive-dynamic chain ``ext_step_change_sc`` solved over every
  milestone year of the plan, its annual cap set to the Step Change intensity path;
* the ``branch`` stage, one conditioned single-year solve per increment cell
  (:mod:`analysis.hpc.increments`), seeded from the base chain's state at the prior milestone
  with the base stock pinned.

Caps are written into the solver as absolute annual tonnes,
``cap_t = delivery x intensity x Q_source_TWh x 1e6``, where ``Q_source`` is the chain's own
source NEM load for that year and ``delivery`` is 1.0 for an intensity quoted on the source
basis (emissions over generation, as the scenario intensities are) and the plan's delivery
fraction for one quoted on the customer-delivered basis. Every cap row records its basis, so no
cap is ever quoted without one.

Naming:

* the base chain is ``ext_<trajectory without the "iasr_" prefix>_sc``;
* an increment cell is ``ext_<trajectory>_b<year>_<demand level>_<cap key>``, e.g.
  ``ext_step_change_b2035_d110_cap003225``, where the cap key is its own annual intensity
  written as a decimal with the point removed (:func:`campaign_grid.cap_key`).

Because the branch solves are single-year and each one is a different year, ``--periods`` rides
in each row's args rather than in ``chain.sbatch``.

Outputs in one launch's ``campaign/`` directory:

* ``caps.csv`` -- one row per (chain, year) with the intensity, its basis, the source load and
  the absolute tonnage.
* ``chains.tsv`` -- headerless ``run_id<TAB>traces<TAB>args``, one line per chain, where
  ``traces`` is the absolute path of that trajectory's ``<trajectory>.txt`` trace-directory
  token file. The line number is the Slurm array index, so the order is part of the contract:
  the base chain first, then the increment cells year by year.
* ``chains_index.csv`` -- the same chains with their array row, chain key, stage, final period
  and increment cell, for picking array ranges by hand.
* ``demand_plan.json`` -- the plan the manifest was built from, with the grid's demand
  trajectories written in.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from analysis.env import OutputLayout
from analysis.hpc import increments
from analysis.hpc.campaign_grid import BASE_CHAIN_KEY, cap_key

DELIVERED_BASIS = "delivered"
SOURCE_BASIS = "source"

BASE_STAGE = "base"
BRANCH_STAGE = "branch"

CAPS_COLUMNS = [
    "run_id",
    "trajectory",
    "chain",
    "year",
    "intensity",
    "intensity_basis",
    "source_twh",
    "cap_t",
    "plan_version",
    "git_commit",
]

CELL_COLUMNS = ["base_cell", "branch_year", "demand_level", "intensity_level"]

CHAINS_COLUMNS = [
    "row",
    "run_id",
    "trajectory",
    "traces",
    "chain",
    "stage",
    "args",
    "last_period",
    *CELL_COLUMNS,
]

INDEX_COLUMNS = [
    "row",
    "run_id",
    "trajectory",
    "chain",
    "stage",
    "last_period",
    *CELL_COLUMNS,
]


@dataclass(frozen=True)
class Rung:
    """One year's cap intensity in t CO2e/MWh, with the basis it is quoted on."""

    intensity: float
    basis: str


def _read_git_commit() -> str:
    """Short commit of the working tree, or ``unknown`` when git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def _run_id(trajectory: str, chain_key: str) -> str:
    """Campaign run id, e.g. ``iasr_step_change`` + ``sc`` -> ``ext_step_change_sc``."""
    return f"ext_{trajectory.removeprefix('iasr_')}_{chain_key}"


def _cap_tonnes(rung: Rung, source_twh: float, delivery_fraction: float) -> int:
    """Absolute annual CO2e cap in tonnes for one rung at one year's source load.

    A delivered-basis intensity is converted to the source boundary by the delivery
    fraction; a source-basis rung is applied to the source load as-is.
    """
    delivery = delivery_fraction if rung.basis == DELIVERED_BASIS else 1.0
    return round(delivery * rung.intensity * source_twh * 1e6)


def _base_intensity(plan: dict, year: int) -> float:
    """The base chain's cap intensity at one milestone year, in t CO2e/MWh."""
    return plan["cap_intensity_t_per_mwh"][str(year)]


def _branch_key(plan: dict, cell: increments.Cell) -> str:
    """Chain key of one increment cell: its own annual intensity as a cap key."""
    return cap_key(_base_intensity(plan, cell.year) * cell.intensity_factor)


def _cap_row(
    plan: dict,
    git_commit: str,
    run_id: str,
    trajectory: str,
    chain: str,
    year: int,
    rung: Rung,
    source_twh: float,
) -> dict:
    """Assemble one ``caps.csv`` row from one chain's intensity and load at one year."""
    return {
        "run_id": run_id,
        "trajectory": trajectory,
        "chain": chain,
        "year": year,
        "intensity": rung.intensity,
        "intensity_basis": rung.basis,
        "source_twh": source_twh,
        "cap_t": _cap_tonnes(rung, source_twh, plan["delivery_fraction"]),
        "plan_version": plan["version"],
        "git_commit": git_commit,
    }


def _base_cap_rows(plan: dict, git_commit: str) -> list[dict]:
    """The base chain's cap, one row per milestone year of the plan."""
    trajectory, knots = increments.base_trajectory(plan)
    basis = plan["cap_intensity_basis"]
    return [
        _cap_row(
            plan,
            git_commit,
            run_id=_run_id(trajectory, BASE_CHAIN_KEY),
            trajectory=trajectory,
            chain=BASE_CHAIN_KEY,
            year=year,
            rung=Rung(_base_intensity(plan, year), basis),
            source_twh=knots[str(year)],
        )
        for year in plan["milestone_years"]
    ]


def _branch_cap_rows(plan: dict, git_commit: str) -> list[dict]:
    """One cap row per increment cell: its intensity factor on the base intensity, at its own load."""
    basis = plan["cap_intensity_basis"]
    return [
        _cap_row(
            plan,
            git_commit,
            run_id=_run_id(cell.trajectory, _branch_key(plan, cell)),
            trajectory=cell.trajectory,
            chain=_branch_key(plan, cell),
            year=cell.year,
            rung=Rung(_base_intensity(plan, cell.year) * cell.intensity_factor, basis),
            source_twh=cell.source_twh,
        )
        for cell in increments.cells(plan)
    ]


def build_caps_table(plan: dict, git_commit: str) -> pd.DataFrame:
    """Every cap of the campaign: the base chain's milestones, then each increment cell."""
    rows = _base_cap_rows(plan, git_commit) + _branch_cap_rows(plan, git_commit)
    return pd.DataFrame(rows, columns=CAPS_COLUMNS)


def _pipeline_args(plan: dict, year: int) -> str:
    """Near-term pin flags, on the periods at or before the plan's pipeline period."""
    if year > plan["pipeline_period"]:
        return ""
    return (
        f" --pipeline-period {plan['pipeline_period']}"
        f" --new-entrant-cap-mw {plan['new_entrant_cap_mw']}"
        f" --new-entrant-storage-cap-mw {plan['new_entrant_storage_cap_mw']}"
    )


def _base_chain_row(plan: dict, caps: pd.DataFrame) -> dict:
    """The base chain: every milestone year in one recursive-dynamic chain."""
    base = caps[caps["chain"] == BASE_CHAIN_KEY]
    periods = " ".join(str(year) for year in plan["milestone_years"])
    schedule = " ".join(f"{year}:{t}" for year, t in zip(base["year"], base["cap_t"]))
    return {
        "run_id": base["run_id"].iloc[0],
        "trajectory": base["trajectory"].iloc[0],
        "chain": BASE_CHAIN_KEY,
        "stage": BASE_STAGE,
        "args": f"--periods {periods} --co2-cap-t-schedule {schedule}"
        + _pipeline_args(plan, plan["pipeline_period"]),
        "last_period": plan["milestone_years"][-1],
        "base_cell": "",
        "branch_year": "",
        "demand_level": "",
        "intensity_level": "",
    }


def _branch_chain_row(
    plan: dict, cell: increments.Cell, base_run_id: str, cap_t: int
) -> dict:
    """One increment cell: a single-year solve seeded from the base chain's earlier state."""
    key = _branch_key(plan, cell)
    return {
        "run_id": _run_id(cell.trajectory, key),
        "trajectory": cell.trajectory,
        "chain": key,
        "stage": BRANCH_STAGE,
        "args": f"--periods {cell.year} --co2-cap-t-schedule {cell.year}:{cap_t} "
        f"--seed-state-from {base_run_id} --pin-base-stock"
        + _pipeline_args(plan, cell.year),
        "last_period": cell.year,
        "base_cell": base_run_id,
        "branch_year": cell.year,
        "demand_level": cell.demand_level,
        "intensity_level": cell.intensity_level,
    }


def _branch_chain_rows(plan: dict, caps: pd.DataFrame, base_run_id: str) -> list[dict]:
    """Every increment cell in cell order, reading its tonnage back out of the caps table."""
    tonnes = dict(zip(caps["run_id"], caps["cap_t"]))
    return [
        _branch_chain_row(
            plan,
            cell,
            base_run_id,
            tonnes[_run_id(cell.trajectory, _branch_key(plan, cell))],
        )
        for cell in increments.cells(plan)
    ]


def build_chain_table(
    plan: dict,
    caps: pd.DataFrame,
    tracedirs: Path,
    max_cap: float | None = None,
    rez_limit_factor: float | None = None,
    flow_path_limit_factor: float | None = None,
) -> pd.DataFrame:
    """Every chain of the campaign in Slurm array order, numbered from zero.

    :param plan: Demand plan holding the trajectories, milestone years and increment grid.
    :param caps: Cap table every chain reads its tonnages from.
    :param tracedirs: Directory holding each trajectory's ``<trajectory>.txt``
        trace-directory token file, which the Slurm job reads at solve time.
    :param max_cap: Not supported by an increment-grid plan, which has one base chain and no
        cap ladder to narrow; raises when given.
    :param rez_limit_factor: Relax every renewable energy zone (REZ) limit by this
        factor in every chain of the launch; omit for the IASR limits.
    :param flow_path_limit_factor: Relax every flow-path and REZ-connection expansion
        limit by this factor in every chain of the launch; omit for the IASR limits.
    """
    if max_cap is not None:
        raise ValueError(
            "--max-cap narrows a cap ladder; this plan has one base chain and an increment grid"
        )
    base = _base_chain_row(plan, caps)
    chains = pd.DataFrame(
        [base, *_branch_chain_rows(plan, caps, base["run_id"])],
    )
    if rez_limit_factor is not None:
        chains["args"] += f" --rez-limit-factor {rez_limit_factor}"
    if flow_path_limit_factor is not None:
        chains["args"] += f" --flow-path-limit-factor {flow_path_limit_factor}"
    chains.insert(0, "row", range(len(chains)))
    chains["traces"] = [
        (tracedirs / f"{trajectory}.txt").as_posix()
        for trajectory in chains["trajectory"]
    ]
    return chains[CHAINS_COLUMNS]


def write_manifest(
    caps: pd.DataFrame, chains: pd.DataFrame, out_dir: Path, plan: dict
) -> None:
    """Write the manifest files with LF endings, as the Slurm jobs read them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    caps.to_csv(out_dir / "caps.csv", index=False, lineterminator="\n")
    chains[["run_id", "traces", "args"]].to_csv(
        out_dir / "chains.tsv", sep="\t", header=False, index=False, lineterminator="\n"
    )
    chains[INDEX_COLUMNS].to_csv(
        out_dir / "chains_index.csv", index=False, lineterminator="\n"
    )
    (out_dir / "demand_plan.json").write_text(
        json.dumps(increments.expand(plan), indent=2) + "\n", encoding="utf-8"
    )


def build(
    plan: Path,
    layout: OutputLayout,
    tracedirs: Path,
    max_cap: float | None = None,
    rez_limit_factor: float | None = None,
    flow_path_limit_factor: float | None = None,
) -> pd.DataFrame:
    """Write one launch's manifest and return its chain table.

    :param plan: Demand plan JSON.
    :param layout: The launch directory the manifest is written into.
    :param tracedirs: Directory of per-trajectory trace-directory token files.
    :param max_cap: Not supported by an increment-grid plan; raises when given.
    :param rez_limit_factor: Relax every REZ limit by this factor in every chain.
    :param flow_path_limit_factor: Relax every corridor expansion limit by this factor in
        every chain.
    :return: Every chain of the campaign in Slurm array order.
    """
    plan_data = json.loads(plan.read_text(encoding="utf-8"))
    caps = build_caps_table(plan_data, _read_git_commit())
    chains = build_chain_table(
        plan_data, caps, tracedirs, max_cap, rez_limit_factor, flow_path_limit_factor
    )
    write_manifest(caps, chains, layout.campaign, plan_data)
    print(f"plan version: {plan_data['version']}; chains: {len(chains)}")
    return chains
