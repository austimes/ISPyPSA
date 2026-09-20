"""Tests for the launch command's Slurm array selection."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from analysis import env as env_module
from analysis.env import RUN_STAMP_FORMAT, Env, OutputLayout
from analysis.hpc.launch import incomplete_array, main, sbatch_command

LAST_PERIOD = 2060


def _chains() -> pd.DataFrame:
    """Three chains in array order, as the manifest writes them."""
    return pd.DataFrame(
        {
            "row": [0, 1, 2],
            "run_id": ["ext_central_c0", "ext_stress_c0", "ext_central_cap002"],
        }
    )


def _write_record(layout: OutputLayout, run_id: str, status: str) -> None:
    """A finished period's record, as the solve driver leaves it."""
    layout.records.mkdir(parents=True, exist_ok=True)
    layout.record(f"{run_id}_{LAST_PERIOD}").write_text(
        json.dumps({"status": status}), encoding="utf-8"
    )


def _write_network(layout: OutputLayout, run_id: str) -> None:
    """A solved network on disk, standing in for a chain whose record was lost."""
    network = layout.network(f"{run_id}_{LAST_PERIOD}")
    network.parent.mkdir(parents=True, exist_ok=True)
    network.write_bytes(b"")


def test_resume_selects_chains_with_no_finished_final_period(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "ext_central_c0", "completed")
    _write_record(layout, "ext_stress_c0", "failed")
    _write_network(layout, "ext_central_cap002")

    assert incomplete_array(layout, _chains(), LAST_PERIOD) == "1"


def test_resume_selects_nothing_when_every_chain_finished(tmp_path):
    layout = OutputLayout(tmp_path)
    for run_id in _chains()["run_id"]:
        _write_record(layout, run_id, "completed")

    assert incomplete_array(layout, _chains(), LAST_PERIOD) == ""


def test_resume_selects_every_chain_in_an_empty_run_dir(tmp_path):
    assert incomplete_array(OutputLayout(tmp_path), _chains(), LAST_PERIOD) == "0,1,2"


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

    main(run_set="ext41", dry_run=True)

    assert _assumptions(tmp_path) == {
        "rez_limit_factor": None,
        "max_cap": None,
        "chains": 41,
        "inputs": package.as_posix(),
    }


def test_a_relaxed_deep_cap_launch_records_the_factor_and_its_narrowed_chain_count(
    monkeypatch, tmp_path
):
    package = _stamped_inputs_package(monkeypatch, tmp_path)

    main(run_set="ext41_rezx2", max_cap=0.005, rez_limit_factor=2.0, dry_run=True)

    assert _assumptions(tmp_path) == {
        "rez_limit_factor": 2.0,
        "max_cap": 0.005,
        "chains": 20,
        "inputs": package.as_posix(),
    }


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
