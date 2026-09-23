#!/bin/bash
# One array task = one campaign chain: a recursive-dynamic solve over the periods its own
# manifest row names. The array index is the 0-based line number in
# $RUN_DIR/campaign/chains.tsv, so `msm launch` writes the manifest and submits the
# array together.
#
#   msm launch --run-set sc5                     # base chain and increment grid
#   msm launch --run <dir> --stage branch        # one stage, rows read from chains_index.csv
#   msm launch --run <dir> --array 31-35         # a subset
#
# The partition, memory, time and cores are set below, at least 1.25x the use observed per
# solve; the account and stdout path arrive as sbatch flags. REPO, RUN_DIR and the solver
# environment (GRB_LICENSE_FILE, UV_CACHE_DIR) arrive through --export=ALL from the
# login-node environment that `msm launch` loaded from .env.
#SBATCH --job-name=ispypsa-ext
#SBATCH --partition=h24
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=32
#SBATCH --mem=40G
#SBATCH --time=12:00:00
set -euo pipefail
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd "$REPO"
IFS=$'\t' read -r RUN_ID TRACES ARGS < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$RUN_DIR/campaign/chains.tsv")
# RESUME is "--resume" only when msm launch submits into an existing launch directory:
# it keeps a chain's carried state and skips periods that already solved, so a run
# directory must never be reused once its inputs change; stamp a new launch instead.
# $ARGS and the trace-token file are deliberately unquoted: $ARGS carries the row's own
# "--periods ..." and cap schedule (a mixed-year branch array cannot share one export), and
# the token file holds one "YEAR:DIR" token per milestone. Both must word-split.
uv run --no-sync msm solve --run-id "$RUN_ID" --output-root "$RUN_DIR" \
  --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule $(cat "$TRACES") \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
  --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 ${RESUME:-} ${SOLVE_FLAGS:-} $ARGS
