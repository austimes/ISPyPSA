import json
from pathlib import Path

import pandas as pd
import pytest

from analysis.hpc.launch import DEFAULT_PLAN
from analysis.hpc.manifest import build_caps_table, build_chain_table, write_manifest

GIT_COMMIT = "abc1234"
TRACEDIRS = Path("/io/inputs/tracedirs")


@pytest.fixture
def plan():
    """The shipped demand plan: the Step Change base chain and its increment grid."""
    return json.loads(DEFAULT_PLAN.read_text(encoding="utf-8"))


@pytest.fixture
def caps(plan):
    """Every cap of the campaign, one row per (chain, year)."""
    return build_caps_table(plan, GIT_COMMIT)


@pytest.fixture
def chains(plan, caps):
    """Every chain of the campaign in Slurm array order."""
    return build_chain_table(plan, caps, TRACEDIRS)


def test_manifest_is_the_base_chain_then_every_increment_cell(chains, csv_str_to_df):
    result = chains.groupby("stage", as_index=False).agg(
        rows=("row", "size"), first_row=("row", "min"), last_row=("row", "max")
    )

    expected = csv_str_to_df("""
        stage,   rows,  first_row,  last_row
        base,    1,     0,          0
        branch,  60,    1,          60
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_every_increment_row_solves_only_its_own_year(chains, csv_str_to_df):
    branches = chains[chains["stage"] == "branch"]

    result = (
        branches.assign(
            periods=branches["args"].str.extract(r"--periods (\d+)")[0].astype(int)
        )
        .groupby(["branch_year", "periods", "last_period"], as_index=False)
        .size()
    )

    expected = csv_str_to_df("""
        branch_year,  periods,  last_period,  size
        2030,         2030,     2030,         12
        2035,         2035,     2035,         12
        2040,         2040,     2040,         12
        2045,         2045,     2045,         12
        2050,         2050,     2050,         12
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_sampled_caps_are_the_cell_intensity_at_the_cell_load(caps, csv_str_to_df):
    sampled = [
        ("ext_step_change_sc", 2030),
        ("ext_step_change_b2040_d120_cap001034", 2040),
    ]

    result = (
        caps.set_index(["run_id", "year"])
        .loc[sampled, ["intensity", "intensity_basis", "source_twh", "cap_t"]]
        .reset_index()
    )

    expected = csv_str_to_df("""
        run_id,                                year,  intensity,  intensity_basis,  source_twh,  cap_t
        ext_step_change_sc,                    2030,  0.19673,    source,           202.73,      39883073
        ext_step_change_b2040_d120_cap001034,  2040,  0.01034,    source,           338.724,     3502406
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_chains_tsv_leads_with_the_base_chain_the_branches_seed_from(
    plan, caps, chains, tmp_path
):
    write_manifest(caps, chains, tmp_path, plan)

    lines = (tmp_path / "chains.tsv").read_text(encoding="utf-8").splitlines()

    traces = "/io/inputs/tracedirs/iasr_step_change.txt"
    assert len(lines) == 61
    assert lines[0] == (
        f"ext_step_change_sc\t{traces}\t--periods 2030 2035 2040 2045 2050 "
        "--co2-cap-t-schedule 2030:39883073 2035:15891510 2040:11674687 2045:8345279 "
        "2050:4460254 --pipeline-period 2030 --new-entrant-cap-mw 19000 "
        "--new-entrant-storage-cap-mw 6000"
    )
    assert lines[1] == (
        "ext_step_change_b2030_d100_cap019673\t"
        "/io/inputs/tracedirs/iasr_step_change_b2030_d100.txt\t"
        "--periods 2030 --co2-cap-t-schedule 2030:39883073 "
        "--seed-state-from ext_step_change_sc --pin-base-stock "
        "--pipeline-period 2030 --new-entrant-cap-mw 19000 "
        "--new-entrant-storage-cap-mw 6000"
    )


def test_written_plan_carries_the_grid_demand_trajectories(
    plan, caps, chains, tmp_path
):
    write_manifest(caps, chains, tmp_path, plan)

    written = json.loads((tmp_path / "demand_plan.json").read_text(encoding="utf-8"))

    paths = written["increment_demand_paths_source_twh"]
    assert len(paths) == 25
    assert paths["iasr_step_change_b2035_d110"] == pytest.approx({"2035": 271.018})


def test_limit_factors_are_appended_to_every_chain_of_the_launch(plan, caps):
    chains = build_chain_table(
        plan, caps, TRACEDIRS, rez_limit_factor=4.0, flow_path_limit_factor=4.0
    )

    assert (
        chains["args"]
        .str.endswith(" --rez-limit-factor 4.0 --flow-path-limit-factor 4.0")
        .all()
    )


def test_max_cap_is_refused_by_an_increment_grid_plan(plan, caps):
    with pytest.raises(ValueError, match="--max-cap"):
        build_chain_table(plan, caps, TRACEDIRS, max_cap=0.005)
