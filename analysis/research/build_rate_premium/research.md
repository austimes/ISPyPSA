# Build rate premium on above-baseline new capacity

## Purpose and scope

The campaign charges every megawatt of new capacity at AEMO's published cost per megawatt, no matter how much is built in
one five-year period. That makes the build rate free: a period that builds four times AEMO's own optimal development path
(ODP) rate pays the same price per megawatt as a period that builds the ODP rate.

This topic sets the second of the campaign's two stepwise build cost curves. Curve 1, in
[`../social_licence_premium/`](../social_licence_premium/), prices cumulative capacity as build moves into worse
locations. Curve 2, here, prices the *instantaneous rate* of build inside one period, independent of where it goes.

Curve 2 answers a question the model cannot answer for itself: what does it cost when new build outruns the supply chain,
workforce and grid-connection capacity that can deliver it. That cost is not in any published per-megawatt input, because
every published input is a unit cost for a project delivered at a normal pace.

## What the campaign does

The premium is a three-tranche step function per carrier group per period, held in
[`../../model/data/build_rate_premiums_central.csv`](../../model/data/build_rate_premiums_central.csv) with columns
`group,tranche,financial_year,cap_mw,adder_$/mw/yr`. The model sums the new-build megawatts of each carrier group in the
period, fills the cheapest tranche first, and adds the tranche adders to the objective.

| Tranche                  | Cumulative width `cap_mw`                                       | Adder              | Meaning                                              |
| ------------------------ | --------------------------------------------------------------- | ------------------ | ---------------------------------------------------- |
| `step_change_rate`       | C1, the Step Change five-year addition                          | 0                  | Build at AEMO's own planned rate is priced as AEMO does |
| `accelerated_rate`       | C2, the Accelerated Transition five-year addition, or 2 x C1     | a2 = +17.5% of annuitised capex | Build between the two published rates    |
| `above_accelerated_rate` | blank, the uncapped backstop                                    | a3 = +45% of annuitised capex | Build past the fastest rate AEMO publishes |

Five carrier groups carry rows: `Wind`, `Solar`, `Gas`, `Battery` and `Water`. These are the `Fuel type` values of the
IASR new-entrant roster (`new_entrants_summary.csv`), which is where a PyPSA carrier name comes from, so the groups are
the carriers the model can actually add. Pumped hydro shares the carrier `Water` with conventional hydro; conventional
hydro has no new entrants, so every `Water` megawatt the premium charges is pumped hydro. `Biomass` is a sixth
new-entrant carrier and is deliberately left out, see A010.

**Each period sees only its own build.** The tranche block is rebuilt every period over the megawatts whose `build_year`
equals that period, so the premium prices compression where the compression happens. It cannot be dodged by building
earlier: an earlier period's build faces that period's own tranches, and nothing carries a credit forward. The premium
therefore reweights *how much* is built in a period against how much is built in other periods, rather than penalising a
cumulative total. The campaign's chained myopic solves reinforce this: a period does not see later periods, so it cannot
plan around a later tranche.

## Widths: what the published paths say a five-year build rate is

C1 and C2 are read from the draft 2026 ISP CDP4 capacity series in [`../../../iasr outputs/`](../../../iasr%20outputs/)
(S001, S002), differencing the annual gigawatt series five years apart. Period 2030 covers 2026-2030, so its addition is
capacity at 2030 minus capacity at 2025, and so on.

| Carrier | 2030 | 2035 | 2040 | 2045 | 2050 | Basis |
| ------- | ---: | ---: | ---: | ---: | ---: | ----- |
| Wind, Step Change | 18 | 14 | 14 | 4 | -1 | S001 |
| Wind, Accelerated Transition | 28 | 14 | 20 | 5 | 9 | S002 |
| Solar, Step Change | 27 | 6 | 12 | 9 | 4 | S001 |
| Solar, Accelerated Transition | 28 | 18 | 47 | 20 | 17 | S002 |
| Gas, Step Change | 2 | 0 | 1 | 1 | 1 | S001 |
| Gas, Accelerated Transition | 2 | 2 | 1 | 1 | 0 | S002 |

Net capacity, gigawatts. The series is net of retirement, so late-period additions understate gross build: Step Change
wind falls 1 GW between 2045 and 2050 because early wind farms reach end of life, not because nothing is built. Two
corrections follow from that, A002 and A003, and the widths the model uses are:

| Carrier | Tranche | 2030 | 2035 | 2040 | 2045 | 2050 |
| ------- | ------- | ---: | ---: | ---: | ---: | ---: |
| Wind | C1 | 18,000 | 14,000 | 14,000 | 9,800 | 9,800 |
| Wind | C2 | 36,000 | 28,000 | 28,000 | 19,600 | 19,600 |
| Solar | C1 | 27,000 | 11,600 | 12,000 | 11,600 | 11,600 |
| Solar | C2 | 54,000 | 23,200 | 47,000 | 23,200 | 23,200 |
| Gas | C1 | 2,000 | 1,000 | 1,000 | 1,000 | 1,000 |
| Gas | C2 | 4,000 | 2,000 | 2,000 | 2,000 | 2,000 |
| Battery | C1 | 6,000 | 6,000 | 6,000 | 6,000 | 6,000 |
| Battery | C2 | 12,000 | 12,000 | 12,000 | 12,000 | 12,000 |
| Water | C1 | 3,000 | 3,000 | 3,000 | 3,000 | 3,000 |
| Water | C2 | 6,000 | 6,000 | 6,000 | 6,000 | 6,000 |

Megawatts per five-year period, cumulative. Wind, Solar and Gas are S001 and S002 under A002 and A003; Battery and Water
are authored, A008 and A009, because the CDP4 export carries no storage series at all.

The near-term widths are large against what the industry is currently delivering. Step Change wants 18 GW of wind and 27
GW of utility solar between 2026 and 2030, or about 9 GW a year of new variable renewable energy (VRE), while the Clean
Energy Council records "Just 2.3 GW of new renewable energy generation projects reached financial close in 2025, one of
the lowest levels in a decade" (S006). C1 is therefore not a soft target the model will clear casually; it is roughly
four times the recent commitment rate, and the first tranche already prices that at AEMO's own cost.

**confidence: high** for Wind, Solar and Gas C1 and C2, which are arithmetic on the published CDP4 series, cross-checked
against AEMO's own summary of the same path (S009: wind 26 GW by 2030, 40 GW by 2035, 57 GW by 2050; grid-scale solar 32
GW, 38 GW, 63 GW, matching the file exactly). **confidence: low** for Battery and Water.

## Adders: what escalation the evidence supports

### The evidence, and what each piece can and cannot carry

| # | Source | Finding | Number | What it bears on |
| - | ------ | ------- | ------ | ---------------- |
| S003 | Oxford Economics Australia for AEMO | Mining boom: construction volume against real construction cost | +50% volume 2003-2009 with +22% real engineering construction cost | The only Australian measurement of what a build-rate surge did to cost |
| S003 | Same | Peak-cycle real installation cost escalation, FY29-FY30 | 0.7% to 1.0% a year, against 0.4% to 0.5% long run | Market-wide secular escalation, already inside AEMO's cost trajectory |
| S003 | Same | Whole-horizon real installation cost rise | about +10% by FY45 against FY24 | Secular, small, and not a rate premium |
| S004 | CSIRO GenCost 2025-26 | United States Energy Information Administration first-of-a-kind (FOAK) premiums | up to 25% | Upper bound on a modest delivery premium |
| S004 | Same | AACE contingency by technology readiness | 10% to 70% | Full width of engineering practice |
| S004 | Same | Global average cost overrun, Flyvbjerg and Gardner | wind 13%, solar 1%, hydro 75%, nuclear 120% | What over-runs look like for the campaign's own technologies |
| S004 | Same | GenCost's own suggested FOAK premiums, first project | solar thermal 37%, gas or coal with carbon capture 42%, offshore wind 63% | A costed ladder in the right units, halved for the second project |
| S005 | Infrastructure Australia | Workforce shortfall against the public infrastructure pipeline | reported as 141,000 now, rising past 300,000 by mid-2027 | Why a delivery ceiling exists at all; no cost conversion published |
| S006 | Clean Energy Council | Financial close for new large-scale renewable generation in 2025 | 2.3 GW | Where the industry's delivery rate actually sits |
| S007 | DCCEEW Capacity Investment Scheme | Tenders heavily oversubscribed on bid volume | reported 135 GWh of bids against a 16 GWh dispatchable target | Project supply is not the binding constraint; delivery is |

Two of those readings deserve to be separated, because they pull in opposite directions.

The secular escalation evidence is small. Oxford Economics, commissioned by AEMO for exactly this purpose, projects real
installation costs only about 10% above FY24 by FY45, with escalation peaking at 0.7% to 1.0% a year around FY29-FY30
when construction activity peaks. That is a market-wide index on the installation share of capital cost, and AEMO already
applies it inside the build costs the model reads. It cannot be double-counted as a rate premium, and it is far too small
to be one.

The surge evidence is larger and closer to the question. The same report's account of the mining boom is a direct
measurement of what happens when construction volume outruns delivery capacity: "A 50% rise in total construction from
2003 to 2009 coincided with a 22% increase in the Engineering Construction IPD as domestic supply chains were put under
significant stress." That is an elasticity of about 0.44 percentage points of real cost per percentage point of extra
volume, measured on the whole market's average cost.

### The two rungs

| Rung | Applies to | Range from the evidence | Chosen | Derivation of the midpoint |
| ---- | ---------- | ----------------------- | -----: | -------------------------- |
| a2 | Build between C1 and C2 | +10% to +25% | +17.5% | Midpoint of the range. The S003 elasticity gives 0.44 x 50% = +22% at the mid-point of a tranche spanning 0 to 100% above C1; Flyvbjerg's 13% wind over-run sets the floor; the EIA's 25% FOAK premium and AACE's 10% contingency floor bracket it |
| a3 | Build above C2 | +30% to +60% | +45% | Midpoint of the range. GenCost's own FOAK ladder for technologies Australia struggles to deliver runs 37% to 63%; AACE allows up to 70%; the same +60% ceiling that curve 1 uses for the densest land is the top |

Both rungs are charged as an absolute A$/MW/yr adder rather than a percentage, because the linopy tranche block needs a
constant coefficient. The percentage is converted per carrier group and per period against the annuitised capital cost of
that group's representative new-entrant technology, so the *relative* signal is what the table above says and the
absolute number tracks AEMO's own falling capital costs.

### Annuitising

`annuity = capex x wacc / (1 - (1 + wacc)^-life)`, with capex from `build_costs.csv`, the WACC from `wacc.csv` and the
economic life from `lead_time_and_project_life.csv` in the workbook cache (S008), all on the Step Change column.

| Carrier | Representative technology | WACC | Economic life | Capex 2029-30 | Annuity 2029-30 | Annuity 2049-50 |
| ------- | ------------------------- | ---: | ------------: | ------------: | --------------: | --------------: |
| Wind | Wind | 7.5% | 25 y | 2,745 A$/kW | 246,256 A$/MW/yr | 191,173 A$/MW/yr |
| Solar | Large scale Solar PV | 7.0% | 30 y | 989 A$/kW | 79,700 A$/MW/yr | 53,832 A$/MW/yr |
| Gas | OCGT (large GT) | 9.0% | 25 y | 1,460 A$/kW | 148,637 A$/MW/yr | 112,190 A$/MW/yr |
| Battery | Battery storage (4hrs storage) | 8.0% | 20 y | 1,208 A$/kW | 123,037 A$/MW/yr | 90,037 A$/MW/yr |
| Water | Pumped Hydro (24hrs storage) | 8.5% | 40 y | 4,032 A$/kW | 356,356 A$/MW/yr | 383,401 A$/MW/yr |

The wind annuity is confirmed against the model itself: the templated 2030 network gives new-entrant onshore wind
`capital_cost` of 261,124 to 354,269 A$/MW/yr, which is this 246,256 plus connection cost and fixed operating cost, so
the basis used here is the same basis the objective already carries.

### The adders the model uses

| Carrier | a2 2030 | a3 2030 | a2 2050 | a3 2050 |
| ------- | ------: | ------: | ------: | ------: |
| Wind | 43,095 | 110,815 | 33,455 | 86,028 |
| Solar | 13,947 | 35,865 | 9,421 | 24,224 |
| Gas | 26,011 | 66,887 | 19,633 | 50,486 |
| Battery | 21,532 | 55,367 | 15,757 | 40,517 |
| Water | 62,362 | 160,360 | 67,095 | 172,531 |

A$/MW/yr, 2025 dollars, full table in
[`../../model/data/build_rate_premiums_central.csv`](../../model/data/build_rate_premiums_central.csv).

**confidence: medium** on a2. Its range is bracketed by three independent published readings in the right units, and its
midpoint sits within a percentage point of the mining boom elasticity applied to the tranche. What is unsourced is the
transfer itself: S003 measured an average cost movement across a whole market over six years, and the model charges it as
a marginal cost on one tranche in one period. A marginal cost should exceed an average one, so the transfer is
conservative, but nothing published fixes by how much.

**confidence: low** on a3. Every number in its range describes a *technology* Australia has not built before, not a
*rate* of building a technology it builds routinely. Nothing published prices megawatts of onshore wind delivered at
twice the ODP rate. The 30% to 60% band is chosen so the outer rung sits inside the width of published engineering
contingency and matches the outer rung of curve 1, not because a source measured it.

## What this does not model

| Not modelled | Why, and what it means for a result |
| ------------ | ----------------------------------- |
| Any physical ceiling on build rate | There is no hard cap, only a rising price. A cell that needs 60 GW of wind in one period can still have it, at a price. Reading a result therefore means reading the tranche usage, not only the total |
| Lead times | The premium prices a rate; it does not stop a plant appearing sooner than its lead time allows. IASR total lead times still gate the new-entrant menu, and the two mechanisms are independent |
| Transmission and connection build rate | Curve 2 covers generation and storage only. Corridor and REZ transmission rates are priced by curve 1's tranches on published headroom, which is a cumulative limit, not a rate |
| Learning from a fast build | A period that builds fast may lower the next period's cost. The premium is one-directional, so it overstates the cost of a sustained fast path against a single fast period |
| Retirement-driven replacement | The C1 widths are net of retirement, corrected only by the horizon-average floor in A002 |

## Plot

[`plot_build_rate_premium.py`](plot_build_rate_premium.py) draws the step function the model reads straight from
`build_rate_premiums_central.csv`: one panel per carrier group, cumulative megawatts of new build in the period against
the adder in A$/MW/yr, one line per period. It writes `build_rate_premium.html` and `build_rate_premium.png` beside
itself.
