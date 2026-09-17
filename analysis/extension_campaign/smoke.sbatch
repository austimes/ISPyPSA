#!/bin/bash
# Stage 0 smoke chain: one NSW-only, 2-period, capped recursive-dynamic chain on
# PDLP. It exercises cap binding, tranche carry under a cap and the per-period
# trace directories before any production chain is released.
#
#   export TRACES_2030=/scratch3/wes148/traces/central_2030
#   export TRACES_2040=/scratch3/wes148/traces/central_2040
#   sbatch analysis/extension_campaign/smoke.sbatch
#SBATCH --job-name=ispypsa-smoke
#SBATCH --partition=defq
#SBATCH --account=OD-241887
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=/scratch3/wes148/code/ispypsa/outputs/campaign/slurm/%x-%A.out
set -euo pipefail
: "${TRACES_2030:?export TRACES_2030 to the 2030 parsed-traces base directory}"
: "${TRACES_2040:?export TRACES_2040 to the 2040 parsed-traces base directory}"
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd /scratch3/wes148/code/ispypsa
mkdir -p outputs/campaign/slurm
# Placeholder NSW tonnages: round numbers chosen to bind without being deep, not
# a rung of the campaign ladder (which is national and written by build_manifest.py).
uv run python analysis/benchmarks/run_myopic.py --run-id smoke_nsw_capped --output-root outputs \
  --filter NSW --periods 2030 2040 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --iasr-final --dataset-year 2026 \
  --parsed-traces-directory-schedule 2030:$TRACES_2030 2040:$TRACES_2040 \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none \
  --gas-supply-curve analysis/gas_market/gas_supply_curve_central.csv \
  --biomass-supply-curve analysis/bioenergy_market/biomass_supply_curve_central.csv \
  --use-pdlp --pdlp-tolerance 3e-3 --highs-threads $SLURM_CPUS_PER_TASK \
  --budget-min 90 --resume \
  --co2-cap-t-schedule 2030:6000000 2040:2000000
