#!/bin/bash
# One array task = one campaign chain: a recursive-dynamic solve over the periods its own
# manifest row names. The array index is the 0-based line number in
# $RUN_DIR/campaign/chains.tsv, so `msm launch` writes the manifest and submits the
# array together. The base row carries --next-period-only, so `msm launch` submits it once
# per milestone period, each job chained behind the one before.
#
#   msm launch --run-set sc5                     # base chain and increment grid
#   msm launch --run <dir> --resume              # only the periods and cells not yet solved
#   msm launch --run <dir> --array 31-35         # a subset
#
# The partition, memory, time and cores are set below, at least 1.25x the use observed per
# solve (a barrier-only 2060 solve peaks at about 71 GB); the account and stdout path arrive
# as sbatch flags. REPO, RUN_DIR and the solver environment (GRB_LICENSE_FILE, UV_CACHE_DIR)
# arrive through --export=ALL from the login-node environment that `msm launch` loaded from .env.
#SBATCH --job-name=ispypsa-ext
#SBATCH --partition=h24
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=32
#SBATCH --mem=96G
#SBATCH --time=12:00:00
set -euo pipefail
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd "$REPO"
IFS=$'\t' read -r RUN_ID TRACES ARGS < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" "$RUN_DIR/campaign/chains.tsv")
# --resume keeps a chain's carried state and skips periods that already solved, which the
# per-period base jobs rely on and which is a no-op in a freshly stamped launch directory; a
# run directory must never be reused once its inputs change, so stamp a new launch instead.
# Crossover is off unless GUROBI_CROSSOVER is set (e.g. -1 to re-solve sub-optimal barrier cells):
# the barrier solution at BarConvTol 1e-8 is the answer.
# $ARGS and the trace-token file are deliberately unquoted: $ARGS carries the row's own
# "--periods ..." and cap schedule (a mixed-year branch array cannot share one export), and
# the token file holds one "YEAR:DIR" token per milestone. Both must word-split.
uv run --no-sync msm solve --run-id "$RUN_ID" --output-root "$RUN_DIR" \
  --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule $(cat "$TRACES") \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-gurobi --gurobi-method 2 --gurobi-crossover ${GUROBI_CROSSOVER:-0} --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
  --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 --resume $ARGS
