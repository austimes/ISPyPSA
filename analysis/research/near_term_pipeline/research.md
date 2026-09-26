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
| `--pipeline-period 2030` | 2030 | Turns the pin on for every solve year at or before 2030, so 2026 and 2030 |
| New-entrant generation allowance, 2026 | 0 MW, A008 | FY2026 is complete; everything built in it is on the existing and committed roster |
| New-entrant storage allowance, 2026 | 0 MW, A008 | As above |
| New-entrant generation allowance, 2030 | 20,500 MW, A011 | One NEM-wide cap over every `New Entrant` generator in the 2030 solve |
| New-entrant storage allowance, 2030 | 5,100 MW, A011 | One NEM-wide cap over every `New Entrant` battery in the 2030 solve |
| Build above the 2030 allowance | Rush charge, [`../pre2030_rush_charge/`](../pre2030_rush_charge/) | Priced rather than forbidden, up to a hard ceiling |
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

## The draft-ISP 2030 allowance

This section is a history-free record of the yardstick used while only the draft 2026 ISP was available. It is not the
campaign's setting; the setting the campaign uses is derived against the final 2026 ISP, in
[The allowance against the final 2026 ISP](#the-allowance-against-the-final-2026-isp).

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

**On the roster above, the draft-ISP derivation gives 19,000 MW of generation and 6,000 MW of storage.** The storage
figure, and eventually the generation figure, fall on the corrected roster, see
[The allowance on the corrected pipeline](#the-allowance-on-the-corrected-pipeline); neither is the campaign's setting,
which is derived against the final 2026 ISP instead. The form of the cap is one NEM-wide megawatt limit over
new-entrant generators, and a second over new-entrant batteries. Generation and storage are capped separately because
they are separate supply chains, and because the custom-constraints framework sums one component type per constraint
in any case.

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

A second gap found while counting them is larger. Ten committed batteries totalling 2,070 MW, and 29 anticipated
batteries, are in the workbook's maximum-capacity sheet but never reached the model. The workbook is consistent: ISPyPSA's
parser configuration stopped reading the summary sheet at row 648, while the final workbook's data ends at row 732. The
parser fix and its effect on the allowance are described under
[The allowance on the corrected pipeline](#the-allowance-on-the-corrected-pipeline).

**confidence: high.** The 29 rows and the 6,739 MW are counted from the templated file, the workbook dates are read from
the cache table, and the missing projects were checked against both workbook sheets by name.

## The 2026 allowance

The 2026 period is the 2025-26 financial year, which has already ended. Every project that generated in it is either
existing or committed with a workbook commissioning date inside it, so the model holds it as fixed capacity. Nothing the
optimiser adds can have been built in it. Against AEMO's own Step Change 2026 capacity (S001), the roster with those dated
projects already exceeds the path in every buildable carrier:

| Carrier | Step Change 2026 (S001) | Roster at FY2026, existing plus dated pipeline (S002) | Gap |
| ------- | ----------------------: | ----------------------------------------------------: | --: |
| Wind | 11 | 14.3 | -3.3 |
| Solar, utility | 9 | 14.1 | -5.1 |
| Gas | 11 | 11.3 | -0.3 |
| Battery | no series | 8.6 | - |

Gigawatts. The roster column sums the maximum-capacity sheet's existing rows and every other row whose commissioning
date, or indicative date where no firm one is given, falls on or before 30 June 2026. CDP4 solar sits well below the
workbook's existing fleet in its early years (5 GW at 2025 against 10.9 GW existing), so the solar gap is partly a
definitional difference, but no reading of it leaves room for new build.

**The 2026 allowance is 0 MW for generation and 0 MW for storage** (A008). The 2026 base is a calibration year: its job is
to reproduce what the fleet did, not to choose new plant.

**confidence: high.** FY2026 is history, and the roster totals are sums over the workbook sheet.

## The allowance on the corrected pipeline

Three roster faults found while counting the storage pipeline are fixed in the model builder, and each moves the 2030
allowance.

| Fault | Fix | Effect on the roster |
| ----- | --- | -------------------- |
| The ISPyPSA parser read the IASR summary sheet only to row 648, while the final workbook's data runs to row 732 | Parser configuration end row corrected | 10 committed and 29 anticipated batteries enter: batteries active in 2030 rise from 14.594 GW (88 units) to 24.280 GW (120 units). 25 wind and solar generators are restored too, but stay out of the solve until their traces are parsed |
| Committed commissioning dates were dropped in templating | Dates carried through | The 2026 solve holds 8.602 GW of batteries (53 units), not 11.028 GW |
| The battery templater in `src/ispypsa/templater/storage.py` kept only the 2024 IASR label "Additional projects", while the 2026 workbook writes "Additional policy-supported project" | Both labels kept | The 29 policy-supported batteries enter: 8.05 GW, 7.56 GW of it dated on or before FY2030 |

Storage at 2030, gigawatts:

| Roster | Batteries | Pumped hydro | Total | Against the 27 GW milestone (S004) |
| ------ | --------: | -----------: | ----: | ---------------------------------: |
| Before the fixes | 14.594 | 6.075 | 20.7 | 6.3 of room |
| With the parser and date fixes | 24.280 | 6.075 | 30.4 | 3.4 over |
| With all three fixes | 31.8 | 6.075 | 37.9 | 10.9 over |

**On this draft-ISP reading, the 2030 storage allowance is 0 MW** (A009); this is not the campaign's setting, see
[The allowance against the final 2026 ISP](#the-allowance-against-the-final-2026-isp). The corrected pipeline already
holds more storage than AEMO's draft path wanted by 2030. It still does when pumped hydro counts only where its
commissioning date falls by FY2030 (3.3 GW, total 27.5 GW). The 6 GW figure derived above is the gap to a roster
missing 9.7 GW of committed and anticipated batteries.

Generation at 2030, gigawatts, once the 25 restored generators have traces (A010):

| Carrier | Step Change 2030 (S001) | Roster before | Restored, dated by FY2030 | Roster after | Allowance |
| ------- | ----------------------: | ------------: | ------------------------: | -----------: | --------: |
| Wind | 26 | 20.107 | 1.192 | 21.299 | 4.7 |
| Solar, utility | 32 | 19.600 | 4.893 | 24.493 | 7.5 |
| Gas | 12 | 11.394 | - | 11.394 | 0.6 |
| **Total** | | | | | **12.8** |

The restored rows are the 20 solar and 5 wind projects whose summary-sheet rows lie below row 648, where the faulty
parser configuration stopped reading; Hexham Wind Farm (720.8 MW) is left out because it commissions in FY2031. **On
this draft-ISP reading, the 2030 generation allowance is 19,000 MW while those generators stay out of the solve, and
13,000 MW once they are in.** Neither figure is the campaign's setting, see
[The allowance against the final 2026 ISP](#the-allowance-against-the-final-2026-isp). The allowance stands in for
missing pipeline, so on this reading it should shrink only when the pipeline actually enters.

**confidence: low** on the draft-ISP storage allowance. It is zero on every roster reading, but it still rests on a
secondary report of a draft-ISP milestone. **confidence: medium** on the draft-ISP 13,000 MW figure, which depends on
the restored generators' dates and on matching their names across the two workbook sheets.

## The allowance against the final 2026 ISP

The final 2026 ISP replaces the draft-ISP CDP4 series used above. The campaign's 2030 new-entrant allowance is measured
against the final ISP directly, using the same roster cut the cost-gap decomposition in
[`../aemo_scenario_cost/`](../aemo_scenario_cost/#capital-scope) already reports.

AEMO's final 2026 ISP Step Change optimal development path reaches, by 1 July 2029 (the model's 2030 period is the
2029-30 financial year), 29.8 GW of wind, 31.2 GW of utility solar and 33.3 GW of grid-scale batteries, its medium and
shallow storage (S006). The IASR roster of existing, committed, anticipated and additional policy-supported projects
commissioned by that date already holds 17.6 GW of wind, 22.9 GW of solar and 28.2 GW of batteries (S007). The
remainder is genuinely new-entrant capacity:

| Carrier | Final 2026 ISP, 1 July 2029 (GW) | IASR roster by 1 July 2029 (GW) | New-entrant allowance (GW) |
| ------- | --------------------------------: | -------------------------------: | --------------------------: |
| Wind | 29.8 | 17.6 | 12.2 |
| Solar, utility | 31.2 | 22.9 | 8.3 |
| **Generation total** | | | **20.5** |
| Batteries | 33.3 | 28.2 | **5.1** |

**The 2030 settings are 20,500 MW of generation and 5,100 MW of storage** (A011), with hard ceilings of twice each
allowance: 41,000 MW of generation and 10,200 MW of storage
([`../pre2030_rush_charge/`](../pre2030_rush_charge/)). These figures are the campaign's setting; the draft-ISP
readings above (19,000 MW / 6,000 MW, and the corrected-pipeline reading of 13,000 MW / 0 MW) are not.

**confidence: high** on the final ISP capacity figures, read from the ISP's own chart data workbook. **confidence:
medium** on the roster totals, which depend on filtering the IASR roster to a single commissioning-date cutoff.

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

[`plot_near_term_pipeline.py`](plot_near_term_pipeline.py) draws the 2030 fleet by carrier as a stacked bar of existing plant and pipeline, with
the allowance stacked on top and the target capacity marked beside it. Wind, utility solar and batteries are stacked to the IASR roster
commissioned by 1 July 2029 and marked against the final 2026 ISP; gas, coal and conventional hydro are still stacked to the corrected model
roster and marked against the draft-ISP CDP4 series. It writes `near_term_pipeline.html` and `near_term_pipeline.png` beside itself.
