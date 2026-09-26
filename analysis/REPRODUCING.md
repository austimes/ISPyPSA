# Reproducing an electricity investment history

The `msm solve` chain carries surviving generation and storage investment forward into later milestone years, applies
each period's demand and emissions settings, and prices fuel from the campaign's supply curves. Always run it through
the `msm` command line: that is the only path that applies the fork-specific model patches under `analysis/model/` (see
[MODELLING_ASSUMPTIONS.md](MODELLING_ASSUMPTIONS.md)). Calling ISPyPSA's own package builder directly skips those
patches.

A model reaching its cost optimum does not by itself prove every demand was served. Always check unserved energy and
solver residuals alongside the reported cost and mix; see "Verify a result" below. Every assumption authored for this
campaign, rather than sourced from the data AEMO publishes for its ISP - the national electricity capacity-expansion
roadmap - in the Inputs, Assumptions and Scenarios Report (IASR), is listed in
[MODELLING_ASSUMPTIONS.md](MODELLING_ASSUMPTIONS.md) - read it before accepting a result.

## Set up inputs

Copy `.example.env` to `.env` and set `IO_DIR` (see [README.md](README.md)), then run `uv sync --frozen` so the
lockfile, solver settings and fuel curves used for the run all match a known state. `msm solve` records the source Git
commit, whether the working tree had uncommitted changes, and the SHA-256 of each generated configuration file with
every solve; existing records are not backfilled, and a later branch head is not evidence of the version behind a solve
made before it.

`analysis.env.Env.from_env()` picks the newest timestamp-versioned input package under `$IO_DIR/inputs/`, or the one
`MSM_INPUTS` names, and resolves the input stores inside it:

- the National Electricity Market (NEM) IASR workbook at
  `<package>/iasr/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm`
- its parsed workbook cache at `<package>/workbook_cache_final/`
- the parsed demand and weather trace store at `<package>/traces/isp_2026/`

Each launch writes the package it read to `campaign/inputs.txt`, so a result always names its inputs.

Build the workbook cache with `isp-workbook-parser` 2.9.0 or later, whose v7.8 table configurations read every table to
its final-workbook extent: a cache built from the earlier draft-derived configuration truncates several tables, as
recorded in [research/workbook_parser_upgrade/](research/workbook_parser_upgrade/).

## Prepare demand trace directories

`msm launch` builds one rewritten demand trace directory per (trajectory, milestone year) under the input package's
`tracedirs/`, scaling the source trace so that year delivers the trajectory's target source NEM load; wind and solar
traces are shared unscaled across trajectories. A trajectory whose trace directories exist is left alone unless the
plan's authored knots for it have changed, in which case they are rebuilt, so the build is safe to repeat and picks up
an edited plan. The demand plan driving this (trajectories, milestone years, target loads) is
`analysis/hpc/demand_plan.json` by default; run `msm launch --help` for the option that points it at a different file.

## Solve a chain

`msm solve` runs one chain: a sequence of single-period solves, one per milestone year, each carrying forward the
previous year's new build and retained capacity. This is the shape the campaign's Slurm job runs:

```text
uv run msm solve --run-id ext_step_change_sc --output-root "$RUN_DIR" \
  --periods 2030 2035 2040 2045 2050 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule 2030:<dir> 2035:<dir> 2040:<dir> 2045:<dir> 2050:<dir> \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 \
  --co2-cap-t-schedule 2030:<tonnes> 2035:<tonnes> 2040:<tonnes> 2045:<tonnes> 2050:<tonnes> \
  --pipeline-period 2030 --new-entrant-cap-mw 2030:19000 --new-entrant-storage-cap-mw 2030:6000 \
  --social-licence-premiums 0.15,0.60 --build-rate-premiums analysis/model/data/build_rate_premiums_central.csv
```

Replace each `<dir>` with a milestone's trace directory (from the trajectory's token file under the input package's
`tracedirs/`) and each `<tonnes>` with its approved absolute annual cap; the uncapped baseline omits
`--co2-cap-t-schedule` and uses `--carbon-price 0` instead. The near-term pin caps new-entrant build at the two
allowances and stops economic early retirement in every period at or before `--pipeline-period`, and the two premium
flags price build above AEMO's published limits and above each carrier's baseline additions, writing what they charged
to each solve's `outputs/capacity_tranches.json`.

An increment-grid cell is the same command narrowed to one year and conditioned on the base chain:

```text
uv run msm solve --run-id ext_step_change_b2035_d110_cap006450 --output-root "$RUN_DIR" \
  --periods 2035 --co2-cap-t-schedule 2035:<tonnes> \
  --seed-state-from ext_step_change_sc --pin-base-stock
```

`--seed-state-from` copies the base chain's carried tranches and retention floors from before the cell's year into the
cell's own state directory, and `--pin-base-stock` holds the existing fleet at what the base chain retained, so the cell
differs from its base cell only by its own demand and cap. Do not reuse a run identifier, or resume a chain, after
changing its inputs or assumptions: `--resume` trusts that a completed period's inputs have not moved.

## Fuel supply curves

By default `msm solve` reads the campaign's central gas and biomass supply curves from
`analysis/model/data/gas_supply_curve_central_held_to_2060.csv` and
`analysis/model/data/biomass_supply_curve_central_held_to_2060.csv`. Each records increasing fuel-price premiums and
quantity limits by tranche, and must cover every period the chain solves. Passing `--gas-supply-curve none` or
`--biomass-supply-curve none` disables the corresponding curve and returns to unlimited fuel at the IASR's own price - a
different assumption, not the campaign's reproduction setting.

The CCS supply curve (`analysis/model/data/ccs_sink_tranches_conservative.csv` and
`analysis/model/data/ccs_transport_adders.csv`) is disabled in the campaign (`--ccs-supply-curve none`) in favour of the
flat **A$89.93 per captured tonne** transport-and-storage charge (`--tns-price 89.93`). The supply curve remains
available as a model feature; enabling it is a different assumption from the one this campaign was run under.

## Outputs

Every product of a chain - generated configs, solver logs, JSON records and solved networks - is written under the
stamped run directory given as `--output-root`, laid out by `analysis.env.OutputLayout`. Run `msm extract --run <dir>`
to turn the solved networks into the `exports/` CSVs, and `msm sharp --run <dir>` for the ShARP deliverable CSVs.
`exports/per_chain/duals_<cell>.csv` carries every custom-constraint dual of a chain, and `exports/increments.csv` joins
each grid cell to the base cell at its own year, giving the cost, emissions, gas, coal and new-build differences between
the two.

## Verify a result

Before accepting a history, check for each milestone: the solver's status and convergence gap, the carbon cap and the
actual emissions against it, unserved energy, fuel purchases against fuel burnt, and the capacities carried into the
next period. Confirm the generated configuration references the intended gas and biomass supply curves, the intended
gas-pricing switch, and the flat transport-and-storage charge.
