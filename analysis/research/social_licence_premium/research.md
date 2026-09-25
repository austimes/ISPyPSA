# Social licence premium on relaxed REZ and corridor capacity

## Purpose and scope

The campaign relaxes AEMO's published renewable energy zone (REZ) and transmission corridor ceilings and needs the
relaxed capacity to cost more than the capacity AEMO planned for. Left alone it does not: the published per-megawatt
expansion price applies at every megawatt, and AEMO's own escape valve for building past a REZ resource limit is an
unbounded generator at a flat penalty. A run held to four times the published limit therefore buys the extra headroom at
close to the same price as the headroom inside it.

This topic assembles the citable evidence for what that extra headroom should cost, and sets the premium the campaign
charges. It is curve 1 of the campaign's two build cost curves: cumulative capacity, rising as build moves into worse and
more contested locations. Curve 2, the instantaneous build rate, is in
[`../build_rate_premium/`](../build_rate_premium/) and is independent of this one.

The premium belongs on the per-megawatt price, not on the megawatt ceiling, because published expansion prices span two
orders of magnitude (21,485 A$/MW at Darling Downs to 1,674,664 A$/MW at NQ1, from
[`../rez_transmission_limits/research.md`](../rez_transmission_limits/research.md)). A flat A$/MW adder would be a
rounding error on one option and a doubling on another, so every tranche below is a percentage of the option's own price.

## What the campaign does

Three mechanisms, all applied to components the model already creates.

### Curve 1a, REZ generation above the published resource limit

Every soft REZ resource limit carries a dummy "relax" generator that lets the model build past the limit at AEMO's
published violation penalty. In the 2030 network of the reference run there are 135 of them, three per REZ: high-quality
wind, medium-quality wind and solar (S014). The penalty is 0.3 A$M/MW inside every REZ (S006), and the translator
annuitises it at the regulated transmission weighted average cost of capital (WACC) of 3.0% over 30 years, so the price
the model actually sees is **A$15,305.78/MW/yr** for unlimited megawatts.

The campaign replaces each unbounded relax generator with two bounded tranches:

| Tranche | Width | Price per MW per year |
| ------- | ----- | --------------------- |
| `_relax1_` | 1x the published resource limit | penalty + 15% of that REZ's median new-entrant variable renewable energy (VRE) annuitised cost |
| `_relax2_` | a further 2x the published limit | penalty + 60% of the same |
| nothing above | - | the REZ's land-use limits, scaled by the run factor, are the hard ceiling |

`rez_limits.py` stops scaling the soft resource limits, so the tranche widths stay at AEMO's published megawatts, and
keeps scaling only the hard land-use limits, the group constraint right-hand sides and the transmission headroom. At the
campaign's factor of 4 that makes the land-use limit the 4x ceiling this topic's outer rung was always written against.

What those percentages are worth, from the 2030 network (S014). The per-REZ median annuitised cost of a new-entrant
onshore wind or large-scale solar candidate runs from 261,124 to 354,269 A$/MW/yr across the 39 REZs that have
candidates, with a median of 301,823:

| Step | Price per MW per year | As a share of the REZ's own new-entrant VRE cost |
| ---- | --------------------: | ----------------------------------------------: |
| AEMO penalty alone, as the model charges it today | 15,306 | 5.1% |
| Tranche 1, penalty + 15% | 60,579 | 20.1% |
| Tranche 2, penalty + 60% | 196,400 | 65.1% |

Median REZ, A$2025. The first row corrects a figure that has circulated in this campaign's own design notes: the AEMO
penalty is **about 5% of a new-entrant wind or solar project's annuitised cost, not about 22%**. The 22% came from
dividing the penalty by a median taken across every wind row in the network, most of which are existing plant carrying
fixed operating cost only and no capital cost at all. On the correct denominator the unbounded penalty is a weak signal,
which is the case for replacing it with tranches rather than simply raising it.

### Curve 1b, REZ and corridor transmission above published headroom

Every expandable link `<isp_name>_exp_<t>` gets the same three-step shape on its own annuitised capital cost, with the
width H being that link's published headroom, `additional_network_capacity_mw` divided by the run's relaxation factor.

| Tranche | Width | Adder on the link's own annuitised cost |
| ------- | ----- | --------------------------------------: |
| 1 | H | +0% |
| 2 | H | +15% |
| 3 | to the 4H ceiling | +60% |

No fourth tranche is needed: each link's untouched `<isp_name>_expansion_limit` constraint already stops it at 4H.

The 2030 network carries 38 expandable links, 28 REZ and 10 corridor, with median published headroom of about 975 MW per
REZ option and 900 MW per corridor option (S014). Their annuitised costs and the adders those percentages imply:

| | REZ links | Corridor links |
| --- | ---: | ---: |
| Annuitised cost, median | 35,689 A$/MW/yr | 18,781 A$/MW/yr |
| Annuitised cost, range | 535 to 193,121 | 3,676 to 84,255 |
| Tranche 2 adder, median link | +5,353 A$/MW/yr | +2,817 A$/MW/yr |
| Tranche 3 adder, median link | +21,413 A$/MW/yr | +11,269 A$/MW/yr |

### Landholder payments, as a flat per-megawatt adder by state

Separately from the tranches, every expansion link carries a flat adder for the legislated landholder payment scheme of
the state it sits in. This is a real cost of building transmission that AEMO carries as a cost category in its own
cost-benefit analysis, and it applies to the first megawatt as much as the last, so it is not a tranche.

**Both schemes are totals, not annual rates**, which is the question A012 settles. The NSW Strategic Benefit Payments
Scheme pays A$200,000 per kilometre in real 2022 dollars, "paid out in annual instalments over 20 years" (S003, S004).
The reported Victorian scheme pays the same A$200,000 per kilometre, delivered as A$8,000 per kilometre per year over 25
years (S005). The Victorian A$8,000 is an instalment of the same A$200,000 total, not an additional annual rate; charging
it as a perpetual annual payment would overcharge Victorian links by about five times against NSW ones. Queensland's
A$230,000 per kilometre is a lump sum (S003).

Each total is converted with the capacity-weighted easement length of the option type (A005) and annuitised on the same
3.0% over 30 years basis as the links themselves:

| State | Scheme total | REZ link adder | Corridor link adder | Share of a capacity-weighted link cost |
| ----- | -----------: | -------------: | ------------------: | -------------------------------------: |
| New South Wales | A$200,000/km | +1,524 A$/MW/yr | +1,144 A$/MW/yr | 2.78% REZ, 1.95% corridor |
| Victoria | A$200,000/km | +1,524 A$/MW/yr | +1,144 A$/MW/yr | same |
| Queensland | A$230,000/km | +1,753 A$/MW/yr | +1,315 A$/MW/yr | 3.20% REZ, 2.24% corridor |
| South Australia | none found | 0 | 0 | - |
| Tasmania | unfinalised, no figure published | 0 | 0 | - |

One row spelled out: A$200,000/km x 0.1494 km/MW = A$29,880/MW, annuitised at 3.0% over 30 years (a factor of 0.051020) =
A$1,524/MW/yr.

## Why AEMO's limits are what they are

AEMO's published REZ ceilings are land, resource and network limits, not a priced social-licence constraint. Three facts
from sources S001, S002 and S007 fix this:

| Ceiling | What sets it | Social licence content |
| ------- | ------------ | ---------------------- |
| REZ resource limits | Existing land use, environmental and cultural constraints, wind and solar quality, and land needed per megawatt | Embedded in the land-use complexity screen, but not priced separately |
| REZ land-use limits | 5% of REZ land area for onshore wind and 1% for solar, at 0.24 km2/MW wind and 0.02 km2/MW solar | None priced; the Accelerated Transition scenario raises the same limits to 25% and 5% |
| REZ and corridor transmission limits | Thermal and stability ratings, and joint planning advice from the network businesses | Easement lengths are drawn to avoid the most complex land, lengthening some early routes by up to 20% |

The Accelerated Transition land-use limits are exactly 5.0x the other scenarios' on every REZ row of the workbook. AEMO
therefore already brackets the campaign's 1x-to-4x range with its own scenario ladder, and prices the relaxed land at the
same cost as the unrelaxed land. The campaign's free relaxation is not an outlier; it inherits a gap that sits in the
published inputs.

## Findings

Every number below is either read from the 2026 IASR workbook cache and workbook on the share, or quoted from a document
whose text was extracted and read. Conversions to A$/MW use AEMO's own easement lengths and capacities, derived in the
next section. The final column converts each figure into a premium on REZ transmission expansion capacity; the corridor
equivalent is in the derivation table.

| # | Source | What it prices | Number and year dollars | Scope | As a premium on REZ expansion capacity | Confidence |
| - | ------ | -------------- | ----------------------- | ----- | -------------------------------------- | ---------- |
| S001 | AEMO 2024 ISP Appendix 8 | Transmission project capex uplift for low social licence | +15% (approximate) | All transmission augmentation options except committed and anticipated, plus pumped hydro | +15%, or +A$161,300/MW at the capacity-weighted REZ price | high |
| S001 | AEMO 2024 ISP Appendix 8 | Transmission lead-time delay for low social licence | +2 years | Same scope | Not a per-megawatt cost | high |
| S001 | AEMO 2024 ISP Appendix 8 | REZ generation capex uplift, graduated by private land parcel density | +5% to +60% | Onshore wind and solar build cost inside a REZ | +60% at the densest REZ, or +A$645,200/MW, if transferred to transmission | high for the number, low for the transfer |
| S001 | AEMO 2024 ISP Appendix 8 | Net market benefit lost to the whole sensitivity | about A$4 billion | Optimal development path | Not per megawatt | high |
| S001 | AEMO 2024 ISP Appendix 8 | Extreme case: no new renewable transmission or generation developed | +A$18.5 billion to consumers | Whole NEM | Not per megawatt; an upper bound on the whole question | high |
| S002 | AEMO Draft 2026 ISP Appendix A8 | Route lengthening to avoid complex land | up to +20% on straight-line route length | Early transmission options | Up to +20% on line capex, already inside published IASR costs | high for the quote, medium for the cost proportionality |
| S002 | AEMO Draft 2026 ISP Appendix A8 | Community engagement time inside the Transmission Cost Database | No isolated figure published | All conceptual ISP transmission options | Already inside published IASR costs | high |
| S003, S004 | 2026 IASR workbook and EnergyCo | NSW Strategic Benefit Payments to transmission hosts | A$200,000/km, real 2022, annual instalments over 20 years, CPI-indexed | New high-voltage transmission on private land, named NSW projects | +A$29,880/MW, or +2.8% | high |
| S003 | 2026 IASR workbook | Queensland Powerlink SuperGrid landholder payments | A$230,000/km, 2023 dollars, lump sum | New Queensland transmission | +A$34,360/MW, or +3.2% | high |
| S003 | 2026 IASR workbook | Tasmanian TasNetworks strategic benefit payments | No figure; scheme unfinalised and no cost carried | North West Transmission Developments | None | high, as an absence |
| S005 | Victorian landholder payment announcements | VicGrid transmission host payments and neighbour payments | A$200,000/km as A$8,000/km/year over 25 years; neighbours up to A$40,000 lump sum | Victorian transmission projects and REZ links | +A$29,880/MW, or +2.8%, on the same arithmetic as NSW | medium; secondary reporting only |
| S006 | 2026 IASR workbook | REZ resource limit violation penalty factor | A$0.3M/MW inside every REZ; A$1.0M/MW outside REZs | Building past a REZ resource limit | +27.9% in-REZ, +93.0% non-REZ | high for the value, medium as a cost estimate |
| S007 | 2026 IASR workbook | Land-use share of REZ land available to wind and solar | 5% and 1%, rising to 25% and 5% in Accelerated Transition | Every onshore REZ | No premium attached to the 5x relaxation | high |
| S008 | Tasmanian community benefit guideline | Community benefit sharing budget per installed megawatt | Wind A$800-1,800/MW/year; solar A$150-800/MW/year, 2024 dollars | Generation projects, explicitly excluding host landowner payments | Wind A$8,900-20,100/MW present value; not a transmission cost | high |
| S009 | Nexa Advisory | Consumer bill cost of transmission delay | NSW household +A$1,092 over 20 years for a 3-year delay; +A$3,984 for 7 years | Corridor and interconnector delay, NEM-wide | Not a capex premium | medium; not read first-hand |
| S010 | AER and Deloitte social licence cost work | Framework for recovering social licence expenditure | No A$/km, A$/MW or percentage published | Regulated transmission | None available | medium, as an absence |
| S011 | CSIRO GenCost | Generation capital cost benchmarks | No social licence or community benefit line item found | New-build generation | None | medium, as an absence |
| S012 | Clean Energy Council | Proposed Renewable Resources Payment to host councils | A per-megawatt-hour charge, rate not set | Renewable generation | None available | low |
| S014 | Templated 2030 network | What the model actually charges and what a candidate actually costs | Penalty 15,306 A$/MW/yr; new-entrant VRE 261,124 to 354,269 A$/MW/yr; expansion links 535 to 193,121 A$/MW/yr | The reference run's 2030 solve | The denominators every percentage above is applied to | high |

Three gaps are genuine rather than unsearched. No published source prices capacity **beyond** a REZ or corridor limit; no
peer-reviewed Australian study estimates a social-licence cost premium in dollars; and no source converts the landholder
payment schemes into a percentage of transmission capital cost. The derivation below does that last conversion from
AEMO's own inputs rather than citing it.

## Derivation

### Kilometres per megawatt, from AEMO's own augmentation options

Every REZ and flow-path augmentation option in the IASR carries both an easement length in kilometres and the capacity it
adds in megawatts, so a per-kilometre payment converts to a per-megawatt premium without any assumption about line
ratings. The ratio is computed over every option with a positive capacity, easement length and cost, from
`rez_augmentation_options_*.csv` and `flow_path_augmentation_options_*.csv` in the workbook cache.

| Statistic | REZ options (65) | Flow-path options (33) |
| --------- | ---------------: | ---------------------: |
| Capacity-weighted easement length | 0.1494 km/MW | 0.1121 km/MW |
| Median easement length | 0.1400 km/MW | 0.0912 km/MW |
| Capacity-weighted expansion cost | A$1,075,349/MW | A$1,150,983/MW |
| NSW payment scheme as a share of expansion cost, capacity-weighted | 2.78% | 1.95% |
| Same share, median option | 2.81% | 1.93% |
| Same share, range across options | 0.17% to 9.65% | 0.69% to 3.84% |

The arithmetic for one row of the findings table, spelled out: A$200,000/km x 0.1494 km/MW = A$29,880/MW, which against a
capacity-weighted REZ expansion cost of A$1,075,349/MW is 2.78%. The Queensland rate substitutes A$230,000/km for the
same easement length.

The conclusion that matters: the landholder payment schemes already in place account for about 2% to 3% of transmission
expansion capital cost. They are real, they are legislated, and they are far too small on their own to price a doubling
of a REZ ceiling. A social-licence premium large enough to change a capacity-expansion result has to stand for scope
change, route change and delay, not for payments to hosts. That is why they enter as a flat adder and the tranches are
set from the sensitivity evidence instead.

### The two rungs

| Tranche | Capacity | Premium on the option's published A$/MW | Anchor |
| ------- | -------- | --------------------------------------: | ------ |
| Base | 0 to 1x the published limit | 0% | The IASR price already carries the community-engagement lead-time allowance, the up-to-20% route lengthening around complex land, and the NSW and Queensland landholder schemes as CBA cost categories |
| Tranche 1 | 1x to 2x | +15% | AEMO's own transmission cost impost for low social licence, set as the midpoint of costed recent scope changes that network businesses made in response to local stakeholder feedback |
| Tranche 2 | 2x to 4x | +60% | The top of AEMO's parcel-density-graduated social licence uplift, applied to the densest REZ at twelve times the reference parcel density |

Implied premiums at the capacity-weighted expansion price:

| Tranche | REZ transmission | Corridor |
| ------- | ---------------: | -------: |
| Base price | A$1,075,349/MW | A$1,150,983/MW |
| Tranche 1 adder | +A$161,300/MW | +A$172,600/MW |
| Tranche 2 adder | +A$645,200/MW | +A$690,600/MW |

The reasoning that joins the two rungs to the two relaxation factors is a land-contestation argument. AEMO's land-use
screen admits the least complex 5% of REZ land for wind and 1% for solar, and its social-licence uplift rises in
proportion to private land parcel density, from a 5% floor at the reference density to 60% at twelve times that density.
Capacity beyond the published limit is by construction capacity on the land the screen excluded, which is the denser and
more contested land. So the first step out takes AEMO's central transmission estimate, and the second step out takes the
top of AEMO's own graduated range rather than inventing a number above it.

The same two rungs are used on generation and on transmission, for one reason: they are the only two numbers AEMO
publishes, and AEMO published the 15% for transmission and the 5% to 60% for REZ generation. Using them on both is a
transfer in one direction and a direct application in the other, and `research.md` cannot say which direction each
transfer runs without knowing which component binds in a given solve.

### Cross-checks

Four independent readings bracket the proposal rather than contradict it:

| Check | Implied premium | Verdict on 15% and 60% |
| ----- | --------------: | ---------------------- |
| AEMO's REZ resource limit violation penalty, in-REZ (A$0.3M/MW) | +27.9% | First tranche is conservative against AEMO's own shadow price |
| AEMO's violation penalty outside a REZ (A$1.0M/MW) | +93.0% | Second tranche sits below the price AEMO puts on building outside a REZ entirely |
| NSW and Queensland landholder schemes at AEMO's easement lengths | +2.0% to +3.2% | Both tranches are several times the cost of the payment schemes, as they must be to stand for scope and delay |
| AEMO's route lengthening to avoid complex land | up to +20% | Brackets the first tranche from above, for detours inside the published limit |

The violation penalties are the closest published analogue to the campaign's question, because they are literally the
price AEMO attaches to one megawatt built past a REZ resource limit. They are a modelling device chosen to make violation
a last resort rather than a costed estimate, so they are used here to bound the proposal, not to set it.

**confidence: medium.** Every published figure in the findings table is high confidence, read from the workbook on the
share or quoted from extracted document text. The first tranche is medium: +15% is AEMO's own transmission estimate in
the right units, but AEMO derived it for scope change on projects inside the published limit, not for capacity beyond it.
The second tranche is low: +60% is transferred from REZ generation build cost to transmission expansion cost, and the
step from parcel density to a relaxation factor rests on the land-contestation argument above, with no source connecting
the two. The band between the cross-checks, roughly 3% at the bottom and 93% at the top, is the honest width of the
evidence. The landholder adders are high confidence for NSW and Queensland and medium for Victoria, whose scheme is known
only through secondary reporting.

## What the premium does not do

| Caveat | Consequence for a result |
| ------ | ------------------------ |
| A relaxation factor of 1.0 makes every tranche a no-op | At factor 1.0 the transmission headroom H equals the published headroom, so tranche 1 covers the whole expansion limit and nothing above it can be built. The premium only bites on a relaxed run, which is the intent, but it means a factor-1.0 run is not a priced baseline, it is an unrelaxed one |
| The chain is myopic | Each period solves without seeing later periods, so a period cannot build cheap headroom early in anticipation of a later tranche binding. The premium is therefore charged period by period on the capacity that period adds, and a chained result will differ from what a perfect-foresight solve would choose |
| Tranches are per component, not per region | Two neighbouring REZs each get their own 1x and 2x steps, so the model can reach 2x in several REZs at once without ever paying the outer rung. Nothing in the premium prices regional concentration across components |
| The hard ceiling is a land-use limit, not a social licence limit | The 4x ceiling comes from scaling AEMO's land-use limits by the run factor. It is a loose stop against absurd concentration, not a claim that 4x is achievable |
| Generation and transmission are priced separately | A megawatt of REZ generation past the resource limit pays the generation tranches; the transmission to carry it pays the link tranches. A project that needs both pays both, which is intended, but nothing checks that the two are consistent for the same project |

## Plot

[`plot_social_licence_premium.py`](plot_social_licence_premium.py) draws the implemented step functions: the REZ
generation relax tranches against the published resource limit, and the REZ and corridor transmission tranches against
published headroom, each against the published anchors that bracket them. It writes `social_licence_premium.html` and
`social_licence_premium.png` beside itself.
