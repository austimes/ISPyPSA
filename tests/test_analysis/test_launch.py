"""Tests for the launch command's Slurm array selection."""

import json

import pandas as pd

from analysis.env import OutputLayout
from analysis.hpc.launch import incomplete_array

LAST_PERIOD = 2060
ARCHETYPE = "cost_optimal"


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
    network = layout.network(f"{run_id}_{LAST_PERIOD}", ARCHETYPE)
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
