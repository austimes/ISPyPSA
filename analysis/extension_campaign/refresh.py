"""Regenerate every campaign deliverable from the solved runs on petrichor, in one command.

    uv run isp refresh

Steps, each deterministic given the solved networks on the cluster:

1. On petrichor (over ssh): pull the branch, collect all solved milestones into
   ``dashboard_data.json`` and run the cost-deliverables pipeline (frontier extraction per
   chain, assembly into results/marginals/storage/manifest CSVs, cost-dashboard JSON).
   See ``refresh_remote.sh``.
2. Copy the JSON and CSV products down to ``outputs/exports/`` here.
3. Render both dashboards from their templates into ``outputs/exports/``.
4. Copy the dashboards and their data to the team share.

Host, paths and share are read from the environment (see ``_Settings``) so the script
carries no machine-specific constants; the defaults match the campaign's current homes.
"""

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from analysis.extension_campaign import build_cost_dashboard

CAMPAIGN = Path(__file__).parent
REPO_ROOT = CAMPAIGN.parents[1]
EXPORTS = REPO_ROOT / "outputs" / "exports"
REMOTE_PRODUCTS = [
    "outputs/exports/cost_dashboard_data.json",
    "outputs/exports/slurm_state.txt",
    "outputs/exports/results.csv",
    "outputs/exports/marginals.csv",
    "outputs/exports/storage.csv",
    "outputs/exports/manifest.csv",
    "outputs/exports/acceptance_per_cell.csv",
    "outputs/exports/acceptance_per_grid.csv",
]
DASHBOARDS = {
    "dashboard.html": (build_cost_dashboard.main, "cost_dashboard_data.json"),
}


@dataclass(frozen=True)
class _Settings:
    """Where the runs live and where the products go; every value is overridable by env."""

    host: str = os.environ.get("ISPYPSA_REMOTE_HOST", "petrichor")
    remote_repo: str = os.environ.get(
        "ISPYPSA_REMOTE_REPO", "/scratch3/wes148/code/ispypsa"
    )
    share_dir: Path = Path(
        os.environ.get("ISPYPSA_SHARE_DIR", "P:/work/AusTIMES2/data/ispypsa/outputs")
    )


def _run(command: list[str]) -> None:
    """Run a command, echoing it first, and stop the refresh on the first failure."""
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def _refresh_on_cluster(settings: _Settings) -> None:
    """Pull, collect and extract on petrichor by running the remote half of the workflow."""
    # Pull before invoking the script, since the script itself may be what just changed.
    branch = os.environ.get("ISPYPSA_BRANCH", "extension-campaign")
    _run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            settings.host,
            f"cd {settings.remote_repo} && git pull -q --ff-only origin {branch} "
            "&& bash analysis/extension_campaign/refresh_remote.sh",
        ]
    )


def _fetch_products(settings: _Settings) -> None:
    """Bring the JSON and CSV products down; a missing product fails loudly."""
    EXPORTS.mkdir(parents=True, exist_ok=True)
    for product in REMOTE_PRODUCTS:
        _run(
            [
                "scp",
                "-q",
                f"{settings.host}:{settings.remote_repo}/{product}",
                str(EXPORTS),
            ]
        )


def _render_dashboards() -> None:
    """Render each dashboard page from its template and freshly fetched data."""
    for page, (render_page, data) in DASHBOARDS.items():
        render_page(data=EXPORTS / data, out=EXPORTS / page)


def _copy_to_share(settings: _Settings) -> None:
    """Put the pages and their data where colleagues can open them without a server."""
    settings.share_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        *DASHBOARDS,
        *(data for _, data in DASHBOARDS.values()),
        "results.csv",
    ]:
        shutil.copy2(EXPORTS / name, settings.share_dir / name)
    print(f"share updated: {settings.share_dir}")


def main(skip_remote: bool = False, no_share: bool = False) -> None:
    """Regenerate every campaign deliverable from the solved runs on petrichor.

    :param skip_remote: Do not re-run the cluster stage; fetch and render what is already there.
    :param no_share: Leave the team share untouched.
    """
    settings = _Settings()
    if not skip_remote:
        _refresh_on_cluster(settings)
    _fetch_products(settings)
    _render_dashboards()
    if not no_share:
        _copy_to_share(settings)
    print(f"page: {settings.share_dir / 'dashboard.html'}")
