#!/usr/bin/env bash
# Perturbation solves for the representation-contrast explainer.
#
# Four solves on a 2x2: demand (reference, +10 per cent) x carbon price ($0/t, $550/t).
# Everything else is held: NSW-only, 2040, 3 representative weeks at 30-minute
# resolution, IASR 7.8 Final, gas and biomass supply curves on, Gurobi barrier
# with crossover so the duals come from a basic optimal solution.
#
# Demand is perturbed by pointing --parsed-traces-directory at a scaled trace
# root built by make_scaled_traces.py. No repository file is modified.
set -euo pipefail

SP="${SCRATCH:?set SCRATCH to the scratchpad path}"
COMMON=(
  --filter NSW
  --periods 2040
  --iasr-final
  --dataset-year 2026
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8
  --gas-supply-curve analysis/gas_market/gas_supply_curve_central.csv
  --biomass-supply-curve analysis/bioenergy_market/biomass_supply_curve_central.csv
  --reference-years 2018
  --tns-price 0
  --budget-min 40
)

run_arm () {
  local arm="$1" traces="$2" cp="$3"
  echo "=============== ${arm} (demand root ${traces}, carbon \$${cp}/t) ==============="
  uv run python analysis/benchmarks/run_myopic.py \
    --run-id "repcon_${arm}" \
    --parsed-traces-directory "${SP}/${traces}" \
    --carbon-price "${cp}" \
    "${COMMON[@]}"
}

run_arm d100_c0   traces_d100   0
run_arm d110_c0   traces_d110   0
run_arm d100_c550 traces_d100 550
run_arm d110_c550 traces_d110 550

echo "ALL FOUR ARMS DONE"
