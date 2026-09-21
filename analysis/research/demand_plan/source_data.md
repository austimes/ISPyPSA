# Demand plan -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- AEMO 2026 final IASR parsed demand trace store

**Source:** parsed trace store under `traces/isp_2026/demand/`, read by
[`analysis/hpc/tracedirs.py`](../../hpc/tracedirs.py) (`_measure_demand_energy`, `_parquets`). Partitioned by scenario, point of exceedance
(POE), demand type and reference year.

No verbatim quote is available: this is a parquet dataset, not a document, and it lives outside the repository on a network share.

What the repository states about it, from `tracedirs.py`:

> "Source financial year that supplies a milestone; 2060 is built from the last modelled year, FY2050."

Measured content, reported in the reasonableness check filed under S004:

| Quantity | Value |
|---|---|
| Partitions present | one only: scenario Step Change, POE50, demand type `OPSO_MODELLING`, reference year 2018 |
| Financial years present | FY2026 to FY2056 in full (no FY2025) |
| Step Change source-NEM totals, all 15 sub-regions | 189.818 TWh (FY2030), 240.051 TWh (FY2040), 251.925 TWh (FY2050) |

These three totals are the ones hard-coded in [`plot_demand_trajectories.py`](plot_demand_trajectories.py); the store itself is not in the
repository, so the script carries them as constants with this source named beside them.

## S002 -- AEMO 2026 draft ISP candidate development path 4 (CDP4) energy outputs

**Source:** [`iasr outputs/NEM-aemo2026draft-<scenario>-CDP4 (ODP)-energy.csv`](../../../iasr%20outputs/) in the repository root, one file
per scenario for `slower_growth`, `step_change` and `accelerated_transition`.

Verbatim header row of `NEM-aemo2026draft-step_change-CDP4 (ODP)-energy.csv`:

> `"date","Demand Response","Coal","Bioenergy","Distillate","Gas","Hydro","Wind","Solar (Utility)","Solar (Rooftop)"`

and its first data row:

> `"1 Jan 2010 12:00 am","0","171","0","0","21","13","4","0","0"`

One row per year from 2010 to 2050, each timestamped `1 Jan <year> 12:00 am`, values in TWh. The plot and the research tables use total
generation less `Solar (Rooftop)`, because behind-the-meter rooftop output never crosses the NEM. `Demand Response` is 0 TWh in every
scenario-year except Accelerated Transition 2050, where it is 1 TWh.

| Scenario | 2030 | 2040 | 2050 |
|---|---:|---:|---:|
| Slower Growth, excluding rooftop | 174.0 | 220.0 | 268.0 |
| Step Change, excluding rooftop | 209.0 | 291.0 | 332.0 |
| Accelerated Transition, excluding rooftop | 221.0 | 375.0 | 491.0 |

The single annual timestamp does not by itself prove calendar-year against financial-year totalling; these are read as AEMO's convention of
labelling an annual result by the financial year ending 30 June of the stated year. That is a convention read, not something the file proves.

## S003 -- AEMO Electricity Demand Forecasting Methodology

**Source:** [Electricity Demand Forecasting Methodology](https://www.aemo.com.au/-/media/files/electricity/nem/planning_and_forecasting/nem_esoo/2024/electricity-demand-forecasting-methodology.pdf),
sections 2.2 and 3.10, cited by S004.

No verbatim quote is available: no local copy of this document exists in or beside this repository. S004's paraphrase of it is quoted under
S004 below.

## S004 -- ShARP review, quantity boundary reconciliation

**Source:** `docs/reviews/ispypsa-electricity/quantity-reconciliation.md` in the ShARP repository at commit
`a09411440235da436607cb31bffb232aaeb35a50`. Absent from that repository's default branch; read with
`git show a0941144...:docs/reviews/ispypsa-electricity/quantity-reconciliation.md`.

On what the demand quantity is:

> "The source demand translator reads `OPSO_MODELLING` and preserves negative local demand from distributed PV exports."

On the component definition:

> "The 2026 ISP demand-component definitions specify `OPSO_MODELLING = OPSO - ICL + EVVPP`: estimated interconnector losses have already
> been removed, and coordinated EV charging is added. Operational demand already accounts for rooftop PV and other embedded non-scheduled PV.
> Hydrogen-production demand is excluded."

On the loss boundary, paraphrasing S003:

> "AEMO distinguishes sent-out demand from customer-delivered electricity. Transmission and distribution losses are added to delivered
> consumption to derive operational consumption; generator auxiliary use is then added to derive the as-generated measure."

On the national factor:

> "Let `beta = 1.3` be the stipulated national handover assumption."

## S005 -- ShARP review, authored delivery and biomass projections

**Source:** `docs/reviews/ispypsa-electricity/owner-projections.md` and `owner-projections.json` at the same commit.

On the loss fraction:

> "The loss projection is 9% of operational load: approximately 3% transmission and 6% distribution, flat in 2030, 2040 and 2050 and held
> through 2070. The owner's stated basis is a standard NEM sent-out loss allowance. It is a disclosed placeholder, not a measured AEMO
> forecast."

> "Customer delivery is 0.91 times the residual source load after the biomass deduction."

From `owner-projections.json`, verbatim field values:

> `"status": "authored_pending_ratification"`, `"pending_ratification": true`, `"source_boundary": "source_nem_load"`,
> `"target_boundary": "customer_delivery"`

> `"anchor_2025": {"status": "accepted planned anchor", "reference": "library/validation/aes_2025_electricity_supply_bridge.csv: planned
> customer-delivered residual grid quantity, 193.911 TWh"}`

## S006 -- ShARP review, OPSO delivery bridge

**Source:** `docs/reviews/ispypsa-electricity/delivery-bridge.md` at the same commit.

On what is still missing:

> "The remaining author input is a versioned public forecast or an approved projection for each loss component, plus the treatment of rooftop
> PV and other embedded PV."

The arithmetic the bridge defines, verbatim:

> ```text
> behind_meter_pv = rooftop_pv + other_embedded_pv
> underlying = delivered + behind_meter_pv
> opso = underlying + distribution_losses + transmission_losses - behind_meter_pv
> delivered = opso - distribution_losses - transmission_losses
> ```

## S007 -- The campaign's own demand plan

**Source:** [`analysis/hpc/demand_plan.json`](../../hpc/demand_plan.json), verbatim:

> ```json
> {
>   "version": "20260921-isp-range-v2",
>   "delivery_fraction": 0.91,
>   "milestone_years": [2030, 2040, 2050, 2060],
>   "anchor_2025_customer_delivered_twh": 193.911
> }
> ```

The `demand_paths_source_twh` block carrying the five trajectories is omitted here only for length; it is reproduced in full in the
`research.md` table and read directly by the plot script.

In this plan version `iasr_low` and `iasr_stress` are the S002 Slower Growth and Accelerated Transition generation proxies multiplied by
0.97, and `iasr_low_bracket` is `iasr_low` multiplied by 0.92. Neither multiplier is stated in the file: the file carries only the resulting
TWh, and the factors are recovered exactly by dividing the plan's knots by the S002 table above. The 0.97 itself is recorded as authored
assumption A010, and no document in or beside this repository states it.
