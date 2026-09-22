#!/bin/bash
# Reads the solved networks of a finished launch on a compute node. The script serves
# both stages of `msm extract`, chosen by the exported STAGE variable:
#
#   extract   one array task per chain, writing exports/per_chain/<chain>.csv
#   assemble  a single task joining those into the launch's exports/*.csv
#
# `msm extract` submits both through analysis.hpc.launch.submit, the assemble step
# depending on the array:
#
#   array_job = submit(extract.sbatch, "0-40", {"STAGE": "extract"}, layout, env)
#   submit(extract.sbatch, "0", {"STAGE": "assemble"}, layout, env, f"afterok:{array_job}")
#
# REPO, RUN_DIR and STAGE arrive through --export; the account, partition and stdout
# path arrive as sbatch flags.
#SBATCH --job-name=ispypsa-extract
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
set -euo pipefail
cd "$REPO"
if [ "${STAGE:-extract}" = assemble ]; then
  uv run --no-sync msm extract --run "$RUN_DIR" --stage assemble --local
  exit 0
fi
IFS=$'\t' read -r RUN_ID _ < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$RUN_DIR/campaign/chains.tsv")
uv run --no-sync msm extract --run "$RUN_DIR" --only "$RUN_ID" --stage extract --local
