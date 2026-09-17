#!/bin/bash
# Full-chronology 2050 validation: one array task = one (trajectory, chain) row of
# outputs/campaign/fullyear.tsv, in the same headerless
# run_id<TAB>trajectory<TAB>args shape as chains.tsv.
#
#   sbatch --array=0-4 analysis/extension_campaign/fullyear.sbatch
#
# This is a GREENFIELD single-year solve, not a conditioned chain: there is no
# --recursive-dynamic, so 2050 is solved on the IASR baseline fleet rather than on
# the vintages a campaign chain would have carried into it. Its only purpose is to
# measure the representative-week sampling bias against the full 30-minute year;
# it is not a menu member and must not be compared like one.
#SBATCH --job-name=ispypsa-fullyear
#SBATCH --partition=ext
#SBATCH --account=OD-241887
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=64
#SBATCH --mem=240G
#SBATCH --time=2-00:00:00
#SBATCH --output=/scratch3/wes148/code/ispypsa/outputs/campaign/slurm/%x-%A_%a.out
set -euo pipefail
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd /scratch3/wes148/code/ispypsa
mkdir -p outputs/campaign/slurm
IFS=$'\t' read -r RUN_ID TRAJ ARGS < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" outputs/campaign/fullyear.tsv)
# $ARGS is deliberately unquoted so its pressure tokens word-split.
uv run python analysis/benchmarks/run_myopic.py --run-id "${RUN_ID}_fullyear" --output-root outputs \
  --periods 2050 --reducible-existing --existing-fom-keeping \
  --iasr-final --dataset-year 2026 \
  --parsed-traces-directory-schedule $(cat outputs/campaign/tracedirs/$TRAJ.txt) \
  --full-year --resolution-min 30 \
  --tns-price 89.93 --ccs-supply-curve none \
  --gas-supply-curve analysis/gas_market/gas_supply_curve_central.csv \
  --biomass-supply-curve analysis/bioenergy_market/biomass_supply_curve_central.csv \
  --use-pdlp --pdlp-tolerance 1e-3 --highs-threads $SLURM_CPUS_PER_TASK \
  --budget-min 1800 --resume $ARGS
