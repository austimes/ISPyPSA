#!/bin/bash
# Smoke-test chain: one NSW-only, 2-period, capped recursive-dynamic chain on PDLP.
# It exercises cap binding, tranche carry under a cap and the per-period trace
# directories before any production chain is released.
#
#   msm launch --run-set ext41 --smoke
#
# The account, partition and stdout path arrive as sbatch flags; REPO, RUN_DIR and the
# solver environment arrive through --export=ALL from the login-node environment.
#SBATCH --job-name=ispypsa-smoke
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
set -euo pipefail
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd "$REPO"
# Trace directories come from the central trajectory's token file, named by that
# chain's row in the launch manifest, so the gate reads the same stores as production.
# The file covers every milestone; this chain solves the first two.
TOKEN_FILE=$(awk -F'\t' '$1=="ext_central_c0" {print $2}' "$RUN_DIR/campaign/chains.tsv")
TRACES=$(cut -d' ' -f1,2 "$TOKEN_FILE")
# Placeholder NSW tonnages: round numbers chosen to bind without being deep, not a rung
# of the campaign ladder (which is national and written into caps.csv).
# $TRACES is deliberately unquoted: it is two "YEAR:DIR" tokens that must word-split.
uv run --no-sync msm solve --run-id smoke_nsw_capped --output-root "$RUN_DIR" \
  --filter NSW --periods 2030 2040 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule $TRACES \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-pdlp --pdlp-tolerance 3e-3 --highs-threads $SLURM_CPUS_PER_TASK \
  --budget-min 90 --resume \
  --co2-cap-t-schedule 2030:6000000 2040:2000000
