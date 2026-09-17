#!/bin/bash
# One array task = one campaign chain (a recursive-dynamic run_myopic sequence
# over 2030/2040/2050/2060). The array index is the 0-based line number in
# outputs/campaign/chains.tsv, which build_manifest.py writes.
#
#   sbatch --array=0-40 analysis/extension_campaign/chain.sbatch
#
# To submit a subset, read outputs/campaign/chains_index.csv and pass its `row`
# values: stage 2a (price chains) is rows 0-10, stage 2b (cap chains) is the
# rest, shallow to deep. For example the six cap0001 chains:
#
#   awk -F, '$5=="2b" && $4=="cap0001" {print $1}' outputs/campaign/chains_index.csv
#   sbatch --array=31-35 analysis/extension_campaign/chain.sbatch
#
# Each chain needs outputs/campaign/tracedirs/<trajectory>.txt holding that
# trajectory's YEAR:DIR trace-directory tokens, one line, space separated.
#SBATCH --job-name=ispypsa-ext
#SBATCH --partition=defq
#SBATCH --account=OD-241887
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=64
#SBATCH --mem=240G
#SBATCH --time=3-00:00:00
#SBATCH --output=/scratch3/wes148/code/ispypsa/outputs/campaign/slurm/%x-%A_%a.out
set -euo pipefail
export GRB_LICENSE_FILE=$HOME/gurobi_sc2.lic
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
cd /scratch3/wes148/code/ispypsa
mkdir -p outputs/campaign/slurm
IFS=$'\t' read -r RUN_ID TRAJ ARGS < <(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" outputs/campaign/chains.tsv)
# $ARGS is deliberately unquoted: it is either "--carbon-price N" or a
# "--co2-cap-t-schedule 2030:T 2040:T ..." token list that must word-split.
uv run python analysis/benchmarks/run_myopic.py --run-id "$RUN_ID" --output-root outputs \
  --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --iasr-final --dataset-year 2026 \
  --parsed-traces-directory-schedule $(cat outputs/campaign/tracedirs/$TRAJ.txt) \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none \
  --gas-supply-curve analysis/gas_market/gas_supply_curve_central.csv \
  --biomass-supply-curve analysis/bioenergy_market/biomass_supply_curve_central.csv \
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
  --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 --resume $ARGS
