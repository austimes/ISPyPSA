import json
import sys
from pathlib import Path

import pytest

from analysis.benchmarks.output_layout import OutputLayout
from analysis.benchmarks.run_myopic import (
    DEFAULT_BIOMASS_SUPPLY_CURVE,
    DEFAULT_GAS_SUPPLY_CURVE,
    _completed_record,
    _parse_year_schedule,
    _require_schedule_covers_periods,
    _write_period_config,
    main,
)


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


def test_period_config_includes_production_supply_curves_and_flat_tns(tmp_path):
    layout = OutputLayout(tmp_path)

    config = _write_period_config(
        "campaign_2060",
        2060,
        None,
        tns_price=89.93,
        gas_supply_curve_csv=DEFAULT_GAS_SUPPLY_CURVE,
        biomass_supply_curve_csv=DEFAULT_BIOMASS_SUPPLY_CURVE,
        gas_unblended=True,
        layout=layout,
    ).read_text()

    assert "tns_price: 89.93" in config
    assert (f'gas_supply_curve:\n  curve_csv: "{DEFAULT_GAS_SUPPLY_CURVE}"') in config
    assert (
        f'biomass_supply_curve:\n  curve_csv: "{DEFAULT_BIOMASS_SUPPLY_CURVE}"'
    ) in config
    assert "blend_biomethane_into_gas: false" in config
    assert "ccs_supply_curve:" not in config


def test_main_rejects_unsupported_ccs_supply_curve_file(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_myopic.py",
            "--run-id",
            "campaign",
            "--ccs-supply-curve",
            "unsupported.csv",
        ],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


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
