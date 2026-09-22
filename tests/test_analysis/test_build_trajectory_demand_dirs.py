"""Tests for the campaign's per-trajectory demand trace directory builder."""

import json
from itertools import product
from pathlib import Path

import pandas as pd
import pytest

from analysis.hpc.tracedirs import _reset_dataset_dir, build

DATASET_DIR = "isp_2026"
REFERENCE_YEAR = 2018
DEMAND_PARTITION = f"demand/scenario=Step%20Change/reference_year={REFERENCE_YEAR}"
SUBREGIONS = ("CNSW", "NNSW")
STORE_FINANCIAL_YEARS = (2048, 2049, 2050)
DEMAND_MW = 100.0
# Two August days, two sub-regions, 100 MW flat: 2 x 96 intervals x 100 MW x 0.5 h.
SOURCE_FY_MWH = 9600.0


@pytest.mark.parametrize(
    "relationship", ["same", "source_inside_output", "output_inside_source"]
)
def test_overlapping_stores_are_rejected_before_writing(tmp_path, relationship):
    source, output = tmp_path / "source", tmp_path / "out"
    if relationship == "same":
        output = source
    elif relationship == "source_inside_output":
        source = output / "source"
    else:
        output = source / "out"
    source.mkdir(parents=True)
    sentinel = source / "original.txt"
    sentinel.write_text("preserved", encoding="utf-8")
    with pytest.raises(ValueError, match="must not overlap"):
        build(source=source, out_root=output, plan=Path("unused.json"))
    assert sentinel.read_text(encoding="utf-8") == "preserved"


def test_reset_rejects_output_escape_before_deleting(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "original.txt"
    sentinel.write_text("preserved", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    with pytest.raises(ValueError, match="under the output root"):
        _reset_dataset_dir(output / ".." / "outside", DATASET_DIR, output)
    assert sentinel.read_text(encoding="utf-8") == "preserved"


def _half_hours(financial_year: int) -> pd.DatetimeIndex:
    """Two August days of half-hourly timestamps sitting inside one financial year."""
    return pd.date_range(f"{financial_year - 1}-08-01 00:30", periods=96, freq="30min")


def _demand_frame() -> pd.DataFrame:
    """Synthetic parsed demand trace with the real store's columns and a flat 100 MW value."""
    frames = [
        pd.DataFrame(
            {
                "datetime": _half_hours(financial_year),
                "value": DEMAND_MW,
                "subregion": subregion,
                "poe": "POE50",
                "demand_type": "OPSO_MODELLING",
            }
        )
        for financial_year, subregion in product(STORE_FINANCIAL_YEARS, SUBREGIONS)
    ]
    return pd.concat(frames, ignore_index=True)


def _vre_frame(id_column: str, id_value: str) -> pd.DataFrame:
    """Synthetic parsed VRE trace covering the same timestamps as the demand trace."""
    frames = [
        pd.DataFrame(
            {
                "datetime": _half_hours(financial_year),
                "value": 0.5,
                id_column: id_value,
                "resource_type": "WIND",
            }
        )
        for financial_year in STORE_FINANCIAL_YEARS
    ]
    return pd.concat(frames, ignore_index=True)


def _write_parquet(path: Path, frame: pd.DataFrame) -> None:
    """Write one parquet, creating its partition directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


@pytest.fixture
def source_store(tmp_path: Path) -> Path:
    """Read-only parsed trace store holding demand, project and zone partitions for FY2048 to FY2050."""
    store = tmp_path / "source" / DATASET_DIR
    _write_parquet(store / DEMAND_PARTITION / "data_0.parquet", _demand_frame())
    _write_parquet(
        store / f"project/reference_year={REFERENCE_YEAR}/data_0.parquet",
        _vre_frame("project", "Dulacca Wind Farm"),
    )
    _write_parquet(
        store / f"zone/reference_year={REFERENCE_YEAR}/data_0.parquet",
        _vre_frame("zone", "N3"),
    )
    return store


@pytest.fixture
def plan_file(tmp_path: Path) -> Path:
    """Demand plan whose milestones sit inside the synthetic store, with one unit-scalar and one scaled trajectory."""
    plan = {
        "version": "test-plan-v1",
        "milestone_years": [2049, 2050, 2060],
        "demand_paths_source_twh": {
            "unit_flat": {"2049": 0.0096, "2050": 0.0096, "2060": 0.0096},
            "unit_scaled": {"2049": 0.0192, "2050": 0.0048, "2060": 0.0192},
        },
        "increment_demand_paths_source_twh": {"unit_branch": {"2050": 0.0192}},
        "anchor_2025_customer_delivered_twh": 193.911,
    }
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


@pytest.fixture
def built(source_store: Path, plan_file: Path, tmp_path: Path) -> Path:
    """Output root after one full build; skipped where the platform refuses to create directory symlinks."""
    out_root = tmp_path / "out"
    try:
        build(
            source=source_store,
            out_root=out_root,
            plan=plan_file,
            reference_year=REFERENCE_YEAR,
        )
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip(f"directory symlinks unavailable on this platform: {error}")
        raise
    return out_root


def test_manifest_lands_realised_energy_on_every_target(built, csv_str_to_df):
    result = pd.read_csv(built / "manifest_demand_dirs.csv")

    expected = csv_str_to_df("""
        trajectory,   year,  scalar,  source_fy_mwh,  realised_fy_mwh,  plan_version,  authored_horizon_extension
        unit_flat,    2049,  1.0,     9600.0,         9600.0,           test-plan-v1,  False
        unit_flat,    2050,  1.0,     9600.0,         9600.0,           test-plan-v1,  False
        unit_flat,    2060,  1.0,     9600.0,         9600.0,           test-plan-v1,  True
        unit_scaled,  2049,  2.0,     9600.0,         19200.0,          test-plan-v1,  False
        unit_scaled,  2050,  0.5,     9600.0,         4800.0,           test-plan-v1,  False
        unit_scaled,  2060,  2.0,     9600.0,         19200.0,          test-plan-v1,  True
        unit_branch,  2050,  2.0,     9600.0,         19200.0,          test-plan-v1,  False
    """)
    pd.testing.assert_frame_equal(result, expected)


def test_a_single_knot_trajectory_builds_only_its_own_year(built):
    tokens = (built / "unit_branch.txt").read_text(encoding="utf-8").split()

    directory = (built / "unit_branch" / "2050").resolve()
    assert tokens == [f"2050:{directory.as_posix()}"]
    assert [path.name for path in sorted((built / "unit_branch").iterdir())] == ["2050"]


def test_unit_scalar_still_rewrites_the_demand_file(built, source_store):
    written = (
        built / "unit_flat" / "2049" / DATASET_DIR / DEMAND_PARTITION / "data_0.parquet"
    )

    result = pd.read_parquet(written)

    expected = pd.read_parquet(source_store / DEMAND_PARTITION / "data_0.parquet")
    pd.testing.assert_frame_equal(result, expected)


def test_extension_year_appends_fy2050_shifted_ten_years(built, source_store):
    written = (
        built
        / "unit_scaled"
        / "2060"
        / DATASET_DIR
        / DEMAND_PARTITION
        / "data_0.parquet"
    )

    result = pd.read_parquet(written)

    source = pd.read_parquet(source_store / DEMAND_PARTITION / "data_0.parquet")
    source_fy_2050 = source[source["datetime"] >= "2049-07-01"]
    expected = source_fy_2050.assign(
        datetime=source_fy_2050["datetime"] + pd.DateOffset(years=10),
        value=source_fy_2050["value"] * 2.0,
    ).reset_index(drop=True)
    appended = result[result["datetime"] >= "2059-07-01"].reset_index(drop=True)
    pd.testing.assert_frame_equal(appended, expected)
    assert appended["value"].sum() * 0.5 == pytest.approx(0.0192 * 1e6)


def test_extended_vre_store_gains_an_unscaled_fy2060(built, source_store):
    written = (
        built
        / "_vre_2060"
        / DATASET_DIR
        / f"project/reference_year={REFERENCE_YEAR}/data_0.parquet"
    )

    result = pd.read_parquet(written)

    source = pd.read_parquet(
        source_store / f"project/reference_year={REFERENCE_YEAR}/data_0.parquet"
    )
    source_fy_2050 = source[source["datetime"] >= "2049-07-01"]
    expected = source_fy_2050.assign(
        datetime=source_fy_2050["datetime"] + pd.DateOffset(years=10)
    ).reset_index(drop=True)
    appended = result[result["datetime"] >= "2059-07-01"].reset_index(drop=True)
    pd.testing.assert_frame_equal(appended, expected)


def test_vre_matches_one_shared_store(built, source_store):
    milestone_links = [
        built / "unit_flat" / "2049" / DATASET_DIR / subdir
        for subdir in ("project", "zone")
    ]
    extension_links = [
        built / "unit_flat" / "2060" / DATASET_DIR / subdir
        for subdir in ("project", "zone")
    ]

    assert all(link.is_symlink() for link in milestone_links + extension_links)
    assert [link.resolve() for link in milestone_links] == [
        (source_store / "project").resolve(),
        (source_store / "zone").resolve(),
    ]
    assert [link.resolve() for link in extension_links] == [
        (built / "_vre_2060" / DATASET_DIR / "project").resolve(),
        (built / "_vre_2060" / DATASET_DIR / "zone").resolve(),
    ]


def test_a_later_build_reuses_the_shared_extension_store(
    built, source_store, plan_file
):
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["demand_paths_source_twh"]["unit_added"] = {
        "2049": 0.0096,
        "2050": 0.0096,
        "2060": 0.0096,
    }
    plan_file.write_text(json.dumps(plan), encoding="utf-8")
    sentinel = built / "_vre_2060" / DATASET_DIR / "kept.txt"
    sentinel.write_text("kept", encoding="utf-8")

    build(
        source=source_store,
        out_root=built,
        plan=plan_file,
        reference_year=REFERENCE_YEAR,
    )

    assert sentinel.read_text(encoding="utf-8") == "kept"
    assert (built / "unit_added" / "2060" / DATASET_DIR / "project").resolve() == (
        built / "_vre_2060" / DATASET_DIR / "project"
    ).resolve()


def test_a_later_build_repairs_a_vre_link_left_behind_by_a_moved_store(
    built, source_store, plan_file
):
    milestone_link = built / "unit_flat" / "2049" / DATASET_DIR / "project"
    extension_link = built / "unit_flat" / "2060" / DATASET_DIR / "project"
    for link in (milestone_link, extension_link):
        link.unlink()
        link.symlink_to(built / "gone" / "project", target_is_directory=True)

    build(
        source=source_store,
        out_root=built,
        plan=plan_file,
        reference_year=REFERENCE_YEAR,
    )

    assert milestone_link.resolve() == (source_store / "project").resolve()
    assert (
        extension_link.resolve()
        == (built / "_vre_2060" / DATASET_DIR / "project").resolve()
    )
    assert (
        len(list(milestone_link.glob(f"reference_year={REFERENCE_YEAR}/*.parquet")))
        == 1
    )


def _rewrite_knot(plan_file: Path, trajectory: str, year: str, twh: float) -> None:
    """Change one authored knot of one trajectory in a demand plan on disk."""
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    plan["demand_paths_source_twh"][trajectory][year] = twh
    plan_file.write_text(json.dumps(plan), encoding="utf-8")


def test_a_changed_knot_rebuilds_only_its_own_trajectory(
    built, source_store, plan_file, caplog
):
    kept = built / "unit_flat" / "2049" / "sentinel.txt"
    kept.write_text("kept", encoding="utf-8")
    discarded = built / "unit_scaled" / "2049" / "sentinel.txt"
    discarded.write_text("discarded", encoding="utf-8")
    _rewrite_knot(plan_file, "unit_scaled", "2049", 0.0096)

    with caplog.at_level("WARNING"):
        build(
            source=source_store,
            out_root=built,
            plan=plan_file,
            reference_year=REFERENCE_YEAR,
        )

    assert (
        "Rebuilding trace directories whose demand plan knots no longer match the built ones: "
        "['unit_scaled']"
    ) in caplog.text
    assert kept.read_text(encoding="utf-8") == "kept"
    assert not discarded.exists()
    manifest = pd.read_csv(built / "manifest_demand_dirs.csv")
    assert manifest["trajectory"].tolist() == ["unit_scaled"] * 3
    assert manifest["scalar"].tolist() == [1.0, 0.5, 2.0]


def test_an_unchanged_plan_rebuilds_nothing(built, source_store, plan_file, caplog):
    sentinels = [
        built / trajectory / "2049" / "sentinel.txt"
        for trajectory in ("unit_flat", "unit_scaled")
    ]
    for sentinel in sentinels:
        sentinel.write_text("kept", encoding="utf-8")

    with caplog.at_level("WARNING"):
        build(
            source=source_store,
            out_root=built,
            plan=plan_file,
            reference_year=REFERENCE_YEAR,
        )

    assert "Rebuilding trace directories" not in caplog.text
    assert [sentinel.read_text(encoding="utf-8") for sentinel in sentinels] == [
        "kept",
        "kept",
    ]


def test_tracedirs_file_lists_one_token_per_milestone_in_year_order(built):
    tokens = (built / "unit_scaled.txt").read_text(encoding="utf-8").split()

    expected = [
        f"{year}:{(built / 'unit_scaled' / str(year)).resolve().as_posix()}"
        for year in (2049, 2050, 2060)
    ]
    assert tokens == expected


def test_annual_series_interpolates_linearly_between_authored_knots(
    built, csv_str_to_df
):
    series = pd.read_csv(built / "annual_demand_series.csv")

    result = series[series["trajectory"] == "unit_scaled"].reset_index(drop=True)

    expected = csv_str_to_df("""
        trajectory,   financial_year,  source_twh,  kind
        unit_scaled,  2025,            193.911,     anchor_customer_delivered
        unit_scaled,  2049,            0.0192,      authored
        unit_scaled,  2050,            0.0048,      authored
        unit_scaled,  2051,            0.00624,     interpolated
        unit_scaled,  2052,            0.00768,     interpolated
        unit_scaled,  2053,            0.00912,     interpolated
        unit_scaled,  2054,            0.01056,     interpolated
        unit_scaled,  2055,            0.012,       interpolated
        unit_scaled,  2056,            0.01344,     interpolated
        unit_scaled,  2057,            0.01488,     interpolated
        unit_scaled,  2058,            0.01632,     interpolated
        unit_scaled,  2059,            0.01776,     interpolated
        unit_scaled,  2060,            0.0192,      authored
    """)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-9)
