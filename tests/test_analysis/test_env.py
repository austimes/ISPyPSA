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


def test_input_stores_hang_off_the_newest_input_package(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("MSM_INPUTS", raising=False)
    (tmp_path / "inputs" / "2026-09-17T13.54_isp2026_final").mkdir(parents=True)
    newest = tmp_path / "inputs" / "2026-09-18T09.00_isp2026_revised"
    newest.mkdir()

    env = Env.from_env()

    assert env.inputs == newest
    assert env.workbook_cache == newest / "workbook_cache_final"
    assert env.traces == newest / "traces" / "isp_2026"
    assert env.tracedirs == newest / "tracedirs"
    assert env.outputs == tmp_path / "outputs"


def test_msm_inputs_names_the_input_package_by_directory_name(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.setenv("MSM_INPUTS", "2026-09-17T13.54_isp2026_final")
    (tmp_path / "inputs" / "2026-09-18T09.00_isp2026_revised").mkdir(parents=True)

    assert (
        Env.from_env().inputs == tmp_path / "inputs" / "2026-09-17T13.54_isp2026_final"
    )


def test_msm_inputs_accepts_an_absolute_path(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.setenv("MSM_INPUTS", str(tmp_path / "elsewhere" / "scratch_inputs"))

    assert Env.from_env().inputs == tmp_path / "elsewhere" / "scratch_inputs"


def test_missing_input_package_is_refused(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.delenv("MSM_INPUTS", raising=False)

    with pytest.raises(FileNotFoundError, match="no stamped input package under"):
        Env.from_env().inputs


def test_slurm_settings_are_none_when_the_environment_names_none(monkeypatch, tmp_path):
    monkeypatch.setattr(env_module, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("IO_DIR", str(tmp_path))
    monkeypatch.delenv("MSM_SLURM_ACCOUNT", raising=False)
    monkeypatch.delenv("MSM_SLURM_PARTITION", raising=False)

    env = Env.from_env()

    assert (env.slurm_account, env.slurm_partition) == (None, None)


def test_new_run_creates_a_stamped_launch_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("IO_DIR", str(tmp_path))

    layout = Env.from_env().new_run("ext41")

    assert layout.root.is_dir()
    assert layout.root.parent == tmp_path / "outputs"
    stamp, _, run_set = layout.root.name.partition("_")
    assert run_set == "ext41"
    assert datetime.strptime(stamp, RUN_STAMP_FORMAT)


def test_output_layout_paths_hang_off_one_root(tmp_path):
    layout = OutputLayout(tmp_path / "outputs" / "2026-09-17T14.05_ext41")

    assert layout.config("chain_2030") == layout.root / "configs" / "chain_2030.yaml"
    assert layout.log("chain_2030") == layout.root / "logs" / "chain_2030.log"
    assert layout.record("chain") == layout.root / "records" / "chain.json"
    assert layout.network("chain_2030") == (
        layout.root
        / "runs"
        / "chain_2030__cost_optimal"
        / "outputs"
        / "capacity_expansion.nc"
    )
    assert layout.chain_dir("chain") == layout.root / "runs" / "chain"
    assert layout.campaign == layout.root / "campaign"
    assert layout.exports == layout.root / "exports"
