"""Stamp a launch directory, write its manifest and submit the campaign to Slurm.

One launch is one stamped directory, ``$IO_DIR/outputs/<stamp>_<run_set>``, holding the
manifest that decides what each Slurm array task solves and every product of the run.
The array index is the chain's row in ``campaign/chains.tsv``, so the manifest and the
array are written together and never drift apart. ``campaign/inputs.txt`` names the input
package the launch read, so a run's results can always be traced back to its inputs, and
``campaign/assumptions.json`` names what this launch varies -- its REZ limit factor, its cap
depth cut-off, its chain count and that input package -- so two run sets can be compared.

``submit`` is the single place that knows how a campaign job is handed to Slurm: the
account, partition, stdout path and the exported variables (``RUN_DIR``, ``REPO`` and
``RESUME``) that the sbatch scripts read. The deliverables builder submits its own
extract array through it as well, so the two entry points cannot disagree.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from analysis.env import REPO_ROOT, Env, OutputLayout
from analysis.hpc import manifest, tracedirs

SLURM_DIR = Path(__file__).parent / "slurm"
DEFAULT_PLAN = Path(__file__).parent / "demand_plan.json"


def sbatch_command(
    script: Path,
    array: str,
    export: dict[str, str],
    layout: OutputLayout,
    env: Env,
    dependency: str | None = None,
) -> list[str]:
    """The ``sbatch`` command line for one array submission of ``script``."""
    exported = {
        "RUN_DIR": layout.root.as_posix(),
        "REPO": REPO_ROOT.as_posix(),
        **export,
    }
    return [
        "sbatch",
        f"--array={array}",
        "--export=ALL,"
        + ",".join(f"{name}={value}" for name, value in exported.items()),
        *([f"--account={env.slurm_account}"] if env.slurm_account else []),
        *([f"--partition={env.slurm_partition}"] if env.slurm_partition else []),
        f"--output={(layout.campaign / 'slurm').as_posix()}/%x-%A_%a.out",
        *([f"--dependency={dependency}"] if dependency else []),
        script.as_posix(),
    ]


def submit(
    script: Path,
    array: str,
    export: dict[str, str],
    layout: OutputLayout,
    env: Env,
    dependency: str | None = None,
) -> str:
    """Submit one Slurm array job for this launch and return its job id.

    :param script: The sbatch script to run.
    :param array: Slurm array specification, e.g. ``0-40`` or ``3,7,9``.
    :param export: Extra variables to export on top of ``RUN_DIR`` and ``REPO``.
    :param layout: The launch directory the job writes into.
    :param env: Cluster account and partition.
    :param dependency: Slurm dependency expression, e.g. ``afterok:12345``.
    """
    (layout.campaign / "slurm").mkdir(parents=True, exist_ok=True)
    command = sbatch_command(script, array, export, layout, env, dependency)
    print(" ".join(command))
    result = subprocess.run(command, capture_output=True, text=True, check=True)
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


def incomplete_array(
    layout: OutputLayout, chains: pd.DataFrame, last_period: int
) -> str:
    """Slurm array specification covering only the chains that have not finished.

    :param layout: The launch directory to inspect.
    :param chains: The launch's chain table, whose ``row`` is the array index.
    :param last_period: Final milestone year of every chain.
    :return: A comma-separated index list, empty when every chain is complete.
    """
    rows = [
        chain.row
        for chain in chains.itertuples()
        if not _chain_is_complete(layout, chain.run_id, last_period)
    ]
    return ",".join(str(row) for row in rows)


def write_assumptions(
    layout: OutputLayout,
    inputs: Path,
    chains: int,
    max_cap: float | None,
    rez_limit_factor: float | None,
) -> None:
    """Record what this launch varies, so two run sets can be compared without reading their manifests."""
    (layout.campaign / "assumptions.json").write_text(
        json.dumps(
            {
                "rez_limit_factor": rez_limit_factor,
                "max_cap": max_cap,
                "chains": chains,
                "inputs": inputs.as_posix(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(
    run_set: str = "ext41",
    plan: Path = DEFAULT_PLAN,
    run: Path | None = None,
    resume: bool = False,
    smoke: bool = False,
    array: str | None = None,
    max_cap: float | None = None,
    rez_limit_factor: float | None = None,
    dry_run: bool = False,
) -> None:
    """Prepare a campaign launch and submit its chains to Slurm.

    :param run_set: Name a new launch directory is stamped with, under ``$IO_DIR/outputs``.
    :param plan: Demand plan JSON holding the trajectories, loads and milestone years.
    :param run: Existing launch directory to submit into, instead of stamping a new one.
    :param resume: Submit only the chains whose final period has not completed; requires
        ``run``, because a freshly stamped directory has no chain to resume.
    :param smoke: Submit the single NSW two-period gate chain instead of the campaign.
    :param array: Slurm array specification, overriding the one derived from the manifest.
    :param max_cap: Launch only the cap chains whose 2050 target intensity in t CO2e/MWh
        delivered is at or below this value, dropping the price chains and the shallower
        caps; omit to launch the whole campaign.
    :param rez_limit_factor: Relax every renewable energy zone (REZ) transmission,
        expansion and resource limit by this factor in every chain of the launch, as a
        sensitivity against the IASR limits; omit for the IASR limits.
    :param dry_run: Write the manifest and print the sbatch command, building no trace
        directories and submitting nothing.
    """
    if resume and run is None:
        raise ValueError("--resume needs --run: name the launch directory to resume")
    env = Env.from_env()
    layout = OutputLayout(run) if run else env.new_run(run_set)
    if not dry_run:
        tracedirs.build(env.traces, env.tracedirs, plan)
    chains = manifest.build(plan, layout, env.tracedirs, max_cap, rez_limit_factor)
    (layout.campaign / "inputs.txt").write_text(
        f"{env.inputs.as_posix()}\n", encoding="utf-8"
    )
    write_assumptions(layout, env.inputs, len(chains), max_cap, rez_limit_factor)
    if array is None and smoke:
        array = "0"
    if array is None and resume:
        milestones = json.loads(plan.read_text(encoding="utf-8"))["milestone_years"]
        array = incomplete_array(layout, chains, milestones[-1])
        if not array:
            print(f"every chain in {layout.root} has completed its final period")
            return
    if array is None:
        array = f"0-{len(chains) - 1}"
    script = SLURM_DIR / ("smoke.sbatch" if smoke else "chain.sbatch")
    # Only a submission into an existing launch directory may keep carried chain state.
    export = {"RESUME": "--resume"} if run else {}
    if dry_run:
        print(" ".join(sbatch_command(script, array, export, layout, env)))
    else:
        submit(script, array, export, layout, env)
    print(layout.root)
