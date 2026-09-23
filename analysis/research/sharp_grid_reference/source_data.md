# ShARP grid reference -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv); authored
assumption ids match [`assumptions_ledger.csv`](assumptions_ledger.csv).

Every source is a file of the ShARP role `generate_grid_electricity` in the GitHub repository `austimes/sharp`, pinned at
commit `eaf1ca27`, under `library/roles/generate_grid_electricity/`. The repository is private, so no copy is readable from
this repository; the rows quoted below were read from that commit through the authenticated `gh` command line, the same way
[`plot_sharp_grid_reference.py`](plot_sharp_grid_reference.py) reads them.

## S001 -- Planned pathway states

**Source:** `overflow_supply_pathway_states.csv`. Supplies `planned_quantity` (TWh), `planned_renewable_fraction` and
`planned_fuel_cost_basis_per_unit` (the fuel allowance, A$2024/MWh). The 2030 row of the current-policy future, verbatim up
to its source ids:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,electricity__grid_supply__current_policy_clean_transition,2030,213.911,0.793941129297777,5.84673598888903,source_mapped__signed_hydro_load__landfill_residual,2024,MAUD_2024,...
> ```

## S002 -- Method years

**Source:** `method_years.csv`. Supplies `output_cost_per_unit` (non-fuel cost, A$2024/MWh), `input_coefficients` (coal,
lignite and natural gas, PJ/TWh) and `energy_emissions_by_pollutant` (CO2e, MtCO2e/TWh). The 2050 row of the current-policy
future, verbatim to its emissions column:

> ```text
> 2050,135.07966747323,2024,MAUD_2024,"[""coal"", ""lignite"", ""natural_gas""]","[0.0,0.0,0.1946518039759835]","[""PJ/TWh"",""PJ/TWh"",""PJ/TWh""]","[{""pollutant"":""CO2e"",""value"":0.011590504625945963}]",...
> ```

## S003 -- Clean ladder

**Source:** `overflow_supply_cleanliness_curve.csv`. One ladder per year, common to every grid future, of
`renewable_fraction` against `average_cost_per_unit` (A$2024/MWh). The 2030 ladder, verbatim to its cost column:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,assumed_clean_at_360676,Assumed clean-supply curve at 36.07% renewables,0,0.360676,88.684595017,...
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,clean_to_668379,Additional clean supply to 66.84% renewables,1,0.668378655,93.553367902,...
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,clean_to_768379,Additional clean supply to 76.84% renewables,2,0.768378655,95.135665879,...
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,clean_to_868379,Additional clean supply to 86.84% renewables,3,0.868378655,98.102474587,...
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,clean_to_968379,Additional clean supply to 96.84% renewables,4,0.968378655,104.629453743,...
> ```

ShARP tags each point `exploratory` and cautions, verbatim: "This is a projected whole-system cost point, not a direct price
for supply added beyond plan."

## S004 -- Overflow-scale premiums

**Source:** `overflow_supply_scale_premiums.csv`. One `overflow_scale_premium_per_unit` (A$2024/MWh) per year. The 2040 row,
verbatim to its currency:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2040,total_overflow_flat,Overflow-scale,11.720471,2024,MAUD_2024,...
> ```

## S005 -- Gas backstop

**Source:** `overflow_supply_backstop.csv`. ShARP's other beyond-plan option: additional open-cycle gas generation. It is
recorded as context and drawn nowhere, because the dashboard's reference follows the clean ladder. The 2030 row, verbatim to
its emissions unit:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,large_ocgt_20pct,Additional open-cycle gas generation,107.937680,2024,MAUD_2024,natural_gas,10.909091,PJ/TWh,transformation_energy,"[{""pollutant"":""CO2e"",""value"":0.562145}]",MtCO2e/TWh,...
> ```

## S006 -- Role README

**Source:** `README.md` of the same role directory. On the cost boundary, verbatim:

> "Coal, lignite and natural gas are paid for separately as fuel inputs, and any policy carbon cost is also added
> separately."

On the structure of ShARP's own beyond-plan price, verbatim:

> "For a fair comparison with planned supply, its price includes the fuel and carbon-price amounts that its own parent
> future would have paid, followed by the cleanliness and overflow-scale amounts."

On the 99% ladder endpoint, verbatim:

> "Every post-2025 clean-supply sequence ends with a local extension to a nominal 99% renewable endpoint at the final
> published interval's incremental price."

## S007 -- ShARP A052, national delivered-electricity factors

**Source:** `assumptions_ledger.csv` of the same role directory, assumption `A052`. On how ShARP maps AEMO's NEM source
generation to its national delivered quantity, verbatim:

> "Rooftop output is removed before translation. Each source quantity is multiplied by planned delivered electricity divided
> by matching source electricity; the existing geographic factor of 1.3 and delivery factor of 0.7914939324516337 establish
> planned output rounded once to 5 TWh. Landfill electricity is then removed once from total and renewable output."

## S008 -- ABS Consumer Price Index, All groups, weighted average of eight capital cities

**Source:** Australian Bureau of Statistics (ABS), Consumer Price Index, Australia: quarterly index numbers, All groups CPI,
original series, weighted average of eight capital cities (series A2325846C), read through the ABS data API at
<https://data.api.abs.gov.au/rest/data/ABS,CPI,1.1.0/1.10001.10.50.Q?startPeriod=2023-Q1>. The rows used, verbatim:

> ```text
> DATAFLOW,MEASURE,INDEX,TSEST,REGION,FREQ,TIME_PERIOD,OBS_VALUE,UNIT_MEASURE,OBS_STATUS,DECIMALS,OBS_COMMENT
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q1,137.4,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q2,138.8,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q3,139.1,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q4,139.4,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2025-Q2,141.7,IN,,1,
> ```

AEMO names the same index for rebasing its own dollar years; the quote is in
[`../aemo_scenario_cost/source_data.md`](../aemo_scenario_cost/source_data.md) (S004 there). ShARP's conventions set the
basis year but no quarter, verbatim from `library/CONVENTIONS.md` at the pinned commit: "deflation to a common basis is the
consumer's responsibility and must use the stated basis year."

## S009 -- Overflow-growth bands

**Source:** `overflow_supply_growth_bands.csv`. Two annual price bands on growth beyond plan, in A$2024/MWh, with no year
column. The lower band, verbatim to its currency:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,expected_growth,Expected annual overflow growth,1,12,2.155449,2024,MAUD_2024,...
> ```

The role README (S006) states how long a band's price is carried, verbatim: "Each positive increment retains its annual
overflow-growth price from the year it is added through 2050."

## S010 -- Overflow-growth adjustments

**Source:** `overflow_supply_growth_adjustments.csv`. One-year adjustments on growth beyond plan, by installation year, in
A$2024/MWh. Its only row, verbatim to its currency:

> ```text
> generate_grid_electricity,generate_grid_electricity__pathway_bundle,2030,renewable_target_short_lead_time,Short-lead-time overflow-growth adjustment,37.447769,2024,MAUD_2024,...
> ```

## A001 -- Constant residual emissions factor

Each ladder point's intensity assumes the non-renewable remainder emits at the planned year's residual factor, planned
intensity over one less the planned renewable share. ShARP publishes no intensity for its ladder points, so this is authored
here.

## A002 -- 99% endpoint priced along the last segment

The ladder is extended to a renewable share of 0.99 at the slope of its last published segment, following S006. ShARP's
files carry no row for that endpoint, so the extension is reconstructed here.

## A003 -- Extra-MWh price proxy

The approximate price of one extra MWh is the ladder cost interpolated at the planned renewable share, plus the
overflow-scale premium (S004), the planned future's fuel allowance (S001) and the overflow-growth charge: the lower band
(S009) in every year, plus the one-year adjustment in its installation year, FY2030 (S010). The lower band assumes a cell's
growth beyond plan stays under 12 TWh a year, and it is applied after 2050 too, though S006 carries it only to 2050. The
proxy leaves out ShARP's carbon allowance (S006).

## A004 -- No boundary factor on intensities

ShARP's emissions and fuel input intensities are drawn as published, per MWh of ShARP's delivered quantity. The common basis
covers the cost and demand panels only, through A007 to A009.

## A005 -- Demand-arm units

The demand arm's measure is already a cost per extra TWh, so ShARP's price is multiplied by 10^6 MWh per TWh and nothing
else.

## A006 -- Intensity-arm anchor

The ShARP intensity-arm line starts at (1, 0), the planned point, as the campaign's own arm starts at its base cell.

## A007 -- Delivered to NEM generation by ShARP's own factors

Per-MWh costs are multiplied by the delivery factor, 0.7915, and quantities divided by the geographic and delivery factors
together, 1.3 x 0.7915 (S007). The step assumes cost and energy scale with ShARP's national quantity in one flat ratio.

## A008 -- Operational demand as generation net of storage losses

NEM generation excluding rooftop becomes operational demand at Step Change's generation net of storage losses over
generation, per year, the demand plan's measured factor ([`../demand_plan/`](../demand_plan/), A010 there). It is read from
the `operational_share` column of [`../aemo_scenario_cost/aemo_scenario_cost.csv`](../aemo_scenario_cost/aemo_scenario_cost.csv),
which sets AEMO's common basis the same way, and held at its FY2027 value for 2026 and its FY2050 value after 2050.


## A009 -- A$2024 as the 2024 mean index

ShARP's A$2024 is taken as the mean of the four 2024 quarterly index values, 138.675, and inflated to the June quarter 2025,
141.7 (S008), a factor of 1.0218. The June quarter 2024 alone would give 1.0209.

## A010 -- Futures range over every grid method

The demand band spans the lowest and highest planned quantity over every method in S001 each year, six methods of which the
two current-policy ones share one quantity path.
