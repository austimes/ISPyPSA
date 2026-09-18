# Extension campaign

Emissions-capped capacity expansion for the NEM over 2030 to 2060: five demand trajectories, ten pressure settings (four
carbon prices and six absolute cap schedules), 41 recursive-dynamic chains solved on petrichor. The campaign design is
in `../intensity_demand_map/EXTENSION_CAMPAIGN_BRIEF.md`.

For the source versions, fuel settings, input preparation commands and Windows trace-copy option, see [reproducing electricity investment histories](../../docs/reproducing-electricity-histories.md).

## Regenerate everything

```bash
uv run python analysis/extension_campaign/refresh.py
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

## Pieces

| script                                                                             | role                                                                                       |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `build_manifest.py`                                                                | Turns the demand plan into the 41-chain manifest and cap tonnages (`outputs/campaign/`)    |
| `build_trajectory_demand_dirs.py`                                                  | Rewrites the demand traces per trajectory and milestone, with the FY2050 to FY2060 relabel |
| `hold_supply_curves.py`                                                            | Extends the gas and biomass supply curves to 2060 by holding their last year               |
| `chain.sbatch`, `smoke.sbatch`, `fullyear.sbatch`                                  | Slurm launchers for the production array, the NSW smoke chain and full-year validations    |
| `build_dashboard_data.py`, `build_dashboard.py`                                    | Solved milestones to JSON, JSON to the monitoring page                                     |
| `build_deliverables.py`, `build_cost_dashboard_data.py`, `build_cost_dashboard.py` | Cost decomposition per cell, marginals, and the cost-surface page                          |
| `refresh_remote.sh`, `refresh.py`                                                  | The cluster half and the single entry point above                                          |

## Launching solves

```bash
sbatch --array=0-40 analysis/extension_campaign/chain.sbatch
```

Rows come from `outputs/campaign/chains_index.csv`. Every run product lands under the gitignored `outputs/` root (see
`analysis/benchmarks/output_layout.py`); nothing under it is committed.
