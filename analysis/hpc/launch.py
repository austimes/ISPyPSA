"""Stamp a launch directory, write its manifest and submit the campaign to Slurm.

One launch is one stamped directory, ``$IO_DIR/outputs/<stamp>_<run_set>``, holding the
manifest that decides what each Slurm array task solves and every product of the run.
The array index is the chain's row in ``campaign/chains.tsv``, so the manifest and the
array are written together and never drift apart. ``campaign/inputs.txt`` names the input
package the launch read, so a run's results can always be traced back to its inputs, and
``campaign/assumptions.json`` names what this launch varies -- its REZ limit factor, its
corridor limit factor, its chain count, its increment grid and that input package -- so two
run sets can be compared.

The manifest always holds every chain of both stages, and ``--stage`` picks which of them this
submission covers, so the base chain and the increment grid that seeds from it go into one launch
directory and the grid is queued behind the base chain with ``--after <job id>``.

``submit`` is the single place that knows how a campaign job is handed to Slurm: the
account, any partition override, stdout path, per-submission resource overrides and the
exported variables (``RUN_DIR``, ``REPO`` and
``RESUME``) that the sbatch scripts read. The deliverables builder submits its own
extract array through it as well, so the two entry points cannot disagree.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Literal

import pandas as pd

from analysis.env import REPO_ROOT, Env, OutputLayout
from analysis.hpc import increments, manifest, tracedirs

SLURM_DIR = Path(__file__).parent / "slurm"
DEFAULT_PLAN = Path(__file__).parent / "demand_plan.json"


def sbatch_command(
    script: Path,
    array: str,
    export: dict[str, str],
    layout: OutputLayout,
    env: Env,
    dependency: str | None = None,
    resources: tuple[str, ...] = (),
) -> list[str]:
    """The ``sbatch`` command line for one array submission of ``script``.

    The script's own ``#SBATCH`` header sets its partition, memory, time and cores; ``resources``
    overrides them for this submission, e.g. ``("--mem=2G",)``.

    Variables reach the job through the submitting environment (see ``job_environment``)
    rather than ``--export`` items, whose comma separator would split flag values.
    """
    return [
        "sbatch",
        f"--array={array}",
        "--export=ALL",
        *([f"--account={env.slurm_account}"] if env.slurm_account else []),
        *([f"--partition={env.slurm_partition}"] if env.slurm_partition else []),
        f"--output={(layout.campaign / 'slurm').as_posix()}/%x-%A_%a.out",
        *([f"--dependency={dependency}"] if dependency else []),
        *resources,
        script.as_posix(),
    ]


def job_environment(export: dict[str, str], layout: OutputLayout) -> dict[str, str]:
    """Variables every array task reads: the launch directory, the repo and the extras."""
    return {"RUN_DIR": layout.root.as_posix(), "REPO": REPO_ROOT.as_posix(), **export}


def submit(
    script: Path,
    array: str,
    export: dict[str, str],
    layout: OutputLayout,
    env: Env,
    dependency: str | None = None,
    resources: tuple[str, ...] = (),
) -> str:
    """Submit one Slurm array job for this launch and return its job id.

    :param script: The sbatch script to run.
    :param array: Slurm array specification, e.g. ``0-40`` or ``3,7,9``.
    :param export: Extra variables to export on top of ``RUN_DIR`` and ``REPO``.
    :param layout: The launch directory the job writes into.
    :param env: Cluster account and partition.
    :param dependency: Slurm dependency expression, e.g. ``afterok:12345``.
    :param resources: sbatch flags overriding the script's header for this submission.
    """
    (layout.campaign / "slurm").mkdir(parents=True, exist_ok=True)
    command = sbatch_command(script, array, export, layout, env, dependency, resources)
    environment = job_environment(export, layout)
    print(" ".join(f"{name}={value}" for name, value in environment.items()))
    print(" ".join(command))
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **environment},
    )
    return result.stdout.split()[-1]


def _chain_is_complete(layout: OutputLayout, run_id: str, last_period: int) -> bool:
    """True when a chain's final period has a completed record or a solved network on disk."""
    final_run = f"{run_id}_{last_period}"
    if layout.network(final_run).exists():
        return True
    record = layout.record(final_run)
    if not record.exists():
        return False
    return json.loads(record.read_text(encoding="utf-8")).get("status") == "completed"


def _array(chains: pd.DataFrame) -> str:
    """Slurm array specification covering the given chains, by their manifest row."""
    return ",".join(str(row) for row in chains["row"])


def incomplete_array(layout: OutputLayout, chains: pd.DataFrame) -> str:
    """Slurm array specification covering only the chains that have not finished.

    :param layout: The launch directory to inspect.
    :param chains: The launch's chain table, whose ``row`` is the array index and whose
        ``last_period`` is the final period of that chain alone.
    :return: A comma-separated index list, empty when every chain is complete.
    """
    return _array(
        chains[
            [
                not _chain_is_complete(layout, chain.run_id, chain.last_period)
                for chain in chains.itertuples()
            ]
        ]
    )


def _stage_chains(chains: pd.DataFrame, stage: str) -> pd.DataFrame:
    """The manifest rows one stage submits: ``base``, ``branch``, or every row for ``all``."""
    if stage == "all":
        return chains
    return chains[chains["stage"] == stage]


def _increments_summary(plan: dict) -> dict | None:
    """The increment grid this launch carries: its cell count and its two level sets."""
    grid = plan.get(increments.GRID_KEY)
    if grid is None:
        return None
    return {
        "cells": len(increments.cell_levels(grid)),
        "demand_levels": grid["demand_levels"],
        "intensity_levels": grid["intensity_levels"],
    }


def write_assumptions(
    layout: OutputLayout,
    inputs: Path,
    chains: int,
    plan: dict,
    max_cap: float | None,
    rez_limit_factor: float | None,
    flow_path_limit_factor: float | None,
    solve_flags: str | None,
) -> None:
    """Record what this launch varies, so two run sets can be compared without reading their manifests."""
    (layout.campaign / "assumptions.json").write_text(
        json.dumps(
            {
                "rez_limit_factor": rez_limit_factor,
                "flow_path_limit_factor": flow_path_limit_factor,
                "solve_flags": solve_flags,
                "max_cap": max_cap,
                "chains": chains,
                "increments": _increments_summary(plan),
                "inputs": inputs.as_posix(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(
    run_set: str = "sc5",
    plan: Path = DEFAULT_PLAN,
    run: Path | None = None,
    resume: bool = False,
    smoke: bool = False,
    stage: Literal["base", "branch", "all"] = "all",
    after: str | None = None,
    array: str | None = None,
    max_cap: float | None = None,
    rez_limit_factor: float | None = None,
    flow_path_limit_factor: float | None = None,
    solve_flags: str | None = None,
    dry_run: bool = False,
) -> None:
    """Prepare a campaign launch and submit its chains to Slurm.

    :param run_set: Name a new launch directory is stamped with, under ``$IO_DIR/outputs``.
    :param plan: Demand plan JSON holding the trajectories, loads and milestone years.
    :param run: Existing launch directory to submit into, instead of stamping a new one.
    :param resume: Submit only the chains whose final period has not completed; requires
        ``run``, because a freshly stamped directory has no chain to resume.
    :param smoke: Submit the single NSW two-period gate chain instead of the campaign.
    :param stage: Which stage of the always-complete manifest to submit: ``base`` for the base
        chain, ``branch`` for the increment grid, or ``all`` for both.
    :param after: Slurm job id this submission waits for, so the increment grid can be queued
        behind the base chain it seeds from.
    :param array: Slurm array specification, overriding the one derived from the manifest.
    :param max_cap: Keep only the cap chains at or below this 2050 target intensity; not
        supported by an increment-grid plan, which has no cap ladder to narrow.
    :param rez_limit_factor: Relax every renewable energy zone (REZ) transmission,
        expansion and resource limit by this factor in every chain of the launch, as a
        sensitivity against the IASR limits; omit for the IASR limits.
    :param flow_path_limit_factor: Relax the expansion headroom of every sub-region flow path
        and every REZ-to-sub-region connection by this factor in every chain of the launch, as
        a sensitivity against the IASR limits; omit for the IASR limits.
    :param solve_flags: Extra ``msm solve`` tokens appended to every chain, e.g.
        ``--gurobi-crossover 0`` for a barrier-only feasibility screen.
    :param dry_run: Write the manifest and print the sbatch command, building no trace
        directories and submitting nothing.
    """
    if resume and run is None:
        raise ValueError("--resume needs --run: name the launch directory to resume")
    env = Env.from_env()
    layout = OutputLayout(run) if run else env.new_run(run_set)
    plan_data = json.loads(plan.read_text(encoding="utf-8"))
    if not dry_run:
        tracedirs.build(env.traces, env.tracedirs, plan)
    chains = manifest.build(
        plan, layout, env.tracedirs, max_cap, rez_limit_factor, flow_path_limit_factor
    )
    (layout.campaign / "inputs.txt").write_text(
        f"{env.inputs.as_posix()}\n", encoding="utf-8"
    )
    write_assumptions(
        layout,
        env.inputs,
        len(chains),
        plan_data,
        max_cap,
        rez_limit_factor,
        flow_path_limit_factor,
        solve_flags,
    )
    selected = _stage_chains(chains, stage)
    if array is None and smoke:
        array = "0"
    if array is None and resume:
        array = incomplete_array(layout, selected)
        if not array:
            print(f"every chain in {layout.root} has completed its final period")
            return
    if array is None:
        array = _array(selected)
    script = SLURM_DIR / ("smoke.sbatch" if smoke else "chain.sbatch")
    # Only a submission into an existing launch directory may keep carried chain state.
    export = {"RESUME": "--resume"} if run else {}
    if solve_flags:
        export["SOLVE_FLAGS"] = solve_flags
    dependency = f"afterok:{after}" if after else None
    if dry_run:
        print(" ".join(sbatch_command(script, array, export, layout, env, dependency)))
    else:
        submit(script, array, export, layout, env, dependency)
    print(layout.root)
