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

## A001 -- Constant residual emissions factor

Each ladder point's intensity assumes the non-renewable remainder emits at the planned year's residual factor, planned
intensity over one less the planned renewable share. ShARP publishes no intensity for its ladder points, so this is authored
here.

## A002 -- 99% endpoint priced along the last segment

The ladder is extended to a renewable share of 0.99 at the slope of its last published segment, following S006. ShARP's
files carry no row for that endpoint, so the extension is reconstructed here.

## A003 -- Extra-MWh price proxy

The approximate price of one extra MWh is the ladder cost interpolated at the planned renewable share plus the overflow-scale
premium. It leaves out ShARP's fuel and carbon allowances and its overflow-growth charge (S006).

## A004 -- No boundary factor

ShARP's national net-delivered boundary is not scaled to the NEM, because only intensities and per-MWh costs are compared.

## A005 -- Demand-arm units

The demand arm's measure is already a cost per extra TWh, so ShARP's price is multiplied by 10^6 MWh per TWh and nothing
else.

## A006 -- Intensity-arm anchor

The ShARP intensity-arm line starts at (1, 0), the planned point, as the campaign's own arm starts at its base cell.
