import json

import pandas as pd
import pytest
import yaml
from cyclopts import App

from analysis.env import MODEL_DATA, OutputLayout
from analysis.hpc import solve
from analysis.hpc.solve import (
    _completed_record,
    _held_curve_csv,
    _hold_curve_to_years,
    _parse_year_schedule,
    _require_schedule_covers_periods,
)


class StopBeforeSolve(Exception):
    """Raised by a stubbed period runner so a test stops at the generated config."""


def test_chain_keeps_fuel_curves_with_ccs_opted_out(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))

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
    monkeypatch.setenv("IO_DIR", str(tmp_path))
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


def test_hold_curve_repeats_last_year_for_each_missing_year(csv_str_to_df):
    curve = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2054,           100,    0.0
        existing,  2055,           110,    0.0
        imports,   2055,           20,     4.5
    """)

    held = _hold_curve_to_years(curve, [2055, 2060, 2070])

    expected = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2054,           100,    0.0
        existing,  2055,           110,    0.0
        imports,   2055,           20,     4.5
        existing,  2060,           110,    0.0
        imports,   2060,           20,     4.5
        existing,  2070,           110,    0.0
        imports,   2070,           20,     4.5
    """)
    pd.testing.assert_frame_equal(held, expected, check_dtype=False)


def test_hold_curve_is_identity_inside_published_span(csv_str_to_df):
    curve = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2050,           100,    0.0
        existing,  2055,           110,    0.0
    """)

    held = _hold_curve_to_years(curve, [2050, 2055])

    pd.testing.assert_frame_equal(held, curve)


def _write_curve(path, csv_str_to_df) -> None:
    csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2050,           100,    0.0
        existing,  2055,           110,    0.0
    """).to_csv(path, index=False, lineterminator="\n")


def test_held_curve_csv_writes_a_held_copy_and_warns(tmp_path, csv_str_to_df, caplog):
    curve_csv = tmp_path / "gas_supply_curve_central.csv"
    _write_curve(curve_csv, csv_str_to_df)

    with caplog.at_level("WARNING"):
        held_csv = _held_curve_csv(str(curve_csv), [2050, 2060], tmp_path / "configs")

    assert held_csv == str(tmp_path / "configs" / "gas_supply_curve_central_held.csv")
    assert (
        "Supply curve gas_supply_curve_central.csv held at FY2055 for investment "
        "periods beyond the published data: [2060]"
    ) in caplog.text
    expected = csv_str_to_df("""
        tranche,   financial_year, cap_pj, adder_$/gj
        existing,  2050,           100,    0.0
        existing,  2055,           110,    0.0
        existing,  2060,           110,    0.0
    """)
    pd.testing.assert_frame_equal(pd.read_csv(held_csv), expected, check_dtype=False)


def test_held_curve_csv_keeps_a_curve_that_already_covers_the_periods(
    tmp_path, csv_str_to_df, caplog
):
    curve_csv = tmp_path / "gas_supply_curve_central.csv"
    _write_curve(curve_csv, csv_str_to_df)

    with caplog.at_level("WARNING"):
        held_csv = _held_curve_csv(str(curve_csv), [2030, 2050], tmp_path / "configs")

    assert held_csv == str(curve_csv)
    assert "Supply curve" not in caplog.text


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
