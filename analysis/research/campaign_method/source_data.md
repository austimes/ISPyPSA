# Campaign method -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- Chain submission script

**Source:** [`analysis/hpc/slurm/chain.sbatch`](../../hpc/slurm/chain.sbatch).

On what one array task is, verbatim:

> "One array task = one campaign chain: a recursive-dynamic solve over the periods its own manifest row names. The array index is the 0-based
> line number in $RUN_DIR/campaign/chains.tsv, so `msm launch` writes the manifest and submits the array together. The base row carries
> --next-period-only, so `msm launch` submits it once per milestone period, each job chained behind the one before."

The allocation, verbatim:

> ```bash
> #SBATCH --partition=h24
> #SBATCH --nodes=1 --ntasks=1 --cpus-per-task=32
> #SBATCH --mem=96G
> #SBATCH --time=12:00:00
> ```

On crossover, verbatim comment: "Crossover is off for every solve: the barrier solution at BarConvTol 1e-8 is the answer." On memory sizing,
verbatim: "The partition, memory, time and cores are set below, at least 1.25x the use observed per solve (a barrier-only 2060 solve peaks at about
71 GB)."

The solve command, verbatim:

> ```bash
> uv run --no-sync msm solve --run-id "$RUN_ID" --output-root "$RUN_DIR" \
>   --recursive-dynamic --reducible-existing --existing-fom-keeping \
>   --parsed-traces-directory-schedule $(cat "$TRACES") \
>   --rep-weeks 1 6 10 14 19 22 26 32 35 39 41 45 50 \
>   --tns-price 89.93 --ccs-supply-curve none --gas-unblended \
>   --use-gurobi --gurobi-method 2 --gurobi-crossover 0 --gurobi-bar-conv-tol 1e-8 --gurobi-threads $SLURM_CPUS_PER_TASK \
>   --highs-threads $SLURM_CPUS_PER_TASK --budget-min 600 --resume $ARGS
> ```

The `--periods` flag and `--no-named-weeks` flag carried by the earlier one-job-per-chain script are both gone: periods are no longer named on the
command line because each job solves the single next unsolved period the manifest row and `--resume` determine, and named weeks are left on the
config template's default rather than disabled.

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

## S006 -- AEMO ISP Methodology, rationale for the named stress weeks

**Source:** AEMO, *ISP Methodology*, June 2025,
<https://www.aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2024/2026-isp-methodology/isp-methodology-june-2025.pdf>,
page 43. No local copy of the document is held in this repository, so the page is cited without a verbatim quote.

The page is the basis given for turning the two named stress weeks on: AEMO's own net-load-based time sampling deliberately includes the
peak-demand and residual-peak weeks rather than leaving their inclusion to chance. Other pages of the same document are quoted verbatim in
[`../aemo_scenario_cost/source_data.md`](../aemo_scenario_cost/source_data.md) (S007 there, pages 26, 41, 44 and 61), on the sampled and fitted
chronology settings and the reliability-standard check; none of those quotes covers page 43.
