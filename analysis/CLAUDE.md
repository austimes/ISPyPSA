# Working rules for `analysis/`

The root `CLAUDE.md` applies; these are the extra rules for campaign work here.

## Code

- `/ponytail ultra` on every change: laziest working solution, shortest diff, delete before adding, stdlib and existing
  deps before new ones, challenge the requirement in the same breath. Mark deliberate ceilings with a `# ponytail:`
  comment naming the upgrade path.
- One CLI: every command lives in `analysis/cli.py` on cyclopts and runs as `uv run isp <command>`. No new argparse.
- Every run product goes under the gitignored `outputs/` root via `analysis/benchmarks/output_layout.py`. Nothing under
  it is committed; records and exports reach colleagues through the team share.
- No hard-coded machine paths. Hosts, repos and shares come from environment variables with documented defaults (see
  `analysis/extension_campaign/README.md`).
- Compute nodes have no internet: cluster commands use `uv run --no-sync` and the scratch uv cache.
- Tests only where a break would be silent: schedule parsing, cap arithmetic, boundary rules. No per-function suites, no
  fixtures for their own sake.
- Australian spelling, no emoji or non-keyboard characters in code, ReST docstrings, `logging.warning` with
  `sorted(...)` collections for data the pipeline alters.

## Results

- A milestone is a menu member only if solver-certified, cap-tracked within 1% and shedding under 0.1% of demand;
  otherwise it is a boundary measurement and is drawn hollow and excluded from marginals.
- Caps are written in absolute tonnes with their basis (delivered vs source) shown beside them. Never quote one without
  it.
- Authored inputs (2060 horizon hold, long-duration pumped hydro, held supply curves) are flagged in every export.

## Process

- Stage the spend: smoke chain, then one pilot, then the grid. Surface-and-pause on any gate failure.
- Regenerate everything with `uv run isp refresh`; the dashboards are published from `outputs/exports/`.
- Report solver tolerance honestly: PDLP `model_status` reads Unknown even when converged; certify on the three relative
  metrics.
