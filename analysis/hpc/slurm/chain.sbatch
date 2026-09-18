#!/bin/bash
# One array task = one campaign chain: a recursive-dynamic solve over the milestones
# 2030/2040/2050/2060. The array index is the 0-based line number in
# $RUN_DIR/campaign/chains.tsv, so `msm launch` writes the manifest and submits the
# array together.
#
#   msm launch --run-set ext41              # whole campaign
#   msm launch --run <dir> --array 31-35    # a subset, rows read from chains_index.csv
#
# The account, partition and stdout path arrive as sbatch flags; REPO, RUN_DIR and the
# solver environment (GRB_LICENSE_FILE, UV_CACHE_DIR) arrive through --export=ALL from
# the login-node environment that `msm launch` loaded from .env.
#SBATCH --job-name=ispypsa-ext
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=64
#SBATCH --mem=240G
#SBATCH --time=3-00:00:00
set -euo pipefail
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd "$REPO"
IFS=$'\t' read -r RUN_ID TRACES ARGS < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$RUN_DIR/campaign/chains.tsv")
# $ARGS and the trace-token file are deliberately unquoted: $ARGS is either
# "--carbon-price N" or a "--co2-cap-t-schedule 2030:T 2040:T ..." token list, and the
# token file holds one "YEAR:DIR" token per milestone. Both must word-split.
uv run --no-sync msm solve --run-id "$RUN_ID" --output-root "$RUN_DIR" \
  --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule $(cat "$TRACES") \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
  --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 --resume $ARGS
