"""Where inputs live and where a campaign writes its products.

Every machine-specific location comes from one environment variable, ``IO_DIR``, read from
the repository's ``.env`` (see ``.example.env``). The same directory is mounted on the
workstation (SMB share) and on the cluster (NFS), so nothing is copied between hosts::

    $IO_DIR/inputs/<stamp>_<label>/      one versioned input package: workbook, cache, traces
    $IO_DIR/outputs/<stamp>_<run_set>/   one directory per launch, holding every product of that launch

Both levels are stamped ``<YYYY-MM-DDTHH.MM>_<name>`` and sit flat under their parent, so the
newest of either sorts last. A run reads the newest input package unless ``MSM_INPUTS`` names
one.

Small authored inputs that are versioned with the code (fuel curves, CCS tranches) resolve
against this package's own directory, so a clone works from any working directory and the
package can move to another repository unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parent
MODEL_DATA = PACKAGE_ROOT / "model" / "data"
RUN_STAMP_FORMAT = "%Y-%m-%dT%H.%M"
RUN_DIR_SUFFIX = "cost_optimal"


@dataclass(frozen=True)
class OutputLayout:
    """Paths for one launch's run products under a single stamped root directory.

    :param root: The launch directory, ``$IO_DIR/outputs/<stamp>_<run_set>``.
    """

    root: Path

    @property
    def campaign(self) -> Path:
        """Chain manifest, cap tonnages, demand plan copy and Slurm stdout."""
        return self.root / "campaign"

    @property
    def configs(self) -> Path:
        """Generated per-period ISPyPSA YAML configs."""
        return self.root / "configs"

    @property
    def logs(self) -> Path:
        """Solver stdout transcripts, one per solve."""
        return self.root / "logs"

    @property
    def records(self) -> Path:
        """JSON records, one per solve plus one per chain."""
        return self.root / "records"

    @property
    def runs(self) -> Path:
        """ISPyPSA run directories (templated inputs, solved networks) and chain state."""
        return self.root / "runs"

    @property
    def exports(self) -> Path:
        """Deliverable CSVs assembled from the solved networks."""
        return self.root / "exports"

    def config(self, run_id: str) -> Path:
        """Generated config for one solve."""
        return self.configs / f"{run_id}.yaml"

    def log(self, run_id: str) -> Path:
        """Solver log for one solve."""
        return self.logs / f"{run_id}.log"

    def record(self, run_id: str) -> Path:
        """JSON record for one solve or one chain."""
        return self.records / f"{run_id}.json"

    def run_dir(self, run_id: str) -> Path:
        """ISPyPSA run directory for one solve, named the way ISPyPSA names it."""
        return self.runs / f"{run_id}__{RUN_DIR_SUFFIX}"

    def network(self, run_id: str) -> Path:
        """Solved capacity-expansion network for one solve."""
        return self.run_dir(run_id) / "outputs" / "capacity_expansion.nc"

    def chain_dir(self, chain_id: str) -> Path:
        """Per-chain state directory holding ``tranches/`` and ``retention/``."""
        return self.runs / chain_id


@dataclass(frozen=True)
class Env:
    """The machine-specific settings, read once from ``.env`` and the process environment.

    :param io_dir: Root of every input and run product.
    :param slurm_account: Slurm account for cluster submissions, or None to leave the
        submission's account to the cluster's own default.
    :param slurm_partition: Slurm partition for cluster submissions, or None to leave
        the submission's partition to the cluster's own default.
    :param inputs_name: Input package to read, as a directory name under
        ``$IO_DIR/inputs`` or an absolute path, or None to read the newest package.
    """

    io_dir: Path
    slurm_account: str | None
    slurm_partition: str | None
    inputs_name: str | None = None

    @classmethod
    def from_env(cls) -> Env:
        """Load ``.env`` from the repository root and validate ``IO_DIR``."""
        load_dotenv(REPO_ROOT / ".env")
        io_dir = os.environ.get("IO_DIR")
        if not io_dir:
            raise ValueError(
                "IO_DIR is not set; copy .example.env to .env and point IO_DIR at the data share"
            )
        root = Path(io_dir)
        if not root.is_dir():
            raise NotADirectoryError(f"IO_DIR={root} does not exist or is not mounted")
        return cls(
            io_dir=root,
            slurm_account=os.environ.get("MSM_SLURM_ACCOUNT"),
            slurm_partition=os.environ.get("MSM_SLURM_PARTITION"),
            inputs_name=os.environ.get("MSM_INPUTS"),
        )

    @property
    def inputs(self) -> Path:
        """The versioned input package this run reads, the newest unless ``MSM_INPUTS`` names one.

        An absolute ``MSM_INPUTS`` is taken as the package itself, so an input package can sit
        outside ``$IO_DIR``.
        """
        if self.inputs_name:
            return self.io_dir / "inputs" / self.inputs_name
        packages = sorted(p for p in (self.io_dir / "inputs").glob("*_*") if p.is_dir())
        if not packages:
            raise FileNotFoundError(
                f"no stamped input package under {self.io_dir / 'inputs'}; "
                "expected one named <YYYY-MM-DDTHH.MM>_<label>"
            )
        return packages[-1]

    @property
    def iasr_workbook(self) -> Path:
        """AEMO 2026 ISP final inputs and assumptions workbook."""
        return (
            self.inputs
            / "iasr"
            / "2026 ISP Final"
            / "2026-isp-inputs-and-assumptions-workbook.xlsm"
        )

    @property
    def workbook_cache(self) -> Path:
        """Parsed v7.8 workbook tables."""
        return self.inputs / "workbook_cache_final"

    @property
    def traces(self) -> Path:
        """Parsed ISP 2026 demand and weather trace store."""
        return self.inputs / "traces" / "isp_2026"

    @property
    def tracedirs(self) -> Path:
        """Per-trajectory, per-milestone demand trace directories built from ``traces``."""
        return self.inputs / "tracedirs"

    @property
    def outputs(self) -> Path:
        """Root of every launch directory."""
        return self.io_dir / "outputs"

    def new_run(self, run_set: str) -> OutputLayout:
        """Create and return a freshly stamped launch directory for ``run_set``."""
        stamp = datetime.now().strftime(RUN_STAMP_FORMAT)
        layout = OutputLayout(self.outputs / f"{stamp}_{run_set}")
        layout.root.mkdir(parents=True)
        return layout
