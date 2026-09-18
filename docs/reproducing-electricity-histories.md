# Reproducing electricity investment histories

The sequential runner carries surviving generation and storage investments into later milestones, applies annual demand and emissions settings, and retains the fuel supply costs used in the electricity campaigns. Run it from a source checkout so the modelling pre-passes under `analysis/archetypes` are included. Calling the package builder alone does not apply that full workflow.

## Model assumptions carried into this workflow

| Behaviour | Source changes |
| --- | --- |
| Restore IASR pumped-hydro candidates, lead times and capacity limits | `7d4acbe`, `fde05c5` |
| Add authored 168-hour and 336-hour pumped hydro with a shared sub-regional site limit | `6033279` |
| Use the AEMO 2026 Step Change conventional-hydro energy trajectory | `fdb5f5c`; [source extract](../analysis/calibration/aemo_2026_isp_sc_hydro_generation.csv) |
| Preserve large numeric input values, offshore-wind availability and existing wind/solar/hydro maintenance costs | `7f12fd4`, `36ab6c6`, `78267c3` |
| Support annual emissions caps, demand-directory schedules and representative-week selection | `0d5f117`, `a9754d4`, `f740c88` |
| Charge retained-fleet maintenance once and avoid carrying assets already present in the later existing-fleet roster | `6a8e06c` |
| Hold costs beyond the published horizon, fill missing thermal heat rates/variable maintenance, and permit fossil-only gas prices | `454f446` |

The long-duration pumped-hydro options are authored extensions, not additional AEMO observations. Their capital costs extrapolate the published 10/24/48-hour costs by year; other properties inherit the 48-hour class. Every duration competes within the shared site-power limit. These assumptions must accompany any result using this workflow. A model reaching an optimum does not by itself establish that all demand was served: inspect unserved energy and numerical residuals separately, especially under tight emissions caps.

Biomass and gas supply curves are enabled by default in `analysis/benchmarks/run_myopic.py`. Their increasing fuel-price premiums and quantity limits remain active in the solved model. A configured biomass curve replaces the older flat feedstock re-pricing pre-pass, so it is not charged twice. `--biomass-supply-curve none` explicitly disables the curve and changes the assumptions; it is not the reproduction setting.

Both the preceding demand/carbon sweep and intensity map disabled the optional CCS supply curve. They used a flat **A$89.93 per captured tonne** transport-and-storage charge. The CCS supply-curve feature remains available, but reproducing those campaigns requires explicitly passing `--ccs-supply-curve none --tns-price 89.93`. The default conservative CCS curve is a different assumption. The flat charge does not establish physical disposal capacity.

## Inputs and versions

Use `uv sync --frozen`. Preserve the source commit, lockfile, authored assumptions, demand plan, annual cap tonnages, original workbook/trace hashes and solver settings with the run. A later branch head is not evidence of the version used by an earlier solve.

Each new solve record includes the source Git commit, whether the worktree had uncommitted changes, and the SHA-256 of its generated YAML. Existing records are not backfilled. Unavailable provenance is marked explicitly. This does not hash the large input package; preserve that package separately.

The final-2026 workflow expects the workbook at `iasr inputs/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm`, its parsed cache under `analysis/data/workbook_cache_final`, and the matching parsed trace store, commonly `data/trace_data_final/isp_2026`. These large inputs and solver licences are supplied separately. Use the tracked v7.8 parser metadata when building the cache; an older cache can omit the restored pumped-hydro rows.

The campaign matrix, workload manifest and Slurm submissions live under [analysis/extension_campaign](../analysis/extension_campaign/). Use the reviewed demand plan and prepare its manifest before launching the array. For exact historical reproduction, use its recorded source snapshot and input package rather than treating newer model fixes as unchanged history.

## Prepare the run inputs

The demand builder reads a JSON object containing `version`, `milestone_years`, `demand_paths_source_twh` and `anchor_2025_customer_delivered_twh`. Trajectory values are annual source-NEM TWh keyed by year. The 2025 anchor is a separate customer-delivered quantity; it is not silently used as source load. Use the reviewed campaign demand-plan file, not an inferred replacement for it.

```text
uv run python analysis/extension_campaign/build_trajectory_demand_dirs.py --source data/trace_data_final/isp_2026 --out-root outputs/inputs/traces --plan analysis/extension_campaign/next-sweep-demand-plan.json
uv run python analysis/extension_campaign/hold_supply_curves.py --curve analysis/gas_market/gas_supply_curve_central.csv --out outputs/inputs/gas_held.csv --years 2060
uv run python analysis/extension_campaign/hold_supply_curves.py --curve analysis/bioenergy_market/biomass_supply_curve_central.csv --out outputs/inputs/biomass_held.csv --years 2060
```

The demand builder scales the supplied demand series, leaves weather generation traces unscaled, and explicitly copies FY2050 to FY2060 for the authored horizon extension. It writes per-trajectory `YEAR:DIR` tokens under `outputs/inputs/traces/tracedirs/`. On Windows without directory-symlink privileges, add `--vre-mode copy`; it uses more disk but preserves the same weather-data bytes. Input and output stores must be separate.

The fuel commands repeat the final published year's tranche limits and premiums through 2060. Always supply those held files when modelling beyond the original curves' coverage. Missing fuel years are an error, not unlimited fuel.

## Run a history

This is the command shape, not a populated production case. Replace each `TRACE_*` path with the generated path from the trajectory's token file and each `CAP_*` value with its approved absolute annual tonnes:

```text
uv run python analysis/benchmarks/run_myopic.py --run-id reviewed_history --output-root outputs --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing --existing-fom-keeping --dataset-year 2026 --iasr-final --parsed-traces-directory-schedule 2030:TRACE_2030 2040:TRACE_2040 2050:TRACE_2050 2060:TRACE_2060 --co2-cap-t-schedule 2030:CAP_2030 2040:CAP_2040 2050:CAP_2050 2060:CAP_2060 --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks --gas-unblended --gas-supply-curve outputs/inputs/gas_held.csv --biomass-supply-curve outputs/inputs/biomass_held.csv --ccs-supply-curve none --tns-price 89.93 --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 --budget-min 600
```

For the uncapped baseline, omit the cap schedule and use `--carbon-price 0`. Specify the campaign's thread allocation and any deliberate fallback solver explicitly. Do not reuse a run identifier or resume a chain after changing its inputs or assumptions.

Outputs remain under `outputs/`: generated YAML, records, logs, solved networks and carried state. Verify the generated YAML contains `biomass_supply_curve.curve_csv` and `gas_supply_curve.curve_csv`, the intended gas-pricing switch, and the flat transport/storage charge. Check each milestone's solver status/gap, annual cap, actual emissions, unserved energy, fuel purchases versus burn, and carried capacities before accepting the history.
