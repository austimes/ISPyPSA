# Campaign method

## Purpose and scope

How a campaign chain is actually solved: the sequence of milestone solves, how much of the year each one looks at, what the solver is told to do, and
what happens at 2060 where the published data runs out. The pressure settings that distinguish one chain from another are in
[`../carbon_caps/`](../carbon_caps/); the demand trajectories are in [`../demand_plan/`](../demand_plan/).

## Recursive-dynamic chains

One chain is a sequence of four single-period solves at 2030, 2040, 2050 and 2060. Each year's newly-built capacity becomes part of the next year's
existing fleet, so the chain accumulates a brownfield stock rather than re-solving greenfield each time.

| Property                      | Treatment                                                                                                                                                                           |
|-------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Carried capacity              | Each year's new tranche is written to `tranches/<year>.parquet` and all surviving prior tranches are concatenated into the next solve                                               |
| Carbon price on carried plant | Carried rows reference the base-technology marginal-cost mapping, which is regenerated at the later year's carbon price, so a 2030-built plant dispatched in 2050 pays 2050's adder |
| Storage                       | Carried storage keeps its solved capacity and maximum hours but not its state of charge, which is re-solved fresh under the cyclic convention                                       |
| Retirement                    | A carried row's lifetime is the IASR new-entrant lifetime; PyPSA's multi-period active-asset check retires expired vintages                                                         |
| Vintages                      | A technology built in two different years yields two distinct carried rows, each persisting subject to its own retirement                                                           |

Why it matters: solving each milestone greenfield ignores what was built earlier. Locking 2040 capacity into a 2045 solve instead shifts emissions by
about +17% and renewable share by about -7.7 percentage points, so a greenfield chain does not give a realistic trajectory.

**confidence: high.** The mechanism, the three correctness traps it clears and the magnitude of the greenfield error are all stated in
[`analysis/model/recursive_dynamic.py`](../../model/recursive_dynamic.py) and implemented as described.

## Time sampling

| Setting                              | Value                                                      |
|--------------------------------------|------------------------------------------------------------|
| Representative weeks                 | 13: weeks 1, 6, 10, 14, 19, 22, 26, 32, 35, 39, 41, 45, 50 |
| Named weeks (peak and residual-peak) | Off, by `--no-named-weeks`                                 |
| Resolution                           | 30 minutes                                                 |
| Reference year cycle                 | 2018                                                       |
| Snapshots per period                 | 13 x 7 x 48 = 4,368, weighted to annualise to 8,760 hours  |

Thirteen weeks spread roughly evenly through the year gives about a quarter of the year's half-hours at a weighting of about 2.0. Turning named weeks
off means the sample carries no deliberately included peak-demand or residual-peak week, so extreme hours enter only if one of the thirteen happens to
contain them.

**confidence: high** on the settings, read from [`analysis/hpc/slurm/chain.sbatch`](../../hpc/slurm/chain.sbatch) and the config template in
[`analysis/hpc/solve.py`](../../hpc/solve.py); **confidence: low** on the choice of those particular thirteen weeks, for which no selection method or
basis is recorded.

## Solver settings

| Setting      | Value                                  | Meaning                                                                                    |
|--------------|----------------------------------------|--------------------------------------------------------------------------------------------|
| Solver       | Gurobi                                 | Selected by `--use-gurobi`; the config's own `solver` field says `highs` and is overridden |
| `Method`     | 2                                      | Barrier, rather than primal or dual simplex                                                |
| `BarConvTol` | 1e-8                                   | Barrier convergence tolerance, the solver default rather than a relaxed one                |
| `Threads`    | 64                                     | Matched to the allocated cores                                                             |
| Budget       | 600 minutes per solve                  | Wall-clock ceiling passed as `--budget-min`                                                |
| Allocation   | 1 node, 64 cores, 240 GiB, 3-day limit | One Slurm array task per chain                                                             |

Other flags carried by every chain: `--reducible-existing` and `--existing-fom-keeping` for how existing plant may retire and what it still costs,
`--tns-price 89.93` as a flat transport-and-storage adder on captured carbon dioxide, `--ccs-supply-curve none`, and
`--gas-unblended` so biomethane is not blended into the gas price. The scenario is Step Change throughout, with a weighted average cost of capital of
0.07, a discount rate of 0.05 and a 30-year annuitisation lifetime, at sub-region granularity with renewable energy zones as discrete nodes and both
transmission and REZ transmission expansion enabled.

**confidence: high** on every setting, all read from the submission script and config template.

## The 2060 hold

No AEMO input reaches 2060, so the fourth milestone is built by holding 2050 conditions forward. Four separate mechanisms do this, and they are worth
listing together because none of them is visible from the 2060 results alone.

| Input                            | How 2060 is produced                                                                                         |
|----------------------------------|--------------------------------------------------------------------------------------------------------------|
| Demand traces                    | FY2050 half-hourly rows copied forward ten years; every 2060 demand scalar is computed against FY2050 energy |
| Wind and solar traces            | FY2050 rows copied forward ten years, unscaled                                                               |
| Conventional hydro energy budget | Clamped to the last published year, FY2050                                                                   |
| Gas and biomass supply curves    | Curve files carry a 2060 row equal to their 2055 values, which the filenames record as "held to 2060"        |

So 2060 is not a forecast. It is 2050's weather, 2050's demand shape, 2050's water and 2050's fuel availability, with an authored demand level and an
authored carbon cap laid over them. What 2060 tests is whether the fleet can meet a deeper cap and a higher load under conditions already seen, not
what 2060 might actually look like.

**confidence: high** on the mechanism; **confidence: low** on 2060 as a representation of anything, for the reason above.

## Plot

[`plot_campaign_sampling.py`](plot_campaign_sampling.py) draws the 13 sampled weeks against the full 52-week year, the two named stress weeks
as a disabled row with no fixed position, and the milestone sequence with the 2060 hold marked. It writes `campaign_sampling.html` and
`campaign_sampling.png` beside itself.
