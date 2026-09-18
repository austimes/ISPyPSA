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

`analysis.env.Env.from_env()` resolves the shared input stores from `$IO_DIR`:

- the National Electricity Market (NEM) IASR workbook at
  `$IO_DIR/inputs/iasr/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm`
- its parsed workbook cache at `$IO_DIR/inputs/workbook_cache_final/`
- the parsed demand and weather trace store at `$IO_DIR/inputs/traces/isp_2026/`

Build the workbook cache from the tracked v7.8 parser metadata: an older cache can be missing the restored pumped hydro
energy storage (PHES) rows described in MODELLING_ASSUMPTIONS.md.

## Prepare demand trace directories

`msm launch` builds one rewritten demand trace directory per (trajectory, milestone year) under
`$IO_DIR/inputs/tracedirs/`, scaling the source trace so that year delivers the trajectory's target source NEM load;
wind and solar traces are shared unscaled across trajectories. A trajectory whose trace directories exist is left alone,
so the build is safe to repeat. The demand plan driving this (trajectories, milestone years, target loads) is
`analysis/hpc/demand_plan.json` by default; run `msm launch --help` for the option that points it at a different file.

## Solve a chain

`msm solve` runs one chain: a sequence of single-period solves, one per milestone year, each carrying forward the
previous year's new build and retained capacity. This is the shape the campaign's Slurm job runs:

```text
uv run msm solve --run-id ext_central_c0 --output-root "$RUN_DIR" \
  --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing --existing-fom-keeping \
  --parsed-traces-directory-schedule 2030:<dir> 2040:<dir> 2050:<dir> 2060:<dir> \
  --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
  --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
  --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 \
  --co2-cap-t-schedule 2030:<tonnes> 2040:<tonnes> 2050:<tonnes> 2060:<tonnes>
```

Replace each `<dir>` with a milestone's trace directory (from the trajectory's token file under
`$IO_DIR/inputs/tracedirs/`) and each `<tonnes>` with its approved absolute annual cap; the uncapped baseline omits
`--co2-cap-t-schedule` and uses `--carbon-price 0` instead. Do not reuse a run identifier, or resume a chain, after
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

## Verify a result

Before accepting a history, check for each milestone: the solver's status and convergence gap, the carbon cap and the
actual emissions against it, unserved energy, fuel purchases against fuel burnt, and the capacities carried into the
next period. Confirm the generated configuration references the intended gas and biomass supply curves, the intended
gas-pricing switch, and the flat transport-and-storage charge.
