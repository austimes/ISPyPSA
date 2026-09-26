# AEMO scenario emissions intensity

## Purpose and scope

The campaign dashboard's "Pathway intensities" row draws every chain's fleet emissions intensity against the milestone years. Read on its
own, that panel gives no sense of whether a chain sits inside or outside the range AEMO's own scenarios cover. This topic commits a per-year
NEM emissions intensity for each of the three AEMO 2026 Integrated System Plan (ISP) scenarios, so the panel can shade the range between
them and draw each scenario as a dotted line behind the chains.

It holds two series, each with its own job:

| Series | File | Source | Used by |
|---|---|---|---|
| 2026 ISP | [`aemo_scenario_intensity_final_isp.csv`](aemo_scenario_intensity_final_isp.csv) | Final 2026 ISP published emissions over operational demand (S006) | The dashboard's emissions overlay |
| Draft 2026 ISP | [`aemo_scenario_intensity.csv`](aemo_scenario_intensity.csv) | Derived from draft 2026 ISP generation and NGER factors (S001, S003, S004) | The base chain's cap schedule, `cap_intensity_t_per_mwh` in [`analysis/hpc/demand_plan.json`](../../hpc/demand_plan.json) |

The overlay is a sanity reference, not a target and not a constraint: nothing in the campaign model reads the 2026 ISP series. The draft
series is the cap source, applied as described in [`../near_term_pipeline/`](../near_term_pipeline/).

Scope and boundaries:

- One number per scenario per year on the National Electricity Market (NEM) as a whole: financial years ending 2027 to 2050 for the 2026
  ISP series, 2010 to 2050 for the draft series. No sub-regional split.
- The 2026 ISP series is AEMO's own "NEM Emissions (Mt CO2-e)" per megawatt hour of operational demand. The draft series is Scope 1
  combustion emissions of grid-connected generation per megawatt hour generated excluding rooftop photovoltaics.
- Candidate development path 4 (CDP4), the optimal development path, in both.

## The dashboard overlay: 2026 ISP

### Source and derivation

The final 2026 ISP generation and storage outlook publishes per-year NEM emissions on its `Emissions` sheet, one row per region, and
generation by technology on its `Generation` sheet (S006). The rows used are extracted to
[`aemo_2026_isp_cdp4_emissions_generation.csv`](aemo_2026_isp_cdp4_emissions_generation.csv):

```text
emissions_Mt            = sum over the five regions of the CDP4 (ODP) Emissions rows
operational_demand_TWh  = (generation excluding rooftop and storage + storage and DSP net generation) / 1000
t_CO2e_per_MWh          = emissions_Mt / operational_demand_TWh
```

Storage and demand-side participation (DSP) net generation is negative: it is the energy storage loses on the round trip. The two
generation series are the same sums [`../aemo_scenario_cost/`](../aemo_scenario_cost/) extracts from the same sheet, and they match its
extract to the gigawatt hour.

### Denominator: operational demand, not generation

The draft series divides by generation excluding rooftop; the 2026 ISP series divides by operational demand instead (A006), because
that is the basis of the measure it sits beside. The campaign's `fleet_intensity` is emissions per megawatt hour delivered to the model's
loads, which is operational demand ([`analysis/sharp/method_years.py`](../../sharp/method_years.py), module docstring, "Denominator"). The
same panel row's cost and demand overlays use this operational demand (A004 in [`../aemo_scenario_cost/`](../aemo_scenario_cost/)).
Dividing by the smaller denominator raises the intensity by 0.4% in 2027 and, as storage grows, by 4% to 6% at the milestones from 2030.

### The numbers

Intensity in t CO2e/MWh of operational demand, from [`aemo_scenario_intensity_final_isp.csv`](aemo_scenario_intensity_final_isp.csv); the
dashboard shows it in g CO2e/kWh, 1,000 times these numbers:

| Year | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| 2030 | 0.17610 | 0.19304 | 0.12631 |
| 2035 | 0.07615 | 0.07292 | 0.00922 |
| 2040 | 0.08527 | 0.04564 | 0.00628 |
| 2045 | 0.06430 | 0.03294 | 0.00296 |
| 2050 | 0.02471 | 0.01231 | 0.00203 |

The emissions and energy behind them:

| Year | Scenario | Emissions (Mt CO2e) | Generation excl. rooftop and storage (TWh) | Operational demand (TWh) |
|---|---|---:|---:|---:|
| 2030 | Slower Growth | 29.1 | 174 | 165 |
| 2030 | Step Change | 39.2 | 210 | 203 |
| 2030 | Accelerated Transition | 27.0 | 221 | 214 |
| 2040 | Slower Growth | 18.2 | 225 | 213 |
| 2040 | Step Change | 12.7 | 294 | 278 |
| 2040 | Accelerated Transition | 2.2 | 374 | 351 |
| 2050 | Slower Growth | 6.5 | 274 | 261 |
| 2050 | Step Change | 3.9 | 332 | 313 |
| 2050 | Accelerated Transition | 0.9 | 493 | 466 |

Slower Growth forms the band's upper edge from 2031 on, as it keeps coal running longest; Step Change forms it in 2027 and 2030.
Accelerated Transition forms the lower edge throughout, first dips below 0.005 in 2039 and stays below it from 2044. The series starts
in financial year 2027, so the overlay does not reach the campaign's 2026 milestone.

### Against the draft

Step Change, t CO2e/MWh:

| Year | Draft, per MWh generated (cap source) | 2026 ISP, per MWh generated | 2026 ISP, per MWh of operational demand (overlay) |
|---|---:|---:|---:|
| 2030 | 0.19673 | 0.18641 | 0.19304 |
| 2035 | 0.06450 | 0.06925 | 0.07292 |
| 2040 | 0.04136 | 0.04312 | 0.04564 |
| 2045 | 0.02714 | 0.03109 | 0.03294 |
| 2050 | 0.01385 | 0.01159 | 0.01231 |

On the same generated basis, the final ISP's published emissions sit 5% below the draft derivation in 2030, 4% to 15% above it over 2035
to 2045 and 16% below it in 2050. The move to operational demand adds 4% to 6% on top. The drawn Step Change line therefore moves from
196.7 to 193.0 g CO2e/kWh in 2030, from 41.4 to 45.6 in 2040 and from 13.9 to 12.3 in 2050.

**confidence: high** on the 2026 ISP series as a statement of AEMO's published emissions: both terms are read from AEMO's workbooks, and
the only authored choice is the operational-demand denominator (A006), shared with the cost overlay. The `Emissions` sheet states no
emissions scope, so whether it matches the campaign's Scope 1 combustion boundary exactly is not confirmed.

## The cap source: draft 2026 ISP series

### Why the draft series is derived rather than read

The draft 2026 ISP published no per-year NEM emissions series, and the 2026 IASR workbook carries cumulative megatonne budgets only, which
cannot be placed on a per-year intensity axis (S002):

| Budget | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| Long-term cumulative budget (Mt CO2e) | 727 | 583 | 303 |
| Cumulative to 2030, federal-target figure (Mt CO2e) | 321 | 290 | 240 |
| Cumulative to 2035, federal-target figure (Mt CO2e) | 24 | 23 | 8 |

Those numbers are recorded here as context and are drawn nowhere on the dashboard.

### Derivation

Three inputs, all cited by path:

1. Annual generation by fuel in terawatt hours for each scenario, from the draft 2026 ISP CDP4 outputs tracked in this repository (S001).
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

Megatonnes per terawatt hour and tonnes per megawatt hour are the same number.

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

### The numbers

Intensity in t CO2e/MWh generated, from [`aemo_scenario_intensity.csv`](aemo_scenario_intensity.csv):

| Year | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| 2026 | 0.55741 | 0.55646 | 0.51997 |
| 2030 | 0.15929 | 0.19673 | 0.09599 |
| 2040 | 0.10312 | 0.04136 | 0.00766 |
| 2050 | 0.03003 | 0.01385 | 0.00819 |

The Step Change column at the campaign's milestones is the base chain's cap schedule, held at its 2050 value to 2060.

### Does it hold up

The draft CDP4 files start in 2010, so the same arithmetic can be run against years with a published outturn. For 2024 it gives 188 TWh of
generation excluding rooftop and 0.620 t CO2e/MWh, against the roughly 0.63 t CO2e/MWh the NEM actually recorded that year (S005).
Agreement to about 2% on a year with no policy assumptions in it is the strongest check available on the factor and heat rate choices. The
final ISP's published emissions, on the same generated basis, land within 5% of the derivation in 2030 and within 16% in 2050.

**confidence: medium** on the draft series. It is derived from AEMO's published generation outputs and the fork's NGER factors, not read
from an AEMO-published emissions series, so it carries the error of three authored choices: the coal blend, the four heat rate medians and
the generation-excluding-rooftop denominator. The 2024 back-check bounds that error at a few per cent on a high-emitting year.

## Reading it beside the campaign

The base chain's cap is the draft Step Change intensity applied to the chain's source load (see
[`../near_term_pipeline/`](../near_term_pipeline/)), so the base chain is held to the draft line, not the drawn 2026 ISP line. The draft
cap sits above the drawn Step Change line in 2030 and 2050 and below it over 2035 to 2045, by the differences in the table above. The
increment grid's intensity levels are multiples of the same draft caps.

## Plot

[`plot_aemo_scenario_intensity.py`](plot_aemo_scenario_intensity.py) writes both CSVs and renders
[`aemo_scenario_intensity.png`](aemo_scenario_intensity.png) and its HTML twin: the 2026 ISP range and lines the dashboard draws, solid,
and the draft lines the caps come from, dotted. The dashboard reads the committed 2026 ISP CSV, so the page needs no extra input and the
figure and the overlay can never disagree.

Run it with:

```bash
uv run --with kaleido python analysis/research/aemo_scenario_intensity/plot_aemo_scenario_intensity.py
```
