# ShARP electricity supply campaign

This package builds, runs and reports the electricity-sector campaign that feeds ShARP, the whole-of-economy
optimisation model this campaign's results are handed to. It wraps [ISPyPSA](../README.md) (the Australian Energy
Market Operator's (AEMO) capacity-expansion model for its Integrated System Plan (ISP), under `src/ispypsa/`) with the
fork's own campaign machinery: a grid of chained yearly solves across demand trajectories and carbon-pressure settings,
a Slurm-driven cluster workflow, and the CSV deliverables ShARP consumes. Slurm is the cluster's job scheduler; every
step that needs it is described in the workflow table below.

Everything in this package is reached through one command line, `msm` (`uv run msm --help`), so no step is ever run by
typing a script path.

## Sub-packages

| Sub-package | Purpose | Category |
| --- | --- | --- |
| `src/ispypsa/` | The ISPyPSA capacity-expansion model itself | Upstream-contributable model fixes |
| `analysis/model/` | Fork-specific patches to the templated ISPyPSA input tables, plus the myopic chain's roll-forward machinery | Fork-specific model patches, not yet upstreamable |
| `analysis/hpc/` | Prepares a campaign launch, submits and resumes it on the cluster, and reads solved networks back into per-chain CSVs | Cluster runs |
| `analysis/sharp/` | Turns solved networks into the CSV deliverables ShARP consumes | ShARP deliverables and emitters |
| `analysis/dashboard/` | Builds one self-contained HTML dashboard from the exported CSVs | Dashboard |

`src/ispypsa/` changes are model corrections any ISPyPSA user would want (see
[MODELLING_ASSUMPTIONS.md](MODELLING_ASSUMPTIONS.md) for what each one fixes); everything under `analysis/` is specific
to this campaign and is not expected to move upstream.

## `IO_DIR` layout

Every input and run product lives under one directory, `$IO_DIR`, mounted at the same path on the workstation and on the
cluster. Both input packages and launches are timestamp-versioned directories, `<YYYY-MM-DDTHH.MM>_<name>`, sitting flat
under `inputs/` and `outputs/`:

```text
$IO_DIR/
  inputs/<YYYY-MM-DDTHH.MM>_<label>/
    iasr/2026 ISP Final/2026-isp-inputs-and-assumptions-workbook.xlsm
    workbook_cache_final/
    traces/isp_2026/
    tracedirs/<trajectory>/<year>/isp_2026/, <trajectory>.txt
  outputs/<YYYY-MM-DDTHH.MM>_<run_set>/
    campaign/   chains.tsv, chains_index.csv, caps.csv, demand_plan.json, inputs.txt,
                assumptions.json, slurm/*.out
    configs/    generated per-period ISPyPSA YAML configs
    logs/       solver stdout, one file per solve
    records/    JSON records, one per solve plus one per chain
    runs/       solved ISPyPSA run directories, each with outputs/capacity_expansion.nc,
                outputs/constraint_duals.json and outputs/capacity_tranches.json,
                plus chain state (tranches/, retention/)
    exports/    results.csv, marginals.csv, storage.csv, transmission.csv, manifest.csv,
                acceptance_*.csv, increments.csv, sharp/,
                per_chain/ with duals_<cell>.csv and one frame per chain
    dashboard.html
```

The Inputs, Assumptions and Scenarios Report (IASR) is AEMO's published workbook of National Electricity Market (NEM)
modelling inputs; `workbook_cache_final/` is its parsed cache and `traces/isp_2026/` is the parsed demand and weather
trace store. `tracedirs/` holds one rewritten demand trace directory per (trajectory, milestone year), built by
`msm launch` the first time a trajectory is used, and rebuilt whenever the demand plan's authored knots for that
trajectory change, so an edited plan is never served from directories scaled to the knots it replaced. A run reads the
newest input package unless `MSM_INPUTS` names another one, and records the package it read in `campaign/inputs.txt`.
Each `outputs/<stamp>_<run_set>/` directory is one launch's complete output, laid out by `analysis.env.OutputLayout`.

## `.env` setup

Copy `.example.env` to `.env` and set each variable for the machine you are on:

| Variable | What it sets |
| --- | --- |
| `IO_DIR` | Root of every input and run product: `\\fs1-cbr.nexus.csiro.au\{en-pathways}\work\AusTIMES2\data\ispypsa` on the workstation, `/datasets/work/en-pathways/work/AusTIMES2/data/ispypsa` on the cluster |
| `MSM_INPUTS` | Optional. Input package to read instead of the newest one, as a directory name under `$IO_DIR/inputs` or an absolute path |
| `MSM_SLURM_ACCOUNT` | Slurm account the campaign's jobs are charged to |
| `MSM_SLURM_PARTITION` | Optional. Slurm partition overriding the one each sbatch script names in its header (`h24` for solves, `h2` for extraction); leave unset |
| `GRB_LICENSE_FILE` | Gurobi licence file on the cluster |
| `UV_CACHE_DIR` | `uv` package cache, kept on the cluster's local scratch filesystem |

The two `IO_DIR` paths point at the same network-mounted storage, so nothing is copied between the workstation and the
cluster. The last four variables matter on the cluster only.

petrichor's `/scratch3` is flushed periodically, so it holds only the repository clone and the `uv` cache; every run
product and export lives under `IO_DIR`.

## Workflow

Running the campaign is five `msm` commands, in order, the first of them once per launch stage:

| Step | Where | Command | What it produces |
| --- | --- | --- | --- |
| 1 | Cluster login node | `msm launch --run-set sc5 --stage base` | Stamps `$IO_DIR/outputs/<stamp>_sc5/`, builds any missing trace directories, writes the chain manifest and the input package it read, and submits the base chain to Slurm |
| 1b | Cluster login node | `msm launch --run <dir> --stage branch --after <base job id>` | Submits the increment grid into the same launch directory, held until the base chain it seeds from finishes |
| 2 | Cluster compute nodes (automatic) | `msm solve --run-id ... --output-root ...` | One chain of single-period solves, one call per Slurm array task |
| 3 | Cluster login node | `msm extract --run <dir>` | Reads the solved networks and writes the `exports/` CSVs (submits itself as a Slurm array job when Slurm is present, or pass `--local` to run in-process) |
| 4 | Anywhere `IO_DIR` is mounted | `msm sharp --run <dir>` | The ShARP deliverable CSVs under `exports/sharp/` |
| 5 | Anywhere `IO_DIR` is mounted | `msm dashboard --run <dir> --show` | `<dir>/dashboard.html`, a self-contained page colleagues can open straight from the share |

Steps 1 to 3 need Slurm; steps 4 and 5 do not. `msm launch --run <dir> --resume` re-submits only the chains whose own
final period has not completed, which for a branch cell is its single year. Run `uv run msm <command> --help` for every
flag.

## What a launch runs

One manifest holds both stages, so a resume or a stage-by-stage submission always reads a complete picture:

| Stage | Chains | What each one solves |
| --- | --- | --- |
| `base` | 1 | The Step Change base chain `ext_step_change_sc`, recursive-dynamic over 2026 and every fifth year from 2030 to 2060, its annual cap set to the Step Change emissions intensity at each milestone |
| `branch` | 504 | One conditioned single-year solve per increment-grid cell: every pair of 8 demand and 9 intensity levels (72 cells) at each of the plan's seven `increment_years`, 2030 to 2060 |

`--stage base|branch|all` chooses which of the two to submit, and `--after <job id>` holds the submission behind a Slurm
job, so the grid queues behind the base chain it seeds from. Each branch row carries its own flags in the manifest:
`--periods <its year>`, its own `--co2-cap-t-schedule`, `--seed-state-from ext_step_change_sc` to copy the base chain's
carried tranches and retention floors from before its year, and `--pin-base-stock` to hold the existing fleet at what
the base chain retained rather than letting the cell retire below it. Every chain solving 2026 or 2030, base and branch
alike, also carries `--pipeline-period 2030` with the two near-term allowances as `YEAR:MW` schedules,
`--new-entrant-cap-mw` over new-entrant generators and `--new-entrant-storage-cap-mw` over new-entrant batteries, so
the near term matches the ISP pipeline, and `--pipeline-rush-charge <generation>,<storage>`: in 2030 itself build above
each allowance pays that rush charge in A$/MW/yr up to a hard ceiling of twice the allowance, while 2026 keeps its
allowance as a hard cap. `--max-cap`
belonged to the earlier ladder of cap chains and now raises, because this plan has one base chain and no ladder to
narrow.

`--rez-limit-factor N` relaxes every renewable energy zone (REZ) transmission, expansion and resource limit by `N` in
each chain of the launch, leaving the interconnector flow paths and every published cost alone;
`--flow-path-limit-factor N` relaxes the interconnector and intra-region flow-path expansion limits the same way; and
`--solve-flags` appends extra `msm solve` tokens to every chain (for example `--solve-flags="--gurobi-crossover 0"` for
a barrier-only feasibility screen; the equals form is needed because the value starts with a dash). Every launch writes
`campaign/assumptions.json` - its limit factors, solve flags, chain count, increment grid and input package - which the
dashboard lists in its assumptions table, so each page states what its own run was launched under.

The two priced build curves are reached through `--solve-flags`. `--social-licence-premiums 0.15,0.60` prices REZ
generation and network capacity above AEMO's published limits as stepped tranches and adds the state landholder
payments to every expansion link; `--build-rate-premiums analysis/model/data/build_rate_premiums_central.csv` prices
each carrier's new build above the period's baseline additions. Every solve writes what its tranches charged to
`outputs/capacity_tranches.json`, which `msm extract` turns into the `social_licence_premium_aud_per_yr`,
`build_rate_premium_aud_per_yr` and `pipeline_rush_premium_aud_per_yr` columns of `results.csv` and the
`premium_aud_per_yr` column of `transmission.csv`. So
the campaign launches with:

```bash
FACTORS='--rez-limit-factor 4.0 --flow-path-limit-factor 4.0'
PREMIUMS='--social-licence-premiums 0.15,0.60 --build-rate-premiums analysis/model/data/build_rate_premiums_central.csv'
uv run msm launch --run-set sc5 --stage base $FACTORS --solve-flags="$PREMIUMS"
uv run msm launch --run <dir> --stage branch --after <base job id> $FACTORS --solve-flags="$PREMIUMS"
```

## Importing inputs and run products produced outside `IO_DIR`

Inputs and run products are brought onto `$IO_DIR` by hand, with no command in this package involved:

- A new set of input stores goes into one stamped package directory, `$IO_DIR/inputs/<stamp>_<label>/`, holding `iasr/`,
  `workbook_cache_final/`, `traces/isp_2026/` and `tracedirs/` at the paths given in "`IO_DIR` layout" above. Later runs
  pick up the newest package, so an earlier one stays readable by any run that names it with `MSM_INPUTS`.
- A run solved on local or scratch storage is `rsync`ed into one stamped launch directory,
  `$IO_DIR/outputs/<stamp>_<run_set>/`, carrying its `configs/`, `logs/`, `records/`, `runs/`, `campaign/` and
  `exports/` subdirectories.

## Moving to its own repository

This package is designed to move to its own repository without change: it imports only the public `ispypsa` package
(never `ispypsa`'s test helpers or internal fixtures), every small authored input it ships (`analysis/model/data/`)
resolves as a package-relative path rather than an absolute one, its tests are self-contained under
`tests/test_analysis/`, and its two extra dependencies (`cyclopts`, `python-dotenv`) are grouped together in
`pyproject.toml`.

## Further reading

- [MODELLING_ASSUMPTIONS.md](MODELLING_ASSUMPTIONS.md) - every way this fork's model differs from upstream ISPyPSA and
  from AEMO's published inputs.
- [REPRODUCING.md](REPRODUCING.md) - how to reproduce an electricity investment history end to end.
- The ShARP export CSVs, what each one contains, and which command emits it:

  | CSV | Produced by | Contents |
  | --- | --- | --- |
  | `exports/results.csv` | `msm extract` | Generation mix (TWh and share by carrier, storage discharge included as its own carriers), built capacity by carrier (1 MW reporting floor), total and average system cost, absolute emissions and intensity, renewable fraction, load-shedding flags |
  | `exports/storage.csv` | `msm extract` | Storage build by carrier and duration class (power, energy, unit count) |
  | `exports/transmission.csv` | `msm extract` | One row per REZ connection and sub-region flow path per cell-year: templated capacity, solved capacity, and the relaxed expansion and transmission limits the solve could reach |
  | `exports/marginals.csv` | `msm extract` | Finite-difference marginal cost and marginal emissions intensity of demand between adjacent trajectories, plus the thermal/renewable split of the marginal generation |
  | `exports/manifest.csv` | `msm extract` | Run identifier, pressure setting, cap tonnage and shadow price, solver settings, termination status, residuals, wall time, output paths |
  | `exports/acceptance_per_cell.csv`, `acceptance_per_grid.csv` | `msm extract` | The campaign's acceptance tests, per cell-period and per grid |
  | `exports/increments.csv` | `msm extract` | One row per increment-grid branch cell against the base cell it branched from, written only by a campaign carrying an increment grid: `base_cell`, `cell`, `year`, `demand_level`, `intensity_level`, `fleet_intensity_t_per_mwh`, then the branch-minus-base differences `delta_delivered_twh`, `delta_total_cost_aud_per_yr`, `delta_cost_per_mwh_excl_fuel_carbon`, `delta_co2e_kt_per_yr`, `delta_pj_gas`, `delta_pj_coal` and one `delta_new_gw_<carrier>` per carrier, the implied carbon price each side faced (`cap_dual_base`, `cap_dual_branch`) and one `dual_<constraint>` column for the twenty largest constraint duals of the campaign |
  | `exports/sharp/methods.csv` | `msm sharp` | One row per archetype: method identifier, short name, description, role |
  | `exports/sharp/method_years.csv` | `msm sharp` | One row per (archetype, milestone year): cost per unit excluding fuel and carbon, input fuel commodities and coefficients, energy and process emissions by pollutant, activity bounds |
  | `exports/sharp/energy_intensity_by_fuel.csv` | `msm sharp` | One row per (archetype, milestone year, fuel): fuel use in gigajoules per MWh delivered, carrying a zero row for every fuel an archetype-year does not burn |
  | `exports/sharp/nger_factor_table.csv` | `msm sharp` | Provenance of the National Greenhouse and Energy Reporting (NGER) emission cross-walk |
  | `exports/sharp/diagnostics.csv` | `msm sharp` | Bundled vs decoupled cost, fuel cost share, delivered demand, physical-mass CH4/N2O/CO2 intensities |

## Solving over network-mounted storage

Solved networks and logs are written to the network-mounted `$IO_DIR`, where Gurobi's and PyPSA's many small file reads
and writes are slower than on local disk. Where that cost matters, point `RUN_DIR` at local scratch storage for the
solve and import the finished run products afterwards.
