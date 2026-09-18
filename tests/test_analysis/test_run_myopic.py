import json
import sys
from pathlib import Path

import pytest
import yaml

from analysis.benchmarks import run_myopic
from analysis.benchmarks.output_layout import OutputLayout
from analysis.benchmarks.run_myopic import (
    _completed_record,
    _parse_year_schedule,
    _require_schedule_covers_periods,
)


def test_campaign_command_keeps_fuel_curves_with_historical_flat_ccs(
    monkeypatch, tmp_path
):
    class StopBeforeSolve(Exception):
        pass

    def inspect_config(config, *args, **kwargs):
        inputs = yaml.safe_load(config.read_text())
        assert (
            inputs["biomass_supply_curve"]["curve_csv"]
            == "analysis/bioenergy_market/biomass_supply_curve_central.csv"
        )
        assert (
            inputs["gas_supply_curve"]["curve_csv"]
            == "analysis/gas_market/gas_supply_curve_central.csv"
        )
        assert inputs["carbon_pricing"]["tns_price"] == 89.93
        assert "ccs_supply_curve" not in inputs
        raise StopBeforeSolve

    monkeypatch.setattr(run_myopic, "_run_one_period", inspect_config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_myopic.py",
            "--run-id",
            "unit_fuel_defaults",
            "--periods",
            "2030",
            "--output-root",
            str(tmp_path),
            "--ccs-supply-curve",
            "none",
            "--tns-price",
            "89.93",
        ],
    )
    with pytest.raises(StopBeforeSolve):
        run_myopic.main()


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


def test_output_layout_paths_hang_off_one_root():
    layout = OutputLayout(Path("outputs"))

    assert layout.config("chain_2030") == Path("outputs/configs/chain_2030.yaml")
    assert layout.log("chain_2030") == Path("outputs/logs/chain_2030.log")
    assert layout.record("chain") == Path("outputs/records/chain.json")
    assert layout.network("chain_2030", "cost_optimal") == Path(
        "outputs/runs/chain_2030__cost_optimal/outputs/capacity_expansion.nc"
    )
    assert layout.chain_dir("chain") == Path("outputs/runs/chain")


def _write_record(layout: OutputLayout, run_id: str, status: str) -> None:
    layout.records.mkdir(parents=True, exist_ok=True)
    layout.record(run_id).write_text(
        json.dumps({"status": status, "objective_value": 1.0})
    )


def test_completed_record_returns_record_when_solve_and_network_exist(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "completed")
    network = layout.network("chain_2030", "cost_optimal")
    network.parent.mkdir(parents=True)
    network.write_bytes(b"")

    assert _completed_record(layout, "chain_2030", "cost_optimal") == {
        "status": "completed",
        "objective_value": 1.0,
    }


def test_completed_record_is_none_without_network(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "completed")

    assert _completed_record(layout, "chain_2030", "cost_optimal") is None


def test_completed_record_is_none_when_status_not_completed(tmp_path):
    layout = OutputLayout(tmp_path)
    _write_record(layout, "chain_2030", "timed_out")
    network = layout.network("chain_2030", "cost_optimal")
    network.parent.mkdir(parents=True)
    network.write_bytes(b"")

    assert _completed_record(layout, "chain_2030", "cost_optimal") is None
