"""Tests for the launch command's Slurm array selection."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from analysis import env as env_module
from analysis.env import RUN_STAMP_FORMAT, Env, OutputLayout
from analysis.hpc.launch import (
    DEFAULT_PLAN,
    Job,
    incomplete_chains,
    job_plan,
    main,
    sbatch_command,
)
from analysis.hpc.manifest import build_caps_table, build_chain_table


def _chains() -> pd.DataFrame:
    """Three chains in array order, as the manifest writes them: a base chain and two branches."""
    return pd.DataFrame(
        {
            "row": [0, 1, 2],
            "run_id": [
                "ext_step_change_sc",
                "ext_step_change_b2030_d100_cap019673",
                "ext_step_change_b2050_d135_cap0006925",
            ],
            "stage": ["base", "branch", "branch"],
            "last_period": [2050, 2030, 2050],
        }
    )


def _write_record(layout: OutputLayout, run_id: str, year: int, status: str) -> None:
    """A finished period's record, as the solve driver leaves it."""
    layout.records.mkdir(parents=True, exist_ok=True)
    layout.record(f"{run_id}_{year}").write_text(
        json.dumps({"status": status}), encoding="utf-8"
    )


def _write_network(layout: OutputLayout, run_id: str, year: int) -> None:
    """A solved network on disk, standing in for a chain whose record was lost."""
    network = layout.network(f"{run_id}_{year}")
    network.parent.mkdir(parents=True, exist_ok=True)
    network.write_bytes(b"")


def test_resume_judges_each_chain_by_its_own_last_period(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "ext_step_change_sc", 2050, "completed")
    # The 2030 branch ends at 2030, so its 2050 record is beside the point.
    _write_record(layout, "ext_step_change_b2030_d100_cap019673", 2050, "completed")
    _write_network(layout, "ext_step_change_b2050_d135_cap0006925", 2050)

    assert incomplete_chains(layout, _chains())["row"].tolist() == [1]


def test_resume_selects_nothing_when_every_chain_finished(tmp_path):
    layout = OutputLayout(tmp_path)
    for chain in _chains().itertuples():
        _write_record(layout, chain.run_id, chain.last_period, "completed")

    assert incomplete_chains(layout, _chains()).empty


def test_resume_selects_every_chain_in_an_empty_run_dir(tmp_path):
    assert incomplete_chains(OutputLayout(tmp_path), _chains())["row"].tolist() == [
        0,
        1,
        2,
    ]


def test_resume_without_a_run_directory_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="--resume needs --run"):
        main(resume=True)

    assert not (tmp_path / "outputs").exists()


def test_dry_run_stamps_a_launch_directory_and_records_the_inputs_it_read(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.delenv("MSM_INPUTS", raising=False)
    package = tmp_path / "inputs" / "2026-09-17T13.54_isp2026_final"
    package.mkdir(parents=True)

    main(run_set="ext41", dry_run=True)

    (launch,) = (tmp_path / "outputs").iterdir()
    stamp, _, run_set = launch.name.partition("_")
    assert (run_set, bool(datetime.strptime(stamp, RUN_STAMP_FORMAT))) == (
        "ext41",
        True,
    )
    assert (launch / "campaign" / "inputs.txt").read_text(
        encoding="utf-8"
    ) == f"{package.as_posix()}\n"
    assert launch.as_posix() in capsys.readouterr().out


def _stamped_inputs_package(monkeypatch, tmp_path) -> Path:
    """An empty stamped input package, the newest one a launch into ``tmp_path`` will read."""
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.delenv("MSM_INPUTS", raising=False)
    package = tmp_path / "inputs" / "2026-09-17T13.54_isp2026_final"
    package.mkdir(parents=True)
    return package


def _assumptions(tmp_path) -> dict:
    """The one launch's ``campaign/assumptions.json``, parsed."""
    (launch,) = (tmp_path / "outputs").iterdir()
    return json.loads(
        (launch / "campaign" / "assumptions.json").read_text(encoding="utf-8")
    )


def test_a_plain_launch_records_null_sensitivity_settings_and_the_whole_campaign(
    monkeypatch, tmp_path
):
    package = _stamped_inputs_package(monkeypatch, tmp_path)

    main(run_set="sc5", dry_run=True)

    assumptions = _assumptions(tmp_path)
    assert assumptions["increments"]["cells"] == 64
    assert assumptions == {
        "rez_limit_factor": None,
        "flow_path_limit_factor": None,
        "solve_flags": None,
        "max_cap": None,
        "chains": 449,
        "increments": assumptions["increments"],
        "inputs": package.as_posix(),
    }


def test_a_relaxed_launch_records_its_factors(monkeypatch, tmp_path):
    _stamped_inputs_package(monkeypatch, tmp_path)

    main(
        run_set="sc5_rezx4",
        rez_limit_factor=4.0,
        flow_path_limit_factor=4.0,
        dry_run=True,
    )

    assumptions = _assumptions(tmp_path)
    assert (assumptions["rez_limit_factor"], assumptions["flow_path_limit_factor"]) == (
        4.0,
        4.0,
    )


def _submitted(output: str) -> list[tuple[str, str | None]]:
    """Each printed sbatch command's array and dependency, in submission order."""
    commands = [
        line.split() for line in output.splitlines() if line.startswith("sbatch")
    ]
    return [
        (
            next(flag for flag in command if flag.startswith("--array=")),
            next((flag for flag in command if flag.startswith("--dependency=")), None),
        )
        for command in commands
    ]


def _year_rows(year: int) -> str:
    """The manifest rows of one increment year of the shipped plan: 64 cells after the base row."""
    first = 1 + (year - 2030) // 5 * 64
    return ",".join(str(row) for row in range(first, first + 64))


def test_job_plan_steps_the_base_chain_and_holds_each_year_behind_its_seed_period():
    plan = json.loads(DEFAULT_PLAN.read_text(encoding="utf-8"))
    chains = build_chain_table(
        plan, build_caps_table(plan, "abc1234"), Path("/io/tracedirs")
    )
    milestones = plan["milestone_years"]

    jobs = job_plan(chains, milestones, milestones)

    base = [
        Job(f"base_{year}", "0", f"base_{before}" if before else None)
        for before, year in zip([None, *milestones], milestones)
    ]
    branches = [
        Job(f"branch_{year}", _year_rows(year), f"base_{seed}")
        for seed, year in zip(milestones, plan["increment_years"])
    ]
    assert jobs == base + branches


def test_a_launch_chains_its_base_periods_and_holds_each_year_behind_its_seed(
    monkeypatch, tmp_path, capsys
):
    _stamped_inputs_package(monkeypatch, tmp_path)

    main(run_set="sc5", after="999", dry_run=True)

    assert _submitted(capsys.readouterr().out) == [
        ("--array=0", "--dependency=afterok:999"),
        ("--array=0", "--dependency=afterok:<base_2026>"),
        ("--array=0", "--dependency=afterok:<base_2030>"),
        ("--array=0", "--dependency=afterok:<base_2035>"),
        ("--array=0", "--dependency=afterok:<base_2040>"),
        ("--array=0", "--dependency=afterok:<base_2045>"),
        ("--array=0", "--dependency=afterok:<base_2050>"),
        ("--array=0", "--dependency=afterok:<base_2055>"),
        (f"--array={_year_rows(2030)}", "--dependency=afterok:<base_2026>"),
        (f"--array={_year_rows(2035)}", "--dependency=afterok:<base_2030>"),
        (f"--array={_year_rows(2040)}", "--dependency=afterok:<base_2035>"),
        (f"--array={_year_rows(2045)}", "--dependency=afterok:<base_2040>"),
        (f"--array={_year_rows(2050)}", "--dependency=afterok:<base_2045>"),
        (f"--array={_year_rows(2055)}", "--dependency=afterok:<base_2050>"),
        (f"--array={_year_rows(2060)}", "--dependency=afterok:<base_2055>"),
    ]


def test_a_resume_keeps_the_manifest_and_submits_only_unsolved_periods_and_cells(
    monkeypatch, tmp_path, capsys
):
    _stamped_inputs_package(monkeypatch, tmp_path)
    main(
        run_set="sc5", rez_limit_factor=4.0, solve_flags="--gas-unblended", dry_run=True
    )
    (launch,) = (tmp_path / "outputs").iterdir()
    manifest_before = (launch / "campaign" / "chains.tsv").read_text(encoding="utf-8")
    layout = OutputLayout(launch)
    for year in (2026, 2030):
        _write_record(layout, "ext_step_change_sc", year, "completed")
    capsys.readouterr()

    main(run=launch, resume=True, dry_run=True)

    assert (launch / "campaign" / "chains.tsv").read_text(
        encoding="utf-8"
    ) == manifest_before
    assert _submitted(capsys.readouterr().out) == [
        ("--array=0", None),
        ("--array=0", "--dependency=afterok:<base_2035>"),
        ("--array=0", "--dependency=afterok:<base_2040>"),
        ("--array=0", "--dependency=afterok:<base_2045>"),
        ("--array=0", "--dependency=afterok:<base_2050>"),
        ("--array=0", "--dependency=afterok:<base_2055>"),
        (f"--array={_year_rows(2030)}", None),
        (f"--array={_year_rows(2035)}", None),
        (f"--array={_year_rows(2040)}", "--dependency=afterok:<base_2035>"),
        (f"--array={_year_rows(2045)}", "--dependency=afterok:<base_2040>"),
        (f"--array={_year_rows(2050)}", "--dependency=afterok:<base_2045>"),
        (f"--array={_year_rows(2055)}", "--dependency=afterok:<base_2050>"),
        (f"--array={_year_rows(2060)}", "--dependency=afterok:<base_2055>"),
    ]


def test_new_settings_for_a_launch_that_already_has_a_manifest_are_refused(
    monkeypatch, tmp_path
):
    _stamped_inputs_package(monkeypatch, tmp_path)
    main(run_set="sc5", dry_run=True)
    (launch,) = (tmp_path / "outputs").iterdir()

    with pytest.raises(ValueError, match="already has a manifest"):
        main(run=launch, resume=True, rez_limit_factor=4.0, dry_run=True)


def test_sbatch_command_omits_the_account_and_partition_the_environment_leaves_unset(
    tmp_path,
):
    env = Env(io_dir=tmp_path, slurm_account=None, slurm_partition=None)
    layout = OutputLayout(tmp_path / "outputs" / "2026-09-18T10.00_ext41")

    command = sbatch_command(Path("chain.sbatch"), "0-2", {}, layout, env)

    assert not [
        flag for flag in command if flag.startswith(("--account", "--partition"))
    ]


def test_sbatch_command_passes_the_account_and_partition_the_environment_names(
    tmp_path,
):
    env = Env(io_dir=tmp_path, slurm_account="OD-1", slurm_partition="defq")
    layout = OutputLayout(tmp_path / "outputs" / "2026-09-18T10.00_ext41")

    command = sbatch_command(Path("chain.sbatch"), "0-2", {}, layout, env)

    assert "--account=OD-1" in command
    assert "--partition=defq" in command
