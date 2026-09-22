# Campaign method -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- Chain submission script

**Source:** [`analysis/hpc/slurm/chain.sbatch`](../../hpc/slurm/chain.sbatch).

On what one array task is, verbatim:

> "One array task = one campaign chain: a recursive-dynamic solve over the milestones 2030/2040/2050/2060. The array index is the 0-based
> line number in $RUN_DIR/campaign/chains.tsv, so `msm launch` writes the manifest and submits the array together."

The allocation, verbatim:

> ```bash
> #SBATCH --nodes=1 --ntasks=1 --cpus-per-task=64
> #SBATCH --mem=240G
> #SBATCH --time=3-00:00:00
> ```

The solve command, verbatim:

> ```bash
> uv run --no-sync msm solve --run-id "$RUN_ID" --output-root "$RUN_DIR" \
>   --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing --existing-fom-keeping \
>   --parsed-traces-directory-schedule $(cat "$TRACES") \
>   --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 --no-named-weeks \
>   --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
>   --use-gurobi --gurobi-method 2 --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
>   --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 ${RESUME:-} $ARGS
> ```

## S002 -- Generated period config

**Source:** [`analysis/hpc/solve.py`](../../hpc/solve.py), from the template written for every period, verbatim:

> ```yaml
> iasr_workbook_version: "7.8"
> scenario: Step Change
> wacc: 0.07
> discount_rate: 0.05
> ```

and

> ```yaml
> network:
>   transmission_expansion: True
>   rez_transmission_expansion: True
>   annuitisation_lifetime: 30
>   nodes:
>     regional_granularity: sub_regions
>     rezs: discrete_nodes
>   rez_to_sub_region_transmission_default_limit: 1e5
> temporal:
>   year_type: fy
>   ...
>   capacity_expansion:
>     resolution_min: 30
>     reference_year_cycle: [2018]
> ```

On the Gurobi flags, verbatim from the runner's argument help:

> "Set Gurobi Method (0=primal simplex, 1=dual simplex, 2=barrier, ...)"

> "Set Gurobi BarConvTol (default 1e-8); e.g. 1e-3 for relaxed run"

so `--gurobi-method 2 --gurobi-bar-conv-tol 1e-8` selects barrier at the default tolerance rather than a relaxed one.

## S003 -- Recursive-dynamic roll-forward

**Source:** [`analysis/model/recursive_dynamic.py`](../../model/recursive_dynamic.py).

On why it exists, verbatim:

> "Solving each milestone year as an independent static greenfield problem ignores capacity built in earlier years. Locking 2040 capacity into
> a 2045 solve instead shifts emissions ~+17% and renewable share ~-7.7 pp, so a greenfield chain does not give a realistic emissions and
> capacity trajectory."

On the carbon price paid by carried plant, verbatim:

> "Carried rows carry physical characteristics (heat_rate, residual_co2, captured_co2 -- vintage-invariant per IASR) but reference the
> *base-tech* marginal_cost mapping. The year-(t+1) translator regenerates the marginal_cost parquet at year-(t+1)'s
> `config.carbon_pricing.carbon_price`, so a 2030-built CCGT dispatched in 2045 pays 2045's carbon adder, not 2030's."

On storage, verbatim:

> "Carried batteries get `p_nom_extendable=False` with the solved `p_nom_opt` and original `max_hours`; SOC is re-solved fresh by year (t+1)
> under PyPSA's existing `cyclic_state_of_charge=True` convention"

On vintage accumulation, verbatim:

> "Each year's tranche is persisted to its own file (`tranches/<year>.parquet`) and `load_tranches(before_year=...)` concatenates ALL
> surviving prior tranches."

On retirement, verbatim:

> "a carried row's PyPSA `lifetime` is the IASR new-entrant lifetime (annuitisation lifetime == technical/economic operating life -- they are
> the same physical quantity, not a convenience coincidence)."

## S004 -- The 2060 hold

**Source:** [`analysis/hpc/tracedirs.py`](../../hpc/tracedirs.py), verbatim:

> "Source financial year that supplies a milestone; 2060 is built from the last modelled year, FY2050."

> "FY2050 rows copied forward ten years, so a store that stops before 2060 gains an FY2060."

> "Copy one VRE subdirectory unscaled, appending its FY2050 rows relabelled to FY2060."

For the hydro budget, verbatim from [`src/ispypsa/pypsa_build/generators.py`](../../../src/ispypsa/pypsa_build/generators.py):

> "AEMO SC hydro budget for a financial year, clamped to the published 2027-2050 range"

For the fuel supply curves, verbatim from the last rows of
[`analysis/model/data/gas_supply_curve_central_held_to_2060.csv`](../../model/data/gas_supply_curve_central_held_to_2060.csv):

> ```text
> existing_market,2055,90.0,0.0
> ...
> existing_market,2060,90.0,0.0
> ```

Every 2060 row in both the gas and the biomass curve repeats its 2055 values, which is what "held to 2060" in the filenames means.

## S005 -- Snapshot count cross-check

Thirteen representative weeks at 30-minute resolution give 13 x 7 x 48 = 4,368 snapshots per period. The same figure appears in the ShARP
review of solved ISPyPSA networks (see [`../demand_plan/source_data.md`](../demand_plan/source_data.md), S004), verbatim:

> "each network's generator snapshot weights: 4,368 snapshots annualised to 8,760 hours"

which confirms the weighting convention rather than only the count.
