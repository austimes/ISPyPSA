# Build rate premium -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

Sources S001 to S004, S006, S008 and S009 were read first-hand: two capacity series in this repository, two published
PDFs whose text was extracted, three cache tables from the share, and two web pages that were fetched and read. S005 and
S007 carry no quote: both pages timed out on fetch, so each records only what a web search established.

## S001 -- AEMO draft 2026 ISP, Step Change CDP4 capacity series

**Source:** [`../../../iasr outputs/NEM-aemo2026draft-step_change-CDP4 (ODP)-capacity.csv`](../../../iasr%20outputs/)
in this repository.

No quote; this is a data table. Annual installed capacity in whole gigawatts from 2010 to 2050, one column per fuel:
`Demand Response`, `Coal`, `Bioenergy`, `Distillate`, `Gas`, `Hydro`, `Wind`, `Solar (Utility)` and `Solar (Rooftop)`.
The values used in `research.md` are the Step Change ODP path:

| Year | Wind | Solar (Utility) | Gas | Hydro | Coal |
| ---- | ---: | --------------: | --: | ----: | ---: |
| 2025 | 8 | 5 | 10 | 8 | 21 |
| 2030 | 26 | 32 | 12 | 7 | 13 |
| 2035 | 40 | 38 | 12 | 7 | 7 |
| 2040 | 54 | 50 | 13 | 7 | 5 |
| 2045 | 58 | 59 | 14 | 7 | 2 |
| 2050 | 57 | 63 | 15 | 7 | 0 |

Two properties of this file shape the whole topic. There is **no storage column**: neither battery nor pumped hydro
appears anywhere in the export, so no five-year storage addition can be read from it, which is why A008 and A009 are
authored. And the `Hydro` column is flat at 7 GW from 2026 to 2050 while the model's own 2030 network already carries 6.1
GW of pumped hydro storage, so `Hydro` here is conventional hydro and cannot stand in for the pumped hydro build rate
either.

## S002 -- AEMO draft 2026 ISP, Accelerated Transition CDP4 capacity series

**Source:**
[`../../../iasr outputs/NEM-aemo2026draft-accelerated_transition-CDP4 (ODP)-capacity.csv`](../../../iasr%20outputs/) in
this repository.

No quote; a data table with the same columns as S001.

| Year | Wind | Solar (Utility) | Gas |
| ---- | ---: | --------------: | --: |
| 2025 | 8 | 5 | 10 |
| 2030 | 36 | 33 | 12 |
| 2035 | 50 | 51 | 14 |
| 2040 | 70 | 98 | 15 |
| 2045 | 75 | 118 | 16 |
| 2050 | 84 | 135 | 16 |

This is the fastest build path AEMO publishes, which is what makes it the natural upper tranche boundary: past it, the
model is building faster than anything in AEMO's own scenario set.

## S003 -- Oxford Economics Australia, 2025 IASR planning and installation cost escalation factors

**Source:** *2025 IASR Planning and Installation Cost Escalation Factors: Report for AEMO*, Oxford Economics Australia,
February 2025, 55 pages,
<https://www.aemo.com.au/-/media/files/major-publications/isp/2025/stage-2/2025-iasr-planning-and-installation-cost-escalation-factors.pdf>.
Text extracted from the fetched PDF. This is the report AEMO commissioned to set the construction cost escalation inside
the 2026 ISP inputs, so it is the closest thing to an official Australian answer on build cost escalation.

The mining boom, which is the only Australian measurement of construction volume against construction cost at this scale,
verbatim from page 10 of the report:

> "The starkest example of demand driven cost escalation in the construction sector occurred over the second half of the
> 2000's, when the mining boom prompted a surge in mining, transport and utility related construction (both directly from
> investment in mining activities and indirectly from wider economic stimulation). A 50% rise in total construction from
> 2003 to 2009 coincided with a 22% increase in the Engineering Construction IPD as domestic supply chains were put under
> significant stress. In particular, strong demand for labour over this period led to construction wage growth greatly
> outpacing the national average and contributing significantly to rising engineering construction costs."

That the escalation did not unwind, verbatim from the same page:

> "Cost escalation began easing over the first half of the 2010s as the level of construction activity peaked and
> domestic supply chains adjusted. However, cost escalation never reversed even as construction activity eased back and
> the price levels of key materials and labour remain well above their 2000s levels."

The long historical trend, verbatim from the executive summary:

> "Real engineering construction costs have risen around 25% over the past 20 years (see Figure 1) while an average
> measure of real installation costs developed by OEA for this study has risen by 13% over the same period."

The forecast, verbatim from the same page:

> "Real installation costs are forecast to ease moderately over the next two years until FY26, before accelerating again
> toward FY30-31, when costs will be approximately 1-3% higher than FY24 levels. By FY45, real installation costs are
> expected to be around 10% higher than FY24 levels, consistent with long-run trends observed in the construction
> sector."

The explicit link from construction activity to escalation rate, verbatim from page 19 of the report:

> "With construction activity expected to peak around FY29 and FY30, real installation cost escalation rates across all
> asset types are expected to be at their greatest, ranging from 0.7% to 1.0% annually, with those assets which are more
> labour-intensive experiencing higher escalation rates."

The long-run rate the escalation settles back to, verbatim from the same page:

> "Long run installation cost escalation rates are forecast to range between 0.4% to 0.5% per annum across the asset
> types and is driven by the historical real wage increase of around 1% per annum for the construction sector (with
> labour costs accounting for around 40-50% of installation costs)."

Which technologies escalate slowest, verbatim from page 20 of the report:

> "Assets which are more modular and mechanised and consequently less labour intensive are expected to see lower
> escalation rates. These projects include onshore wind and large-scale PV."

This report also quotes Infrastructure Australia's 2024 Market Capacity Report, verbatim from page 11 of the report, with
its own page citation:

> "Infrastructure Australia's 2024 Market Capacity Report notes that 'for years, demand has been outweighing supply
> leading to cost increases and project timelines being delayed.'"

The footnote on that sentence reads "Infrastructure Australia (2024) Infrastructure Market Capacity 2024 Report, p4."

Two consequences for `research.md`. First, the secular escalation this report projects is small, about 10% over twenty
years on the installation share of capital cost, and it is already inside the build costs the model reads, so it cannot
be reused as a rate premium. Second, the mining boom paragraph is a genuine measurement of the thing curve 2 is trying to
price, and it is an average-cost measurement over a whole market, which is why `research.md` treats the transfer to a
marginal tranche as conservative and unsourced rather than exact.

## S004 -- CSIRO GenCost 2025-26 final report

**Source:** *GenCost 2025-26: Final report*, CSIRO, July 2026, 113 pages,
<https://www.csiro.au/-/media/Energy/GenCost-2025-26-Final/GenCost_2025-26_Final_Report_20260715.pdf>. Text extracted
from the fetched PDF. Section 2.1.1 is the only published Australian ladder of cost premiums for build the market
struggles to deliver.

The published brackets, verbatim from page 20 of the report:

> "EIA (2023) applies FOAK premiums of up to 25% to their technology costs. AACE (1991) recommends applying different
> levels of contingency based on the Technology Readiness Level ranging from 10% to up to 70%. In practice, we can find
> examples of projects that have cost around 100% more than planned such as the Vogtle large-scale nuclear plant in the
> US and the Snowy 2.0 pumped hydro project in Australia. Flyvbjerg and Gardner (2023) report that the global average
> cost overrun for nuclear, hydro, wind and solar are 120%, 75%, 13% and 1%, respectively."

The caveat that bounds how far this evidence can be pushed, verbatim from the same page:

> "Technologies that are currently being regularly deployed in Australia such as onshore wind, solar PV, batteries and
> gas generation are least likely to be impacted."

That sentence is why a3 is low confidence in `research.md`: GenCost's premiums are about technology novelty, and the
campaign's largest carriers are the ones GenCost says novelty does not touch.

How the ladder was built, and Table 2-1 itself, verbatim from page 21 of the report:

> "To develop the premium the value of 120% has been applied to large scale nuclear based on Flyvbjerg and Gardner
> (2023). The remaining premiums are based on observing the ratio between this large scale nuclear premium and its
> construction time and applying that ratio to the other technology's construction times. Effectively we are proposing
> that technologies that take longer to build will face higher FOAK premiums as they are more complex to plan. We then
> halve the premium for the second project and assume the third and subsequent projects are not impacted by a FOAK
> premium."

| Technology | Construction time (years) | First project | Second project |
| ---------- | ------------------------: | ------------: | -------------: |
| Gas with CCS | 2.0 | 42% | 21% |
| Black coal with CCS | 2.0 | 42% | 21% |
| Nuclear SMR | 4.4 | 92% | 46% |
| Nuclear large-scale | 5.8 | 120% | 60% |
| Solar thermal | 1.8 | 37% | 18% |
| Wind offshore | 3.0 | 63% | 31% |

What the premium stands for, verbatim from page 58 of the report:

> "In other words, there is an initial additional cost which must be paid to establish the required workforce, skills and
> supply chains when commencing a program of building technologies that Australia has not previously deployed."

Workforce, skills and supply chains are exactly what a build-rate premium prices, which is why this ladder is used to set
a3's range even though its subject is novelty rather than rate.

That the Oxford Economics escalation is already inside the published capital costs, verbatim from page 30 of the report:

> "The construction cost escalation factors estimated by Oxford Economics Australia are applied to the installation cost
> proportion of capital costs which is sourced from GHD (2026). Note that, this escalation factor is applied after
> learning."

## S005 -- Infrastructure Australia, 2025 Infrastructure Market Capacity Report

**Source:** <https://www.infrastructureaustralia.gov.au/reports/2025-infrastructure-market-capacity-report>.

No quote: the page timed out on fetch and was not read directly. What a web search established, recorded as reported
rather than as quoted text: the infrastructure industry is short about 141,000 workers against the five-year major public
infrastructure pipeline, with the shortfall reported to rise beyond 300,000 by mid-2027 as renewable energy projects ramp
up; utilities investment, chiefly energy transmission, is reported to more than double to about A$36 billion over five
years. No per-megawatt or percentage cost premium is attributed to the shortfall in any search result, so this source
establishes that a delivery ceiling exists and contributes no number to the adders. The 2024 edition of the same report
is quoted at second hand under S003.

## S006 -- Clean Energy Council, Clean Energy Australia 2026 report

**Source:** <https://cleanenergycouncil.org.au/news-resources/clean-energy-australia-report-2026>. Page fetched and read;
the underlying report PDF was not.

Verbatim from the page:

> "Just 2.3 GW of new renewable energy generation projects reached financial close in 2025, one of the lowest levels in a
> decade."

This is the benchmark the C1 widths are read against: Step Change asks for about 9 GW a year of new wind and utility
solar over 2026 to 2030, roughly four times the 2025 commitment rate, and the first tranche prices all of it at AEMO's
published cost.

## S007 -- DCCEEW Capacity Investment Scheme tenders

**Source:** <https://www.dcceew.gov.au/energy/renewable/capacity-investment-scheme> and its tender results pages.

No quote: every fetch of the department's pages timed out, so none was read directly. What a web search established,
recorded as reported: the scheme target was raised to 40 GW in July 2025; Tender 1 for NEM generation selected 19
projects totalling 6.4 GW; Tender 4 awarded 6.6 GW against a 6 GW target; and the dispatchable tender rounds are heavily
oversubscribed on bid volume, one round reportedly receiving 135 GWh of bids against a 16 GWh target. No clearing price
was found in any search result. The direction this evidence points is the one `research.md` uses it for and no further:
the pipeline of projects wanting to be built is not the binding constraint, so a build-rate premium prices delivery
capacity rather than project scarcity. No adder is derived from it.

## S008 -- IASR workbook cache: build costs, WACC and project life

**Source:** `build_costs.csv`, `wacc.csv` and `lead_time_and_project_life.csv` in the campaign input directory's
`workbook_cache_final/` folder on the share.

No quote; these are data tables. `build_costs.csv` carries capital cost in A$/kW per financial year from 2025-26 to
2053-54 for each technology and IASR scenario; the Step Change rows used here are sourced by the workbook to "CSIRO
GenCost 2025-26 Consultation Draft" under the "GenCost Global NZE post 2050" cost scenario. `wacc.csv` carries a
weighted average cost of capital per technology per scenario, in per cent. `lead_time_and_project_life.csv` carries
economic and technical life in years per technology. The five representative technologies drawn from them:

| Technology | Step Change WACC | Economic life | Capex 2029-30 | Capex 2049-50 |
| ---------- | ---------------: | ------------: | ------------: | ------------: |
| Wind | 7.5% | 25 y | 2,745 A$/kW | 2,131 A$/kW |
| Large scale Solar PV | 7.0% | 30 y | 989 A$/kW | 668 A$/kW |
| OCGT (large GT) | 9.0% | 25 y | 1,460 A$/kW | 1,102 A$/kW |
| Battery storage (4hrs storage) | 8.0% | 20 y | 1,208 A$/kW | 884 A$/kW |
| Pumped Hydro (24hrs storage) | 8.5% | 40 y | 4,032 A$/kW | 4,338 A$/kW |

The carrier groups themselves come from `new_entrants_summary.csv` in the same folder, whose `Fuel type` column takes
exactly six values: `Battery`, `Biomass`, `Gas`, `Solar`, `Water` and `Wind`. That column becomes the PyPSA carrier, so
it fixes the set of groups the premium can act on.

## S009 -- AEMO draft 2026 ISP capacity milestones as reported

**Source:** *Renewables on rise as AEMO lays out roadmap for energy transition*, pv magazine Australia, 10 December 2025,
<https://www.pv-magazine-australia.com/2025/12/10/renewables-on-rise-as-aemo-lays-out-roadmap-for-energy-transition/>.
Page fetched and read; the draft ISP itself was not read for this topic.

Verbatim from the article, reporting AEMO's draft optimal development path:

> "Wind would reach 26 GW by 2030, 40 GW by 2035, and 57 GW by 2050."

> "Grid-scale solar would reach 32 GW by 2030, 38 GW by 2035, and 63 GW by 2050."

> "33 GW of dispatchable, grid-scale battery and pumped-hydro energy storage would be needed by 2050, with 27 GW by
> 2030."

The first two sentences match the CDP4 capacity file in S001 exactly at all six milestones, which is what confirms the
repository's capacity series is the draft 2026 ISP Step Change ODP. The third is the only published storage milestone
available for this topic, and it is a combined battery and pumped hydro figure from secondary reporting, so the storage
widths in A008 and A009 are authored against it rather than read from it.
