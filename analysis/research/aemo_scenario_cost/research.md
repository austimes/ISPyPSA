# AEMO scenario cost intensity

## Purpose and scope

The dashboard's "Pathway intensities" row draws every chain's conversion cost, the cost excluding fuel and carbon per megawatt hour,
against the milestone years. This topic derives the same measure for the three AEMO 2026 ISP scenarios and commits it as a CSV, so the
conversion cost panel shades the range between them and draws each scenario as a dotted line behind the chains. The same CSV carries each
scenario's operational demand, which the row's demand panel draws the same way. Both overlays sit under one "AEMO 2026 ISP" legend group,
so one legend click hides both; the emissions panel's overlay from [`../aemo_scenario_intensity/`](../aemo_scenario_intensity/) comes from
the draft ISP and keeps its own "AEMO draft ISP" group.

The dashboard draws both overlays on the campaign's own basis, described under [Common basis](#common-basis-with-the-campaigns-measure).

The overlay is a sanity reference, not a target and not a constraint. Nothing in the campaign model reads it.

Scope and boundaries:

- One number per scenario per financial year, 2027 to 2050, for the National Electricity Market (NEM) as a whole.
- AEMO's optimal development path, candidate development path 4 (CDP4), from the final 2026 Integrated System Plan (ISP) (S001).
- The dashboard draws only the years the CSV covers and only from the first plotted campaign year on.

## Derivation

AEMO's "Costs" sheet reports 14 annual cost classes in thousands of dollars, and its "Generation" sheet reports generation in gigawatt
hours (S001). Thousands of dollars over gigawatt hours is dollars per megawatt hour, so no unit factor is needed:

```text
cost_excl_fuel_emissions_aud_per_mwh = (sum of the 14 cost classes - Fuel costs - Emissions costs) / generation excluding rooftop and storage
fuel_aud_per_mwh                     = Fuel costs / generation excluding rooftop and storage
emissions_cost_aud_per_mwh           = Emissions costs / generation excluding rooftop and storage
all_cost_aud_per_mwh                 = sum of the 14 cost classes / generation excluding rooftop and storage
```

The first column is the one the dashboard draws; the other three are kept in the CSV so the split can be checked. The denominator sums
every CDP4 generation row except rooftop and other small-scale solar and except storage and demand-side participation (DSP) net
generation (A001).

## The numbers

Cost excluding fuel and emissions, A$/MWh generated in real July 2023 dollars, from [`aemo_scenario_cost.csv`](aemo_scenario_cost.csv):

| Year | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| 2030 | 49.0 | 44.4 | 56.4 |
| 2035 | 66.2 | 62.2 | 74.5 |
| 2040 | 75.3 | 78.1 | 93.5 |
| 2045 | 78.7 | 85.2 | 101.8 |
| 2050 | 88.6 | 93.7 | 105.9 |

The split and the denominator behind three of those years:

| Year | Scenario | Excl. fuel and emissions (A$/MWh) | Fuel (A$/MWh) | Emissions (A$/MWh) | All costs (A$/MWh) | Generation (TWh) |
|---|---|---:|---:|---:|---:|---:|
| 2030 | Slower Growth | 49.0 | 6.5 | 17.6 | 73.2 | 174 |
| 2030 | Step Change | 44.4 | 6.7 | 19.7 | 70.8 | 210 |
| 2030 | Accelerated Transition | 56.4 | 10.8 | 12.9 | 80.1 | 221 |
| 2040 | Slower Growth | 75.3 | 5.1 | 18.3 | 98.8 | 225 |
| 2040 | Step Change | 78.1 | 4.9 | 9.8 | 92.7 | 294 |
| 2040 | Accelerated Transition | 93.5 | 2.9 | 1.3 | 97.7 | 374 |
| 2050 | Slower Growth | 88.6 | 8.5 | 10.1 | 107.2 | 274 |
| 2050 | Step Change | 93.7 | 3.8 | 5.0 | 102.5 | 332 |
| 2050 | Accelerated Transition | 105.9 | 1.1 | 0.8 | 107.9 | 493 |

Step Change cost classes per MWh generated, showing what drives the rise:

| Cost class | 2030 (A$/MWh) | 2050 (A$/MWh) |
|---|---:|---:|
| Generation, storage and electrolyser capital | 19.74 | 63.77 |
| Generation, storage and electrolyser fixed operation and maintenance (FOM) | 18.72 | 19.50 |
| Generation, storage and electrolyser variable operation and maintenance | 2.14 | 0.82 |
| Generation, storage and electrolyser retirement | 2.02 | 3.40 |
| Flow path capital and operation and maintenance | 1.00 | 3.55 |
| Renewable energy zone (REZ) capital and operation and maintenance | 0.00 | 0.97 |
| System security | 0.82 | 1.53 |
| Distribution capital and operation and maintenance | 0.00 | 0.19 |
| DSP and unserved energy | 0.00 | 0.01 |

Every scenario starts near A$20/MWh in 2027 and more than doubles by 2030. AEMO annualises the capital of new builds only, so the early
years carry little capital; the rise tracks the new fleet's annualised capital accumulating, not a change in the cost of running the grid.

**confidence: high** on the arithmetic: every number is a sum and a ratio of AEMO-published rows, and the five milestone years reproduce
by hand from the source CSV.

## Common basis with the campaign's measure

The dashboard draws AEMO on the campaign's own basis, not as published. The campaign's conversion cost divides by the load its model
serves, which is AEMO operational demand with no transmission losses modelled ([`../../../docs/method.md`](../../../docs/method.md)), and
its costs are in real 30 June 2025 dollars (S002). Two CSV columns restate AEMO on that basis:

```text
common_cost_aud_per_mwh = (14 cost classes - fuel - emissions - retirement - system security - distribution capital - distribution O&M)
                          / generation excluding rooftop and storage / 0.97 x CPI June quarter 2025 / CPI June quarter 2023
operational_demand_twh  = generation excluding rooftop and storage x 0.97
```

| Difference | As published | Common basis | Factor | Basis |
|---|---|---|---|---|
| Dollar year | Real July 2023 dollars (S001) | Real 30 June 2025 dollars (S002) | 141.7 / 133.7 = 1.0598 | A002 (S003, S004) |
| Cost scope | 14 classes less fuel and emissions | Also less retirement, system security and distribution capital and O&M | Classes dropped | A003 |
| Denominator | Generation excluding rooftop and storage (A001) | Operational demand, the load the campaign serves | 1 / 0.97 = 1.031 | A004 |

Common-basis cost, A$/MWh of operational demand in real June 2025 dollars, and operational demand in TWh:

| Year | Cost, Slower Growth | Cost, Step Change | Cost, Accelerated Transition | Demand, Slower Growth | Demand, Step Change | Demand, Accelerated Transition |
|---|---:|---:|---:|---:|---:|---:|
| 2030 | 47.4 | 45.5 | 52.2 | 169.0 | 204.2 | 214.8 |
| 2035 | 67.5 | 64.9 | 79.3 | 194.6 | 251.3 | 296.3 |
| 2040 | 80.8 | 83.5 | 99.5 | 217.8 | 285.3 | 362.5 |
| 2045 | 83.0 | 90.0 | 107.8 | 240.3 | 307.5 | 418.8 |
| 2050 | 91.1 | 96.8 | 110.9 | 265.4 | 322.1 | 477.8 |

Inflation and the smaller denominator raise every figure by 9.3%, and dropping the unmodelled classes takes some of that back. Against
the published series, the common basis runs 8% lower to 2% higher in 2030, where retirement costs are heaviest, and 3% to 7% higher from
2035 on.

**confidence: high** on the price-index factor: both index values are ABS-published, and AEMO's own IASR names the same All groups index.

**confidence: medium** on the dropped classes: the campaign has no retirement, system security or distribution cost, but AEMO does not
split its generation capital and O&M the way the campaign splits sunk and new-build capital.

**confidence: low** on the 0.97: it is the demand plan's authored placeholder, not an AEMO figure
([`../demand_plan/`](../demand_plan/), A010 there).

One scope difference remains. The campaign counts pre-2030 existing-fleet capital as sunk and adds annualised capital and FOM of the
chain's surviving builds and existing-fleet FOM ([`../../sharp/frontier_points.py`](../../sharp/frontier_points.py)); AEMO annualises the
capital of its new builds only. The ShARP reference on the same panel ([`../sharp_grid_reference/`](../sharp_grid_reference/)) is restated
to the same basis, so every line on the cost and demand panels shares one dollar year and one denominator.

## Plot

[`plot_aemo_scenario_cost.py`](plot_aemo_scenario_cost.py) reads the committed source extract
[`aemo_2026_isp_cdp4_costs_generation.csv`](aemo_2026_isp_cdp4_costs_generation.csv), writes
[`aemo_scenario_cost.csv`](aemo_scenario_cost.csv) and renders [`aemo_scenario_cost.png`](aemo_scenario_cost.png) and its HTML twin:
each scenario's cost as published (dotted) and on the common basis the dashboard draws (solid). The dashboard reads the same committed
CSV, so the figure and the overlay never disagree.

Run it with:

```bash
uv run --with kaleido python analysis/research/aemo_scenario_cost/plot_aemo_scenario_cost.py
```
