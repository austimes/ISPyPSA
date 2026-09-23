import json
import shlex
from pathlib import Path

import pandas as pd
import pytest
import yaml
from cyclopts import App

from analysis.env import MODEL_DATA, OutputLayout
from analysis.hpc import solve
from analysis.hpc.solve import (
    _completed_record,
    _parse_year_schedule,
    _require_schedule_covers_periods,
)

SLURM_DIR = Path(solve.__file__).parent / "slurm"

# Shell expansions the sbatch scripts rely on, longest first so the command
# substitution is replaced before the bare variable inside it.
SBATCH_SUBSTITUTIONS = {
    '$(cat "$TRACES")': "2030:/io/tracedirs/c/2030 2040:/io/tracedirs/c/2040",
    "${RESUME:-}": "--resume",
    "${SOLVE_FLAGS:-}": "",
    "$SLURM_CPUS_PER_TASK": "64",
    "$RUN_ID": "ext_step_change_sc",
    "$RUN_DIR": "/io/outputs/2026-09-18T10.00_sc5",
    "$TRACES": "2030:/io/tracedirs/c/2030 2040:/io/tracedirs/c/2040",
    "$ARGS": "--periods 2030 2040 --co2-cap-t-schedule 2030:6e6 2040:2e6",
}


class StopBeforeSolve(Exception):
    """Raised by a stubbed period runner so a test stops at the generated config."""


def _point_io_dir_at(monkeypatch, tmp_path: Path) -> None:
    """Point ``IO_DIR`` at ``tmp_path``, holding the one stamped input package a solve reads."""
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    (tmp_path / "inputs" / "2026-09-17T13.54_test_inputs").mkdir(parents=True)


def test_chain_keeps_fuel_curves_with_ccs_opted_out(monkeypatch, tmp_path):
    _point_io_dir_at(monkeypatch, tmp_path)

    def inspect_config(cfg, *args, **kwargs):
        inputs = yaml.safe_load(cfg.read_text())
        assert (
            inputs["gas_supply_curve"]["curve_csv"]
            == (MODEL_DATA / "gas_supply_curve_central_held_to_2060.csv").as_posix()
        )
        assert (
            inputs["biomass_supply_curve"]["curve_csv"]
            == (MODEL_DATA / "biomass_supply_curve_central_held_to_2060.csv").as_posix()
        )
        assert inputs["carbon_pricing"]["tns_price"] == 89.93
        assert "ccs_supply_curve" not in inputs
        raise StopBeforeSolve

    monkeypatch.setattr(solve, "_run_one_period", inspect_config)

    with pytest.raises(StopBeforeSolve):
        solve.main(
            run_id="unit_fuel_defaults",
            output_root=tmp_path / "run",
            periods=[2030],
            ccs_supply_curve="none",
            tns_price=89.93,
        )


def test_cli_parses_every_period_of_a_chain(monkeypatch, tmp_path):
    _point_io_dir_at(monkeypatch, tmp_path)
    solved = []

    def record_period(cfg, run_id, *args, **kwargs):
        solved.append(run_id)
        return {"status": "completed"}

    monkeypatch.setattr(solve, "_run_one_period", record_period)
    app = App()
    app.command(solve.main, name="solve")

    app(
        [
            "solve",
            "--run-id",
            "cli_chain",
            "--output-root",
            str(tmp_path / "run"),
            "--periods",
            "2030",
            "2040",
            "--rep-weeks",
            "1",
            "6",
            "--no-named-weeks",
            "--co2-cap-t-schedule",
            "2030:6e6",
            "2040:2e6",
        ],
        result_action="return_value",
    )

    assert solved == ["cli_chain_2030", "cli_chain_2040"]
    chain_record = json.loads(
        (tmp_path / "run" / "records" / "cli_chain.json").read_text()
    )
    assert chain_record["periods"] == [2030, 2040]
    assert chain_record["co2_cap_t_schedule"] == {"2030": 6000000.0, "2040": 2000000.0}


def test_parse_year_schedule_casts_values():
    schedule = _parse_year_schedule(["2030:19984000", "2040:2.672e6"], float)

    assert schedule == {2030: 19984000.0, 2040: 2672000.0}


def test_parse_year_schedule_keeps_paths_as_strings():
    schedule = _parse_year_schedule(
        ["2030:/scratch/central_2030", "2060:C:/t/x_2060"], str
    )

    assert schedule == {2030: "/scratch/central_2030", 2060: "C:/t/x_2060"}


@pytest.mark.parametrize("token", ["2030", "abcd:1", "2030-1"])
def test_parse_year_schedule_rejects_malformed_tokens(token):
    with pytest.raises(ValueError, match="YEAR:VALUE"):
        _parse_year_schedule([token], float)


def test_parse_year_schedule_rejects_duplicate_years():
    with pytest.raises(ValueError, match="appears twice"):
        _parse_year_schedule(["2030:1", "2030:2"], float)


def test_require_schedule_covers_periods_names_missing_years():
    with pytest.raises(
        ValueError,
        match=r"--co2-cap-t-schedule has no entry for periods \[2050, 2060\]",
    ):
        _require_schedule_covers_periods(
            {2030: 1.0, 2040: 2.0}, [2030, 2040, 2050, 2060], "--co2-cap-t-schedule"
        )


def _write_record(layout: OutputLayout, run_id: str, status: str) -> None:
    layout.records.mkdir(parents=True, exist_ok=True)
    layout.record(run_id).write_text(
        json.dumps({"status": status, "objective_value": 1.0})
    )


def test_completed_record_returns_record_when_solve_and_network_exist(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "completed")
    network = layout.network("chain_2030")
    network.parent.mkdir(parents=True)
    network.write_bytes(b"")

    assert _completed_record(layout, "chain_2030") == {
        "status": "completed",
        "objective_value": 1.0,
    }


def test_completed_record_is_none_without_network(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "completed")

    assert _completed_record(layout, "chain_2030") is None


def test_completed_record_is_none_when_status_not_completed(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "timed_out")
    network = layout.network("chain_2030")
    network.parent.mkdir(parents=True)
    network.write_bytes(b"")

    assert _completed_record(layout, "chain_2030") is None


def _runner_flags_for(monkeypatch, tmp_path: Path, year: int, **kwargs) -> list[str]:
    """The runner flags one period is launched with, with the solve itself stubbed out."""
    captured: list[str] = []

    def capture(cfg, run_id, budget_min, layout, runner_flags):
        captured.extend(runner_flags)
        return {"status": "failed"}

    monkeypatch.setattr(solve, "_run_one_period", capture)
    with pytest.raises(SystemExit):
        solve.main(
            run_id=f"pin_{year}", output_root=tmp_path / "run", periods=[year], **kwargs
        )
    return captured


def test_pinned_periods_take_their_own_allowances_and_only_the_pipeline_period_the_rush(
    monkeypatch, tmp_path
):
    _point_io_dir_at(monkeypatch, tmp_path)
    pin = {
        "reducible_existing": True,
        "pipeline_period": 2030,
        "new_entrant_cap_mw": ["2026:500", "2030:19000"],
        "new_entrant_storage_cap_mw": ["2026:400", "2030:6000"],
        "pipeline_rush_charge": "98000,26000",
    }

    early = _runner_flags_for(monkeypatch, tmp_path, 2026, **pin)
    pinned = _runner_flags_for(monkeypatch, tmp_path, 2030, **pin)
    later = _runner_flags_for(monkeypatch, tmp_path, 2035, **pin)

    assert early[-4:] == [
        "--new-entrant-cap-mw",
        "500.0",
        "--new-entrant-storage-cap-mw",
        "400.0",
    ]
    assert pinned[-6:] == [
        "--new-entrant-cap-mw",
        "19000.0",
        "--new-entrant-storage-cap-mw",
        "6000.0",
        "--pipeline-rush-charge",
        "98000,26000",
    ]
    assert "--reducible-existing" not in early + pinned
    assert "--reducible-existing" in later and "--new-entrant-cap-mw" not in later
    assert "--pipeline-rush-charge" not in later


def _seed_state(layout: OutputLayout, run_id: str, years: list[int]) -> None:
    """A finished chain's carried state: one tranche and one retention directory per year."""
    for year in years:
        for name in ("tranches", "retention"):
            directory = layout.chain_dir(run_id) / name / str(year)
            directory.mkdir(parents=True)
            (directory / "state.parquet").write_bytes(b"")


def test_seeding_copies_only_the_years_before_the_branch_period(tmp_path):
    layout = OutputLayout(tmp_path)
    _seed_state(layout, "ext_step_change_sc", [2030, 2035, 2040])

    seeded = solve._seed_chain_state(layout, "ext_step_change_sc", "branch", 2040)

    branch = layout.chain_dir("branch")
    assert seeded == {"run_id": "ext_step_change_sc", "years": [2030, 2035]}
    assert sorted(p.name for p in (branch / "tranches").iterdir()) == ["2030", "2035"]
    assert sorted(p.name for p in (branch / "retention").iterdir()) == ["2030", "2035"]


def test_seeding_from_a_chain_with_no_state_is_refused(tmp_path):
    layout = OutputLayout(tmp_path)

    with pytest.raises(FileNotFoundError, match="no carried state"):
        solve._seed_chain_state(layout, "ext_step_change_sc", "branch", 2040)


def test_pin_base_stock_holds_the_existing_fleet_at_the_retained_level():
    from analysis.model.retirement import make_existing_reducible

    generators = pd.DataFrame(
        {"name": ["Coal A"], "p_nom": [700.0], "p_nom_extendable": [False]}
    )

    make_existing_reducible(generators, ["Coal A"], {"Coal A": 400.0}, pin=True)

    expected = pd.DataFrame(
        {
            "name": ["Coal A"],
            "p_nom": [400.0],
            "p_nom_extendable": [True],
            "p_nom_max": [400.0],
            "p_nom_min": [400.0],
            "capital_cost": [0.0],
        }
    )
    pd.testing.assert_frame_equal(generators, expected)


def _sbatch_solve_tokens(script: str) -> list[str]:
    """The ``msm solve`` argument list one sbatch script runs, with its shell expansions filled in."""
    text = (SLURM_DIR / script).read_text(encoding="utf-8").replace("\\\n", " ")
    command = next(
        line for line in text.splitlines() if "uv run --no-sync msm solve" in line
    )
    for name, value in SBATCH_SUBSTITUTIONS.items():
        command = command.replace(name, value)
    return shlex.split(command)[len("uv run --no-sync msm".split()) :]


@pytest.mark.parametrize(
    "script, periods",
    [("chain.sbatch", [2030, 2040]), ("smoke.sbatch", [2030, 2035])],
)
def test_sbatch_command_lines_bind_to_the_solve_cli(script, periods):
    app = App()
    app.command(solve.main, name="solve")

    command, bound, _ = app.parse_args(
        _sbatch_solve_tokens(script), exit_on_error=False
    )

    assert command is solve.main
    assert bound.kwargs["periods"] == periods
