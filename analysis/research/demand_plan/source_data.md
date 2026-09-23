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

## S001, measured per financial year

The trace store's Step Change `OPSO_MODELLING` total over all 15 sub-regions per financial year, summed as
`analysis/hpc/tracedirs.py` sums it (half-hourly MW x 0.5 h, July rolling into the next year), TWh:

| FY | TWh | FY | TWh | FY | TWh | FY | TWh |
| -: | --: | -: | --: | -: | --: | -: | --: |
| 2026 | 178.116 | 2034 | 215.296 | 2042 | 243.442 | 2050 | 251.925 |
| 2027 | 179.483 | 2035 | 219.336 | 2043 | 244.922 | 2051 | 251.984 |
| 2028 | 181.121 | 2036 | 224.376 | 2044 | 246.224 | 2052 | 252.088 |
| 2029 | 183.191 | 2037 | 229.470 | 2045 | 247.158 | 2053 | 251.659 |
| 2030 | 189.818 | 2038 | 234.131 | 2046 | 248.818 | 2054 | 251.475 |
| 2031 | 196.103 | 2039 | 237.622 | 2047 | 250.048 | 2055 | 251.825 |
| 2032 | 203.635 | 2040 | 240.051 | 2048 | 251.214 | 2056 | 251.168 |
| 2033 | 210.146 | 2041 | 241.796 | 2049 | 251.808 | | |

FY2026 lacks its first half-hour (the store starts at 00:30 on 1 July 2025), a loss of under 0.01%.

## S008 -- AEMO final 2026 ISP generation and storage outlook, Step Change

**Source:** [`../aemo_scenario_cost/aemo_2026_isp_cdp4_costs_generation.csv`](../aemo_scenario_cost/aemo_2026_isp_cdp4_costs_generation.csv),
the committed extract of the outlook's Generation sheet; the verbatim workbook path is under S001 of
[`../aemo_scenario_cost/source_data.md`](../aemo_scenario_cost/source_data.md). Series used, GWh:

| FY | Generation excluding rooftop and storage | Storage and DSP net generation |
| -: | ---------------------------------------: | -----------------------------: |
| 2027 | 190,599 | -941 |
| 2030 | 210,467 | -7,230 |
| 2035 | 259,031 | -13,056 |
| 2040 | 294,160 | -16,240 |
| 2045 | 317,019 | -17,843 |
| 2050 | 332,097 | -19,242 |

## S009 -- 2026 IASR workbook, hydrogen demand sheets

**Source:** `2026-isp-inputs-and-assumptions-workbook.xlsm` in the campaign input directory, sheets
`Hydrogen demand - Domestic`, `Hydrogen demand-Export&Commod` and `Other hydrogen assumptions`.

Verbatim instruction repeated on each demand block:

> "To estimate the electricity load required for the electrolysers, multiply 'Mts' by 'electrolysers electricity
> consumption rate (kWh/kg H2)' detailed in the sheet 'Other hydrogen assumptions'."

Verbatim heading of the green steel block:

> "REZ-based Electricity demand for green steel production (TWh/annum)"

Step Change totals over all sub-regions, and the resulting load with the PEM consumption rate:

| FY | Domestic H2 (Mt) | Green-commodity H2 (Mt) | Export H2 (Mt) | Green steel (TWh) | PEM rate (kWh/kg) | Load (TWh) |
| -: | ---------------: | ----------------------: | -------------: | ----------------: | ----------------: | ---------: |
| 2030 | 0.005 | 0 | 0 | 1.023 | 53.69 | 1.3 |
| 2035 | 0.148 | 0.010 | 0 | 1.023 | 48.95 | 8.8 |
| 2040 | 0.332 | 0.012 | 0 | 1.023 | 44.62 | 16.4 |
| 2045 | 0.504 | 0.045 | 0 | 1.023 | 43.00 | 24.6 |
| 2050 | 0.605 | 0.077 | 0 | 1.023 | 43.00 | 30.3 |

Balance-of-plant load, which the sheet sets at 0.054 of total electrolyser capacity in MW, is not included, because electrolyser capacity is a
model output, not an input.

## S010 -- ShARP post-2050 quantity rule

**Source:** `library/roles/generate_grid_electricity/assumptions_ledger.csv`, row `A046`, and
`overflow_supply_pathway_states.csv` in `austimes/sharp` at commit `eaf1ca27`.

From A046's `rationale`, verbatim:

> "Post-2050 quantities continue each corrected future's 2040-2050 absolute trend."

`planned_quantity` of `electricity__grid_supply__current_policy_clean_transition`, TWh of national delivered electricity:
299.3 (2040), 324.5 (2045), 339.7 (2050), 359.7 (2055), 379.7 (2060), 399.7 (2065), 419.7 (2070).
