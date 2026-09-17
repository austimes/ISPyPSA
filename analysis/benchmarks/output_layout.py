"""Where a solve campaign writes its products.

Every run product (generated per-period configs, solver logs, JSON records, solved
networks and chain state) lives under one root so a campaign can be staged on a
scratch filesystem and kept out of version control with a single ignore rule.
The default root is ``outputs/`` at the repository root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path("outputs")


@dataclass(frozen=True)
class OutputLayout:
    """Paths for one campaign's run products under a single root directory.

    :param root: Directory holding every run product. Relative paths resolve against
        the current working directory, which the drivers assume is the repo root.
    """

    root: Path = DEFAULT_OUTPUT_ROOT

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

    def config(self, run_id: str) -> Path:
        """Generated config for one solve."""
        return self.configs / f"{run_id}.yaml"

    def log(self, run_id: str) -> Path:
        """Solver log for one solve."""
        return self.logs / f"{run_id}.log"

    def record(self, run_id: str) -> Path:
        """JSON record for one solve or one chain."""
        return self.records / f"{run_id}.json"

    def run_dir(self, run_id: str, archetype: str) -> Path:
        """ISPyPSA run directory for one solve, named the way ISPyPSA names it."""
        return self.runs / f"{run_id}__{archetype}"

    def network(self, run_id: str, archetype: str) -> Path:
        """Solved capacity-expansion network for one solve."""
        return self.run_dir(run_id, archetype) / "outputs" / "capacity_expansion.nc"

    def chain_dir(self, chain_id: str) -> Path:
        """Per-chain state directory holding ``tranches/`` and ``retention/``."""
        return self.runs / chain_id
