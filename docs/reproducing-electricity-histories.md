# Reproducing electricity investment histories

Use a source checkout and `uv sync --frozen`. The campaign runner applies modelling pre-passes under `analysis/archetypes`, including the restored pumped-hydro candidates. Calling the package builder alone does not apply the same assumptions.

The historical campaigns and their launch settings are recorded under [demand/carbon sweep](../analysis/demand_carbon_sweep/) and [intensity/demand map](../analysis/intensity_demand_map/). Preserve the source commit, lockfile, input workbook and traces, demand settings, absolute annual emissions caps and solver settings with any reproduction. A later branch head is not evidence of the version used by an earlier solve.

Each new solve record includes the source Git commit, whether the worktree had uncommitted changes, and the SHA-256 of its input YAML. Unavailable provenance is marked explicitly. Large input files are not hashed by the runner; preserve their versions separately.

## Fuel and storage assumptions

Gas and biomass supply curves are enabled by default in `analysis/benchmarks/run_myopic.py`. Their quantity limits and increasing fuel-price premiums remain active in the model. A configured biomass curve replaces the older flat feedstock re-pricing pre-pass, so it is not charged twice. Passing `--biomass-supply-curve none` changes those assumptions.

The CCS supply-curve feature is available on this branch, but the preceding demand/carbon sweep and intensity map disabled it. Those campaigns used `--ccs-supply-curve none --tns-price 89.93`, a flat A$89.93 per captured tonne transport-and-storage charge. The runner's default conservative CCS curve is a different assumption. Do not combine a supply curve with the flat charge.

This branch restores the IASR pumped-hydro candidates and uses AEMO's annual conventional-hydro energy budgets. The extension campaign adds authored one- and two-week pumped-hydro options, later milestones and annual demand/cap schedules in [PR #1](https://github.com/austimes/ISPyPSA/pull/1). Those additions must accompany any result that uses them; they are not observations from the earlier sweep.

Solver completion alone does not establish that demand was served. Check unserved energy, actual emissions against the cap, fuel purchases versus burn, carried capacity and numerical quality before accepting any tight-cap result. The historical floor probes include boundary measurements with material unserved demand.
