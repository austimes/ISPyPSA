from datetime import datetime

import pytest

from analysis import env as env_module
from analysis.env import RUN_STAMP_FORMAT, Env, OutputLayout


def test_run_stamp_is_sortable_to_the_minute():
    assert datetime(2026, 9, 18, 14, 5).strftime(RUN_STAMP_FORMAT) == "2026-09-18T14.05"


def test_from_env_requires_io_dir_to_be_set(monkeypatch):
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("IO_DIR", raising=False)

    with pytest.raises(ValueError, match="IO_DIR is not set"):
        Env.from_env()


def test_from_env_requires_io_dir_to_exist(monkeypatch, tmp_path):
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("IO_DIR", str(tmp_path / "not_mounted"))

    with pytest.raises(NotADirectoryError, match="not_mounted"):
        Env.from_env()


def test_input_stores_hang_off_io_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))

    env = Env.from_env()

    assert env.workbook_cache == tmp_path / "inputs" / "workbook_cache_final"
    assert env.traces == tmp_path / "inputs" / "traces" / "isp_2026"
    assert env.tracedirs == tmp_path / "inputs" / "tracedirs"
    assert env.run_set("ext41") == tmp_path / "runs" / "ext41"


def test_new_run_creates_a_stamped_launch_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))

    layout = Env.from_env().new_run("ext41")

    assert layout.root.is_dir()
    assert layout.root.parent == tmp_path / "runs" / "ext41"
    assert datetime.strptime(layout.root.name, RUN_STAMP_FORMAT)


def test_latest_run_picks_the_newest_stamp(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    run_set = tmp_path / "runs" / "ext41"
    for stamp in ["2026-09-16T09.00", "2026-09-17T08.30", "2026-09-17T14.05"]:
        (run_set / stamp).mkdir(parents=True)

    layout = Env.from_env().latest_run("ext41")

    assert layout.root == run_set / "2026-09-17T14.05"


def test_latest_run_raises_when_a_run_set_has_no_launches(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    (tmp_path / "runs" / "ext41").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="No launches under"):
        Env.from_env().latest_run("ext41")


def test_output_layout_paths_hang_off_one_root(tmp_path):
    layout = OutputLayout(tmp_path / "ext41" / "2026-09-17T14.05")

    assert layout.config("chain_2030") == layout.root / "configs" / "chain_2030.yaml"
    assert layout.log("chain_2030") == layout.root / "logs" / "chain_2030.log"
    assert layout.record("chain") == layout.root / "records" / "chain.json"
    assert layout.network("chain_2030", "cost_optimal") == (
        layout.root
        / "runs"
        / "chain_2030__cost_optimal"
        / "outputs"
        / "capacity_expansion.nc"
    )
    assert layout.chain_dir("chain") == layout.root / "runs" / "chain"
    assert layout.campaign == layout.root / "campaign"
    assert layout.exports == layout.root / "exports"
