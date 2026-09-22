# AEMO scenario emissions intensity

## Purpose and scope

The campaign dashboard's "Pathway intensities" row draws every chain's fleet emissions intensity against the milestone years. Read on its
own, that panel gives no sense of whether a chain sits inside or outside the range AEMO's own scenarios cover. This topic derives a per-year
NEM emissions intensity for each of the three AEMO 2026 draft ISP scenarios and commits it as a CSV, so the panel can shade the range between
them and draw each scenario as a dotted line behind the chains.

The overlay is a sanity reference, not a target and not a constraint. Nothing in the campaign model reads it: it is drawn on one dashboard
panel and recorded here.

Scope and boundaries:

- One number per scenario per year, 2010 to 2050, on the National Electricity Market (NEM) as a whole. No sub-regional split.
- Scope 1 combustion emissions of grid-connected generation only. No upstream fuel-cycle emissions, no rooftop photovoltaics, no other
  sectors.
- Emissions per megawatt hour **generated** excluding rooftop, not per megawatt hour delivered to customers. The campaign's own
  `fleet_intensity` is on the same generated basis, so the two are comparable without a delivery factor.

## Why the series is derived rather than read

AEMO publishes no per-year NEM emissions series in the 2026 IASR workbook. Its "Carbon Budgets" sheet carries cumulative megatonne budgets
only, which cannot be placed on a per-year intensity axis (S002):

| Budget | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| Long-term cumulative budget (Mt CO2e) | 727 | 583 | 303 |
| Cumulative to 2030, federal-target figure (Mt CO2e) | 321 | 290 | 240 |
| Cumulative to 2035, federal-target figure (Mt CO2e) | 24 | 23 | 8 |

Those numbers are recorded here as context and are drawn nowhere on the dashboard.

## Derivation

Three inputs, all cited by path:

1. Annual generation by fuel in terawatt hours for each scenario, from the draft 2026 ISP candidate development path 4 (CDP4) outputs tracked
   in this repository (S001).
2. Combined Scope 1 combustion emission factors in kilograms of carbon dioxide equivalent per gigajoule, from the fork's NGER cross-walk
   (S003).
3. A heat rate in gigajoules per megawatt hour sent out for each fuel, converting the fuel's electricity output back to fuel energy, from the
   2026 final IASR heat rate table (S004).

For each year and scenario:

```text
emissions_Mt      = sum over fuels of ( generation_TWh x factor_kg_per_GJ x heat_rate_GJ_per_MWh / 1000 )
generation_TWh    = sum of every CDP4 fuel column less Solar (Rooftop)
t_CO2e_per_MWh    = emissions_Mt / generation_TWh
```

Megatonnes per terawatt hour and tonnes per megawatt hour are the same number, so the result drops straight onto the dashboard panel's
existing axis.

### The four fuel factors

| CDP4 fuel | NGER carrier | Factor (kg CO2e/GJ) | Heat rate (GJ/MWh) | Emissions per MWh generated (t CO2e/MWh) |
|---|---|---:|---:|---:|
| Coal | 75% Black Coal, 25% Brown Coal (A001) | 91.135 | 10.052 | 0.9159 |
| Gas | Gas | 51.530 | 11.155 | 0.5748 |
| Distillate | Liquid Fuel (A003) | 70.200 | 12.001 | 0.8425 |
| Bioenergy | Biomass | 1.800 | 17.535 | 0.0316 |

Bioenergy carries only its methane and nitrous oxide combustion residuals: the NGER cross-walk treats biomass carbon dioxide as biogenic and
gives it a factor of zero. Hydro, wind, solar and demand response burn nothing and contribute no emissions.

Each heat rate is the median of the units burning that fuel in the IASR table: 15 sub- and super-critical steam units for coal, 48
combined-cycle, open-cycle and reciprocating units for gas, two biomass units for bioenergy. CDP4 reports no separate liquid-fuelled plant,
so distillate takes the small open-cycle gas turbines, which is where the NGER cross-walk places diesel in the IASR fleet.

The gas heat rate is the weakest of the four, because a unit-count median over 48 units leans towards the many small peakers rather than
towards the combined-cycle plant that supplies most gas energy. It barely matters: replacing 11.155 with the combined-cycle median of 7.67
moves Step Change in 2030 from 0.1967 to 0.1941 t CO2e/MWh, a 1.3% shift, because gas is a small share of generation in every year plotted.

## The numbers

Intensity in t CO2e/MWh generated, from [`aemo_scenario_intensity.csv`](aemo_scenario_intensity.csv):

| Year | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| 2030 | 0.15929 | 0.19673 | 0.09599 |
| 2040 | 0.10312 | 0.04136 | 0.00766 |
| 2050 | 0.03003 | 0.01385 | 0.00819 |

The generation and emissions behind those intensities:

| Year | Scenario | Generation excl. rooftop (TWh) | Emissions (Mt CO2e) |
|---|---|---:|---:|
| 2030 | Slower Growth | 174 | 27.7 |
| 2030 | Step Change | 209 | 41.1 |
| 2030 | Accelerated Transition | 221 | 21.2 |
| 2040 | Slower Growth | 220 | 22.7 |
| 2040 | Step Change | 291 | 12.0 |
| 2040 | Accelerated Transition | 375 | 2.9 |
| 2050 | Slower Growth | 268 | 8.0 |
| 2050 | Step Change | 332 | 4.6 |
| 2050 | Accelerated Transition | 491 | 4.0 |

Two features worth naming. Slower Growth is the *highest*-intensity scenario from 2034 on, because it keeps coal running longest; over 2029
to 2033 Step Change is highest instead, so the shaded range swaps which scenario forms its upper edge partway along. And Accelerated
Transition stops falling around 2039 and holds between 0.004 and 0.011 to 2050, wandering rather than trending, as gas peaking varies against
a fleet that is already almost decarbonised.

## Does it hold up

The CDP4 files start in 2010, so the same arithmetic can be run against years with a published outturn. For 2024 it gives 188 TWh of
generation excluding rooftop and 0.620 t CO2e/MWh, against the roughly 0.63 t CO2e/MWh the NEM actually recorded that year. Agreement to
about 2% on a year with no policy assumptions in it is the strongest check available on the factor and heat rate choices, and it is well
inside the precision a sanity band needs.

**confidence: medium.** The series is derived from AEMO's published generation outputs and the fork's NGER factors, not read from an
AEMO-published emissions series, so it carries the error of three authored choices: the coal blend, the four heat rate medians and the
generation-excluding-rooftop denominator. The 2024 back-check bounds that error at a few per cent on a high-emitting year.

## Reading it beside the campaign

The campaign's cap ladder anchors every schedule at 0.12 t CO2e/MWh delivered in 2030 (see [`../carbon_caps/`](../carbon_caps/)). AEMO's
Step Change reaches 0.197 in 2030 on the generated basis, so the campaign's own 2030 rung is materially tighter than the AEMO scenario the
overlay sits closest to. By 2050 the positions reverse: every cap schedule targets 0.02 or below, which is at or under the 0.008 to 0.030
range the three scenarios span. The overlay is there to make exactly that comparison visible on the panel rather than to validate either
number.

## Plot

[`plot_aemo_scenario_intensity.py`](plot_aemo_scenario_intensity.py) computes the series, writes
[`aemo_scenario_intensity.csv`](aemo_scenario_intensity.csv) and renders
[`aemo_scenario_intensity.png`](aemo_scenario_intensity.png) and its HTML twin. The dashboard reads the same committed CSV, so the page needs
no extra input and the figure and the overlay can never disagree.

Run it with:

```bash
uv run --with kaleido python analysis/research/aemo_scenario_intensity/plot_aemo_scenario_intensity.py
```
