import hashlib
import subprocess

from analysis.hpc import instrumented_runner


def _completed(command: list[str], stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")


def test_git_provenance_records_clean_commit(monkeypatch, tmp_path):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:] == ["rev-parse", "HEAD"]:
            return _completed(command, "abc123\n")
        return _completed(command)

    monkeypatch.setattr(instrumented_runner.subprocess, "run", fake_run)

    provenance = instrumented_runner._git_provenance(tmp_path)

    assert provenance == {
        "source_git_status": "available",
        "source_git_commit": "abc123",
        "source_git_dirty": False,
    }
    assert all(call[1]["cwd"] == tmp_path for call in calls)


def test_git_provenance_records_dirty_worktree(monkeypatch, tmp_path):
    def fake_run(command, **kwargs):
        if command[1:] == ["rev-parse", "HEAD"]:
            return _completed(command, "def456\n")
        return _completed(command, " M analysis/hpc/instrumented_runner.py\n")

    monkeypatch.setattr(instrumented_runner.subprocess, "run", fake_run)

    provenance = instrumented_runner._git_provenance(tmp_path)

    assert provenance["source_git_commit"] == "def456"
    assert provenance["source_git_dirty"] is True
    assert provenance["source_git_status"] == "available"


def test_git_provenance_marks_git_failure_unavailable(monkeypatch, tmp_path):
    def unavailable(command, **kwargs):
        raise subprocess.CalledProcessError(
            128, command, stderr="fatal: not a git repository"
        )

    monkeypatch.setattr(instrumented_runner.subprocess, "run", unavailable)

    provenance = instrumented_runner._git_provenance(tmp_path)

    assert provenance["source_git_status"] == "unavailable"
    assert provenance["source_git_commit"] is None
    assert provenance["source_git_dirty"] is None
    assert "not a git repository" in provenance["source_git_error"]


def test_config_provenance_hashes_exact_yaml_bytes(tmp_path):
    config = tmp_path / "run.yaml"
    content = b"solver: highs\ntemporal:\n  year_type: fy\n"
    config.write_bytes(content)

    provenance = instrumented_runner._config_provenance(config)

    assert provenance == {
        "input_config_sha256_status": "available",
        "input_config_sha256": hashlib.sha256(content).hexdigest(),
    }


def test_config_provenance_marks_missing_yaml_unavailable(tmp_path):
    provenance = instrumented_runner._config_provenance(tmp_path / "missing.yaml")

    assert provenance["input_config_sha256_status"] == "unavailable"
    assert provenance["input_config_sha256"] is None
    assert "FileNotFoundError" in provenance["input_config_sha256_error"]
