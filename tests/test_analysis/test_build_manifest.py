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
        branch,  448,   1,          448
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
        2030,         2030,     2030,         64
        2035,         2035,     2035,         64
        2040,         2040,     2040,         64
        2045,         2045,     2045,         64
        2050,         2050,     2050,         64
        2055,         2055,     2055,         64
        2060,         2060,     2060,         64
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_only_rows_solving_the_pipeline_period_carry_the_rush_charge(
    chains, csv_str_to_df
):
    result = (
        chains.assign(
            rush=chains["args"].str.contains("--pipeline-rush-charge 71400,24900"),
            branch_year=chains["branch_year"].replace("", 0),
        )
        .groupby(["stage", "rush"], as_index=False)
        .agg(
            rows=("row", "size"),
            first_year=("branch_year", "min"),
            last_year=("branch_year", "max"),
        )
    )

    expected = csv_str_to_df("""
        stage,   rush,   rows,  first_year,  last_year
        base,    True,   1,     0,           0
        branch,  False,  384,   2035,        2060
        branch,  True,   64,    2030,        2030
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_sampled_caps_are_the_cell_intensity_at_the_cell_load(caps, csv_str_to_df):
    sampled = [
        ("ext_step_change_sc", 2026),
        ("ext_step_change_sc", 2030),
        ("ext_step_change_b2040_d120_cap00169576", 2040),
        ("ext_step_change_b2060_d200_cap000006925", 2060),
    ]

    result = (
        caps.set_index(["run_id", "year"])
        .loc[sampled, ["intensity", "intensity_basis", "source_twh", "cap_t"]]
        .reset_index()
    )

    expected = csv_str_to_df("""
        run_id,                                  year,  intensity,  intensity_basis,  source_twh,  cap_t
        ext_step_change_sc,                      2026,  0.55646,    source,           190.1,       105783046
        ext_step_change_sc,                      2030,  0.19673,    source,           202.73,      39883073
        ext_step_change_b2040_d120_cap00169576,  2040,  0.0169576,  source,           338.724,     5743946
        ext_step_change_b2060_d200_cap000006925, 2060,  0.00006925, source,           723.6,       50109
    """)
    pd.testing.assert_frame_equal(result, expected, check_dtype=False)


def test_chains_tsv_leads_with_the_base_chain_the_branches_seed_from(
    plan, caps, chains, tmp_path
):
    write_manifest(caps, chains, tmp_path, plan)

    lines = (tmp_path / "chains.tsv").read_text(encoding="utf-8").splitlines()

    traces = "/io/inputs/tracedirs/iasr_step_change.txt"
    assert len(lines) == 449
    assert lines[0] == (
        f"ext_step_change_sc\t{traces}\t--periods 2026 2030 2035 2040 2045 2050 2055 2060 "
        "--co2-cap-t-schedule 2026:105783046 2030:39883073 2035:15891510 2040:11674687 "
        "2045:8345279 2050:4460254 2055:4735315 2060:5010930 --next-period-only "
        "--pipeline-period 2030 --new-entrant-cap-mw 2026:0 2030:20500 "
        "--new-entrant-storage-cap-mw 2026:0 2030:5100 "
        "--pipeline-rush-charge 71400,24900 --pipeline-rush-ceiling-mw 41000,10200"
    )
    assert lines[1] == (
        "ext_step_change_b2030_d060_cap039346\t"
        "/io/inputs/tracedirs/iasr_step_change_b2030_d060.txt\t"
        "--periods 2030 --co2-cap-t-schedule 2030:47859687 "
        "--seed-state-from ext_step_change_sc --pin-base-stock "
        "--pipeline-period 2030 --new-entrant-cap-mw 2030:20500 "
        "--new-entrant-storage-cap-mw 2030:5100 --pipeline-rush-charge 71400,24900 "
        "--pipeline-rush-ceiling-mw 41000,10200"
    )


def test_written_plan_carries_the_grid_demand_trajectories(
    plan, caps, chains, tmp_path
):
    write_manifest(caps, chains, tmp_path, plan)

    written = json.loads((tmp_path / "demand_plan.json").read_text(encoding="utf-8"))

    paths = written["increment_demand_paths_source_twh"]
    assert len(paths) == 56
    assert paths["iasr_step_change_b2035_d120"] == pytest.approx({"2035": 295.656})


def test_limit_factors_and_solve_flags_are_appended_to_every_chain_of_the_launch(
    plan, caps
):
    chains = build_chain_table(
        plan,
        caps,
        TRACEDIRS,
        rez_limit_factor=4.0,
        flow_path_limit_factor=4.0,
        solve_flags="--social-licence-premiums 0.15,0.60",
    )

    assert (
        chains["args"]
        .str.endswith(
            " --rez-limit-factor 4.0 --flow-path-limit-factor 4.0"
            " --social-licence-premiums 0.15,0.60"
        )
        .all()
    )


def test_max_cap_is_refused_by_an_increment_grid_plan(plan, caps):
    with pytest.raises(ValueError, match="--max-cap"):
        build_chain_table(plan, caps, TRACEDIRS, max_cap=0.005)
