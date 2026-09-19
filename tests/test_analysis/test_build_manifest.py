import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.hpc.manifest import (
    build_caps_table,
    build_chain_table,
    write_manifest,
)

GIT_COMMIT = "abc1234"
TRACEDIRS = Path("/io/inputs/tracedirs")


@pytest.fixture
def plan():
    """A two-trajectory demand plan carrying the real central and stress loads."""
    return {
        "version": "test-plan-v1",
        "milestone_years": [2030, 2040, 2050, 2060],
        "delivery_fraction": 0.91,
        "demand_paths_source_twh": {
            "iasr_central": {"2030": 183, "2040": 268, "2050": 365, "2060": 431},
            "iasr_stress": {"2030": 225, "2040": 350, "2050": 490, "2060": 585},
        },
    }


def _schedule_rows(caps, trajectory, cap_key):
    """The four milestone rows of one (trajectory, cap schedule) pair."""
    selected = caps[(caps["trajectory"] == trajectory) & (caps["cap_key"] == cap_key)]
    return selected.reset_index(drop=True)


def test_caps_table_holds_the_central_0p001_schedule(plan, csv_str_to_df):
    caps = build_caps_table(plan, GIT_COMMIT)

    result = _schedule_rows(caps, "iasr_central", "cap0001")

    expected = csv_str_to_df("""
        run_id,               trajectory,    cap_key,  target_2050_t_per_mwh_delivered,  year,  intensity,     intensity_basis,  source_twh,  cap_t,     plan_version,   git_commit
        ext_central_cap0001,  iasr_central,  cap0001,  0.001,                            2030,  0.12,          delivered,        183,         19984000,  test-plan-v1,   abc1234
        ext_central_cap0001,  iasr_central,  cap0001,  0.001,                            2040,  0.010954451,   delivered,        268,         2672000,   test-plan-v1,   abc1234
        ext_central_cap0001,  iasr_central,  cap0001,  0.001,                            2050,  0.001,         delivered,        365,         332000,    test-plan-v1,   abc1234
        ext_central_cap0001,  iasr_central,  cap0001,  0.001,                            2060,  0.001,         delivered,        431,         392000,    test-plan-v1,   abc1234
    """)
    pd.testing.assert_frame_equal(
        result, expected, check_exact=False, rtol=1e-3, check_dtype=False
    )


def test_caps_table_holds_the_stress_0p02_schedule(plan, csv_str_to_df):
    caps = build_caps_table(plan, GIT_COMMIT)

    result = _schedule_rows(caps, "iasr_stress", "cap002")

    expected = csv_str_to_df("""
        run_id,             trajectory,   cap_key,  target_2050_t_per_mwh_delivered,  year,  intensity,    intensity_basis,  source_twh,  cap_t,     plan_version,  git_commit
        ext_stress_cap002,  iasr_stress,  cap002,   0.02,                             2030,  0.12,         delivered,        225,         24570000,  test-plan-v1,  abc1234
        ext_stress_cap002,  iasr_stress,  cap002,   0.02,                             2040,  0.048989795,  delivered,        350,         15603000,  test-plan-v1,  abc1234
        ext_stress_cap002,  iasr_stress,  cap002,   0.02,                             2050,  0.02,         delivered,        490,         8918000,   test-plan-v1,  abc1234
        ext_stress_cap002,  iasr_stress,  cap002,   0.02,                             2060,  0.02,         delivered,        585,         10647000,  test-plan-v1,  abc1234
    """)
    pd.testing.assert_frame_equal(
        result, expected, check_exact=False, rtol=1e-3, check_dtype=False
    )


def test_deepest_schedule_tightens_2060_onto_the_source_basis(plan, csv_str_to_df):
    caps = build_caps_table(plan, GIT_COMMIT)

    result = _schedule_rows(caps, "iasr_central", "cap00005").query("year == 2060")

    expected = csv_str_to_df("""
        run_id,                trajectory,    cap_key,   target_2050_t_per_mwh_delivered,  year,  intensity,  intensity_basis,  source_twh,  cap_t,  plan_version,  git_commit
        ext_central_cap00005,  iasr_central,  cap00005,  0.0005,                           2060,  0.0001,     source,           431,         43100,  test-plan-v1,  abc1234
    """)
    pd.testing.assert_frame_equal(
        result.reset_index(drop=True), expected, check_exact=False, check_dtype=False
    )


def test_chains_tsv_orders_price_chains_before_cap_chains(plan, tmp_path):
    caps = build_caps_table(plan, GIT_COMMIT)
    chains = build_chain_table(plan, caps, TRACEDIRS)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(plan), encoding="utf-8")

    write_manifest(caps, chains, tmp_path, plan_file)
    lines = (tmp_path / "chains.tsv").read_text(encoding="utf-8").splitlines()

    central, stress = (
        "/io/inputs/tracedirs/iasr_central.txt",
        "/io/inputs/tracedirs/iasr_stress.txt",
    )
    # 2 trajectories x (1 uncapped + 6 caps) + 2 price-calibrated trajectories x 3.
    assert len(lines) == 20
    assert lines[0] == f"ext_central_c0\t{central}\t--carbon-price 0"
    assert lines[1] == f"ext_stress_c0\t{stress}\t--carbon-price 0"
    assert lines[2] == f"ext_central_c150\t{central}\t--carbon-price 150"
    assert lines[7] == f"ext_stress_c550\t{stress}\t--carbon-price 550"
    assert lines[8].split("\t")[2].startswith("--co2-cap-t-schedule 2030:")
    assert (
        json.loads((tmp_path / "demand_plan.json").read_text(encoding="utf-8")) == plan
    )


def test_chain_args_carry_every_milestone_tonnage(plan, csv_str_to_df):
    caps = build_caps_table(plan, GIT_COMMIT)

    chains = build_chain_table(plan, caps, TRACEDIRS)

    result = chains[chains["run_id"] == "ext_central_cap0001"].reset_index(drop=True)
    expected = csv_str_to_df("""
        row,  run_id,               trajectory,    traces,                                 chain,    stage,  args
        16,   ext_central_cap0001,  iasr_central,  /io/inputs/tracedirs/iasr_central.txt,  cap0001,  2b,     --co2-cap-t-schedule 2030:19983600 2040:2671572 2050:332150 2060:392210
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)
