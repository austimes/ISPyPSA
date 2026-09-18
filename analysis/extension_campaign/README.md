# Extension campaign

Emissions-capped capacity expansion for the NEM over 2030 to 2060: five demand trajectories, ten pressure settings (four
carbon prices and six absolute cap schedules), 41 recursive-dynamic chains solved on petrichor. The campaign design is
in `../intensity_demand_map/EXTENSION_CAMPAIGN_BRIEF.md`.

For the source versions, fuel settings, input preparation commands and Windows trace-copy option, see [reproducing electricity investment histories](../../docs/reproducing-electricity-histories.md).

## Regenerate everything

```bash
uv run isp refresh
```

That one command pulls the branch on petrichor, reads every solved milestone on a compute node, runs the
cost-deliverables pipeline, copies the products to `outputs/exports/`, renders both dashboards, and copies them to the
team share. It is deterministic given the solved networks on the cluster and safe to re-run. Use `--skip-remote` to
re-render from products already fetched, and `--no-share` to leave the share alone. Publishing the pages to their Claude
artifact links is the one manual step; the script prints the files.

Machine-specific locations come from the environment, with defaults matching the campaign's current homes:

| variable                  | default                                  | meaning                                     |
| ------------------------- | ---------------------------------------- | ------------------------------------------- |
| `ISPYPSA_REMOTE_HOST`     | `petrichor`                              | ssh host holding the runs                   |
| `ISPYPSA_REMOTE_REPO`     | `/scratch3/wes148/code/ispypsa`          | clone on that host                          |
| `ISPYPSA_SHARE_DIR`       | `P:/work/AusTIMES2/data/ispypsa/outputs` | where colleagues open the pages             |
| `ISPYPSA_SLURM_ACCOUNT`   | `OD-241887`                              | cluster stage (read by `refresh_remote.sh`) |
| `ISPYPSA_SLURM_PARTITION` | `defq`                                   | cluster stage                               |
| `ISPYPSA_WORKERS`         | `16`                                     | parallel network reads on the compute node  |

## Commands

Every campaign entry point is a command of the one cyclopts app in `analysis/cli.py`, so nothing is run by script path.
`uv run isp --help` lists them; `uv run isp <command> --help` shows a command's options. On petrichor's compute nodes,
which have no internet, run them as `uv run --no-sync isp <command>`.

| command               | script                            | role                                                                                       |
| --------------------- | --------------------------------- | ------------------------------------------------------------------------------------------ |
| `manifest`            | `build_manifest.py`               | Turns the demand plan into the 41-chain manifest and cap tonnages                          |
| `tracedirs`           | `build_trajectory_demand_dirs.py` | Rewrites the demand traces per trajectory and milestone, with the FY2050 to FY2060 relabel |
| `hold-curves`         | `hold_supply_curves.py`           | Extends the gas and biomass supply curves to 2060 by holding their last year               |
| `deliverables`        | `build_deliverables.py`           | Cost decomposition per cell and marginals                                                  |
| `cost-dashboard-data` | `build_cost_dashboard_data.py`    | Deliverable tables to the cost-surface page's JSON                                         |
| `cost-dashboard`      | `build_cost_dashboard.py`         | JSON to the cost-surface page                                                              |
| `refresh`             | `refresh.py`                      | The single entry point above, driving the cluster half in `refresh_remote.sh`              |

The Slurm launchers `chain.sbatch`, `smoke.sbatch` and `fullyear.sbatch` stay separate: they call
`analysis/benchmarks/run_myopic.py`, which is not a campaign command.

## Launching solves

```bash
sbatch --array=0-40 analysis/extension_campaign/chain.sbatch
```

Rows come from `outputs/campaign/chains_index.csv`. Every run product lands under the gitignored `outputs/` root (see
`analysis/benchmarks/output_layout.py`); nothing under it is committed.
