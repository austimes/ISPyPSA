#!/usr/bin/env bash
# Cluster half of the campaign refresh: run the cost-deliverables pipeline over every solved
# milestone and record the Slurm queue state for the page's progress strip. Runs on the petrichor login node; the heavy
# network reads go to a compute node through srun because they need tens of cores and
# hundreds of GB, and compute nodes have no internet so uv must never try to sync.
#
# Invoked by `isp refresh` over ssh; can also be run by hand:
#   bash analysis/extension_campaign/refresh_remote.sh
set -euo pipefail

REPO="${ISPYPSA_REMOTE_REPO:-/scratch3/wes148/code/ispypsa}"
BRANCH="${ISPYPSA_BRANCH:-extension-campaign}"
ACCOUNT="${ISPYPSA_SLURM_ACCOUNT:-OD-241887}"
PARTITION="${ISPYPSA_SLURM_PARTITION:-defq}"
WORKERS="${ISPYPSA_WORKERS:-16}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/scratch3/wes148/uv_cache2}"

cd "$REPO"
git pull -q --ff-only origin "$BRANCH"
echo "refresh_remote: $(git log -1 --format='%h %s')"
# The login node has internet; sync here so the isp entry point and any new dependency
# exist before the compute nodes run with --no-sync.
uv sync -q --extra solvers

run_on_node() {
    srun -p "$PARTITION" --account="$ACCOUNT" -c "$WORKERS" --mem=200G -t 2:00:00 \
        -J ispypsa-refresh --quiet "$@"
}

echo "refresh_remote: extracting costs per chain"
run_on_node bash -c "cut -f1 outputs/campaign/chains.tsv \
    | xargs -P $WORKERS -I{} uv run --no-sync isp deliverables --only {} --stage extract"

echo "refresh_remote: assembling deliverables and dashboard data"
uv run --no-sync isp deliverables --stage assemble
squeue -u "$USER" -h -o %T | sort | uniq -c > outputs/exports/slurm_state.txt
uv run --no-sync isp cost-dashboard-data
echo "refresh_remote: done"
