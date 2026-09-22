# Near-term pipeline and the 2030 new-entrant allowance

## Purpose and scope

Left free, the campaign model builds whatever 2030 capacity is cheapest, and the reference run
(`outputs/2026-09-21T16.08_ext41_rezx4_corrx4`) duly built 33 GW of wind by 2030. Nothing in the real system can deliver
that: 2030 is four years away, the projects that will be running then are largely already committed, and anything not yet
through planning will not be generating by then. A model free to invent near-term capacity decarbonises the near term far
faster than the National Electricity Market (NEM) can, and every later result inherits that head start.

This topic derives the megawatt allowance the campaign gives new entrants in the pinned near-term period: how much
genuinely new capacity can appear in 2030 beyond what is already existing, committed, anticipated or policy-supported. It
also records the two other near-term settings the pin carries, and retires the authored 2030 carbon cap anchor that the
Step Change intensity schedule replaces.

## What the campaign does

| Setting | Value | Effect |
| ------- | ----- | ------ |
| `--pipeline-period 2030` | the first milestone | Turns the pin on for every solve year at or before 2030 |
| `--new-entrant-cap-mw` | 19,000 MW, A003 | One NEM-wide capacity cap over every `New Entrant` generator in the 2030 solve |
| `--new-entrant-storage-cap-mw` | 6,000 MW, A003 | One NEM-wide capacity cap over every `New Entrant` battery in the 2030 solve |
| No economic early retirement | A004 | `make_existing_reducible` is skipped for the pinned period, so plant closes on its announced year and not before |
| 2030 carbon cap | 0.19673 t CO2e/MWh generated, A007 | The Step Change scenario's own 2030 intensity, replacing the authored 0.12 anchor |

Everything already existing, committed, anticipated or policy-supported enters as fixed capacity regardless of the cap;
the cap bounds only what the optimiser adds on top.

## What is already in the model at 2030

Read from the templated inputs of the reference run's 2030 solve (S003), which is the roster any campaign run starts from.
Capacity in gigawatts.

| Carrier | Existing | Committed | Anticipated | Additional policy-supported | In the model at 2030 |
| ------- | -------: | --------: | ----------: | --------------------------: | -------------------: |
| Wind | 11.749 | 3.859 | 2.118 | 2.381 | 20.107 |
| Solar | 10.859 | 2.500 | 5.176 | 1.064 | 19.600 |
| Gas | 10.070 | 0.750 | 0.574 | - | 11.394 |
| Black coal | 11.915 | - | - | - | 11.915 |
| Brown coal | 3.370 | - | - | - | 3.370 |
| Water, conventional hydro | 6.885 | - | - | - | 6.885 |
| Liquid fuel | 0.567 | - | - | - | 0.567 |
| Biomass | 0.032 | - | - | - | 0.032 |
| **Generation total** | **55.447** | **7.109** | **7.869** | **3.446** | **73.870** |
| Battery storage | 4.023 | 6.739 | 3.862 | - | 14.624 |
| Pumped hydro storage | 0.817 | 2.450 | 1.998 | 0.810 | 6.075 |
| **Storage total** | **4.840** | **9.189** | **5.860** | **0.810** | **20.699** |

The pipeline already in the model is therefore **18.4 GW of generation and 15.9 GW of storage**, of which 10.6 GW is
battery. Its composition matters: the pipeline is overwhelmingly wind, solar and batteries, so the near term is already
decarbonising fast without any new-entrant build at all.

## The 2030 allowance

AEMO's Step Change optimal development path (ODP) is the yardstick: the campaign's base chain follows the Step Change
emissions intensity, so its 2030 fleet should be able to reach the Step Change 2030 fleet and not much further. The
allowance per carrier is that path's 2030 capacity (S001) minus what the model already holds.

| Carrier | Draft 2026 ISP Step Change 2030 | In the model at 2030 | Allowance | Buildable |
| ------- | ------------------------------: | -------------------: | --------: | --------- |
| Wind | 26 | 20.107 | 5.9 | yes |
| Solar, utility | 32 | 19.600 | 12.4 | yes |
| Gas | 12 | 11.394 | 0.6 | yes |
| Grid-scale storage, battery and pumped hydro | 27 (S004) | 20.699 | 6.3 | yes |
| Hydro, conventional | 7 | 6.885 | 0.1 | no: the model offers no conventional hydro new entrant |
| Coal | 13 | 15.285 | -2.3 | no: closures follow announced years, A004 |
| Distillate and biomass | 0 | 0.599 | -0.6 | no: no new entrant is offered |
| **Total buildable** | | | **25.2** | |

Gigawatts. Two roundings are worth naming: the CDP4 series is published in whole gigawatts as at 1 January of each year,
while the model's 2030 is the 2029-30 financial year, so a half-year offset and up to 0.5 GW of rounding sit in every
row.

**The recommended settings are `--new-entrant-cap-mw 19000` and `--new-entrant-storage-cap-mw 6000`**: one NEM-wide
megawatt cap over new-entrant generators, and a second over new-entrant batteries. Generation and storage are capped
separately because they are separate supply chains, and because the custom-constraints framework sums one component
type per constraint in any case.

Within generation the cap is deliberately one pooled number rather than a per-carrier schedule, A002. Splitting it per
carrier would pin the 2030 technology mix to AEMO's, which would make the 2030 increment grid a re-reading of AEMO's own answer instead of
a measurement of what an extra terawatt hour or an extra tonne of abatement costs. Pooling keeps the mix free and bounds
only the total, which is the quantity the supply chain actually constrains.

The two-and-a-half gigawatts of coal the model holds above the ODP at 2030 is a direct consequence of A004 and is left as
it is. The ODP retires coal on economics as well as on announcement; the campaign retires it only on announcement in the
pinned period, so the base chain enters 2031 with a slightly larger coal fleet than AEMO's, and the 2030 carbon cap does
the work of displacing its output rather than its capacity.

**confidence: high** on the roster, which is read from the templated inputs; **confidence: high** on the wind, solar and
gas allowances, which are arithmetic against the published CDP4 series; **confidence: low** on the storage allowance,
whose 27 GW anchor is secondary reporting of a combined battery and pumped hydro milestone rather than a series read from
a file.

## Committed batteries with no commissioning date

The templated `ecaa_batteries.csv` carries **29 committed batteries totalling 6,739 MW with an empty `commissioning_date`**,
which the model then treats as available from the start of the run and, in a chain whose first period is 2030, gives an
effective build year of 2029.

The workbook itself is not missing those dates. The cache's
`maximum_capacity_existing_committed_anticipated_additional_generators.csv` carries a commissioning date for every one of
them, running from January 2024 (Tailem Bend) to March 2028 (Bennetts Creek), so the loss happens in templating rather
than in the input. The largest are Waratah Super Battery (844 MW), Western Downs (510 MW), Liddell (500 MW), Gnarwarre
(470 MW) and Orana (417 MW).

What the loss costs this campaign is small, because every one of those dates is 2028 or earlier and the first milestone is
2030, so each unit would be in service by 2030 anyway. It would matter to any run whose first period is 2025 or 2026, and
it is recorded in [`../../MODELLING_ASSUMPTIONS.md`](../../MODELLING_ASSUMPTIONS.md) for that reason.

A second gap found while counting them does bite this campaign, slightly. Ten committed batteries totalling 2,070 MW are
listed in the workbook's maximum-capacity sheet and are absent from its summary sheet, which is the roster the templater
reads, so they never enter the model at all. That is an inconsistency inside the IASR workbook rather than a templating
fault, and its effect is to understate the 2030 storage pipeline, and so overstate the storage allowance, by about 2 GW.
The allowance below is left as derived rather than adjusted for it, because the 27 GW storage anchor it is measured
against carries a wider uncertainty than 2 GW.

**confidence: high.** The 29 rows and the 6,739 MW are counted from the templated file, the workbook dates are read from
the cache table, and the ten missing projects were checked against both workbook sheets by name.

## The base cap schedule

The base chain's carbon cap is no longer an authored ladder. Each milestone takes the Step Change scenario's own emissions
intensity for that year, derived in [`../aemo_scenario_intensity/`](../aemo_scenario_intensity/) and committed as
`aemo_scenario_intensity.csv` (S005).

| Year | Step Change intensity (t CO2e/MWh generated) | Step Change generation (TWh) |
| ---- | -------------------------------------------: | ---------------------------: |
| 2030 | 0.19673 | 209 |
| 2035 | 0.06450 | 254 |
| 2040 | 0.04136 | 291 |
| 2045 | 0.02714 | 317 |
| 2050 | 0.01385 | 332 |

The series is emissions over generation, so it is already on the source basis and the campaign's 0.91 delivery fraction
does not apply to it. That is the second half of the near-term fix: with a 2030 cap of 0.19673 rather than the authored
0.12, the base chain is no longer forced to out-decarbonise AEMO's own path in its first period, and with the pipeline pin
it no longer has the means to.

**confidence: high** on the schedule, which is read from the committed CSV; the derivation's own confidence is recorded in
[`../aemo_scenario_intensity/research.md`](../aemo_scenario_intensity/research.md).

## Plot

[`plot_near_term_pipeline.py`](plot_near_term_pipeline.py) draws the 2030 fleet by carrier as a stacked bar of existing,
committed, anticipated and policy-supported capacity, with the allowance stacked on top and AEMO's Step Change 2030
capacity marked beside it. It writes `near_term_pipeline.html` and `near_term_pipeline.png` beside itself.
