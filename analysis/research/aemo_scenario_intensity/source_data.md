# AEMO scenario emissions intensity -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv); authored assumption ids
match [`assumptions_ledger.csv`](assumptions_ledger.csv).

## S001 -- AEMO 2026 draft ISP CDP4 generation outputs

**Source:** three files tracked in this repository, one per scenario:

- `iasr outputs/NEM-aemo2026draft-slower_growth-CDP4 (ODP)-energy.csv`
- `iasr outputs/NEM-aemo2026draft-step_change-CDP4 (ODP)-energy.csv`
- `iasr outputs/NEM-aemo2026draft-accelerated_transition-CDP4 (ODP)-energy.csv`

Each holds 41 annual rows, financial years 2010 to 2050, in terawatt hours. The header and first row of the Step Change file, verbatim:

> ```text
> "date","Demand Response","Coal","Bioenergy","Distillate","Gas","Hydro","Wind","Solar (Utility)","Solar (Rooftop)"
> "1 Jan 2010 12:00 am","0","171","0","0","21","13","4","0","0"
> ```

The Step Change rows for the three milestone years, verbatim:

> ```text
> "1 Jan 2030 12:00 am","0","43","0","0","3","14","81","68","45"
> "1 Jan 2040 12:00 am","0","10","0","0","5","13","165","98","79"
> "1 Jan 2050 12:00 am","0","0","0","0","8","10","189","125","121"
> ```

The same three columns and the same date format are read by
[`../demand_plan/plot_demand_trajectories.py`](../demand_plan/plot_demand_trajectories.py), which established the date parsing and the
generation-excluding-rooftop convention reused here.

## S002 -- IASR workbook "Carbon Budgets" sheet

**Source:** sheet "Carbon Budgets" of the AEMO 2026 ISP inputs and assumptions workbook,
`2026-isp-inputs-and-assumptions-workbook.xlsm`, in the input package on the data share (path resolved by
[`../../env.py`](../../env.py) as `Env.iasr_workbook`).

**No verbatim quote is carried for this source.** The sheet is not parsed into the repository and not parsed into the input package's
workbook cache either -- the only carbon table in that cache is `regional_carbon_budget_trajectory.csv`, which holds the state percentage
reduction targets rather than the budgets. The figures below are recorded as supplied, without a quoted cell reference:

| Budget | Slower Growth | Step Change | Accelerated Transition |
|---|---:|---:|---:|
| Long-term cumulative budget (Mt CO2e) | 727 | 583 | 303 |
| Cumulative to 2030, federal-target figure (Mt CO2e) | 321 | 290 | 240 |
| Cumulative to 2035, federal-target figure (Mt CO2e) | 24 | 23 | 8 |

These are cumulative megatonnes, not a per-year series, which is why the overlay is derived from S001 rather than read from here, and why
none of these numbers is drawn on the dashboard.

## S003 -- NGER combustion emission factors

**Source:** [`../../sharp/nger_factors.py`](../../sharp/nger_factors.py), which cross-walks the National Greenhouse Accounts Factors 2024
(DCCEEW, July 2024) to ISPyPSA's carrier set.

On the basis and units, verbatim:

> "All factors are Scope 1 (direct combustion), in kg CO2-e per GJ on a Gross Calorific Value basis. CO2 / CH4 / N2O are reported separately
> (in CO2-e units already, i.e. multiplied by AR5 GWP-100); the "combined" column is their sum."

The four factors this topic uses, verbatim from the table constant (`(CO2, CH4, N2O, NGA table, NGA fuel name)`):

> ```python
> "Black Coal": (90.0, 0.04, 0.2, "Table 4", "Bituminous coal"),
> "Brown Coal": (93.5, 0.02, 0.3, "Table 4", "Brown coal (lignite)"),
> "Gas": (51.4, 0.1, 0.03, "Table 5", "Natural gas distributed in a pipeline"),
> "Liquid Fuel": (69.9, 0.1, 0.2, "Table 8", "Diesel oil"),
> "Biomass": (0.0, 0.8, 1.0, "Table 4", "Primary solid biomass fuels"),
> ```

Summing each row gives the combined factors used here: Black Coal 90.24, Brown Coal 93.82, Gas 51.53, Liquid Fuel 70.20, Biomass 1.80
kg CO2e/GJ. On why biomass carbon dioxide is zero, verbatim:

> "\"Biomass\" -> NGA \"Primary solid biomass fuels other than those mentioned in the items above\" (Table 4). CO2 is biogenic (zero); CH4 +
> N2O combustion residuals only."

On placing diesel in the IASR fleet, which is why the CDP4 Distillate column takes an open-cycle gas turbine heat rate, verbatim:

> "\"Liquid Fuel\" -> NGA \"Diesel oil\" (Table 8). ISPyPSA's IASR fleet uses diesel for liquid-fuelled OCGT."

## S004 -- IASR existing-fleet heat rates

**Source:** `heat_rates_existing_committed_anticipated_additional_generators.csv` in the 2026 final input package's workbook cache on the
data share (path resolved by [`../../env.py`](../../env.py) as `Env.workbook_cache`). The table is not tracked in this repository, so the
four medians derived from it are carried as constants in
[`plot_aemo_scenario_intensity.py`](plot_aemo_scenario_intensity.py).

The header and first two rows, verbatim:

> ```text
> IASR ID,Power Station,Technology,Heat rate (GJ/MWh)
> BW01,Bayswater,Steam Sub Critical,10.0519349978723
> CALL_B_1,Callide B,Steam Sub Critical,10.0662696087912
> ```

Medians by technology group, computed from that table:

| Group | Technologies | Units | Median heat rate (GJ/MWh) |
|---|---|---:|---:|
| Coal | Steam Sub Critical, Steam Super Critical | 15 | 10.052 |
| Gas | CCGT, CCGT - Gas Turbine, CCGT - Steam Turbine, OCGT (large GT), OCGT (small GT), Reciprocating engine | 48 | 11.155 |
| Distillate | OCGT (small GT) | 21 | 12.001 |
| Bioenergy | Biomass | 2 | 17.535 |

The combined-cycle median alone is 7.67 GJ/MWh, which is the alternative gas figure the sensitivity in `research.md` quotes.

## S005 -- NEM outturn intensity used as a back-check

**Source:** the roughly 0.63 t CO2e/MWh generated that the NEM recorded in financial year 2024.

**No verbatim quote is carried for this source.** No copy of an AEMO or Clean Energy Regulator emissions-intensity publication is readable
from this repository, so the back-check in `research.md` is reported against a remembered order-of-magnitude figure rather than a quoted one.
The check is a smoke test on the factor and heat rate choices, and nothing in the derivation depends on its precision.

## S006 -- AEMO 2026 ISP generation and storage outlook, CDP4 emissions and generation

**Source:** AEMO's final 2026 ISP "2026 ISP generation and storage outlook", published 25 June 2026 at
<https://www.aemo.com.au/energy-systems/major-publications/integrated-system-plan-isp/2026-integrated-system-plan-isp> as
`2026-isp-generation-and-storage-outlook.zip`, the same download as S001 of [`../aemo_scenario_cost/`](../aemo_scenario_cost/). Three
workbooks inside it were read, one per scenario:

- `Core scenarios/2026 ISP - Step Change - Core.xlsx`
- `Core scenarios/2026 ISP - Slower Growth - Core.xlsx`
- `Core scenarios/2026 ISP - Accelerated Transition - Core.xlsx`

The zip is not tracked in this repository; the rows used are extracted to
[`aemo_2026_isp_cdp4_emissions_generation.csv`](aemo_2026_isp_cdp4_emissions_generation.csv), long format
`scenario,series,financial_year_ending,value,unit`, 216 rows covering financial years ending 2027 to 2050.

Sheet `Emissions`, titled "NEM Emissions (Mt CO2-e)", with header row "CDP, Region, Total, 2026-27, 2027-28, ..., 2049-50": one row per
region for each development path. The sheet carries no note, so it states no emissions scope. The `CDP4 (ODP)` rows for the five regions
are summed into the series "NEM emissions". The Step Change `CDP4 (ODP)` rows' 2029-30 cells, verbatim:

> ```text
> NSW 7.771673542395926, QLD 20.32747116852524, VIC 11.042241499188002, SA 0.09149100059309245, TAS 0
> ```

They sum to the extract's 39.233 Mt CO2-e for 2030.

Sheet `Generation`, titled "Annual as-generated generation by technology (GWh)", described on the workbook's `Index` sheet as "Annual
as-generated generation by technology for all cases": the `CDP4 (ODP)` rows summed into two series. "Storage and DSP net generation" sums the
technologies Utility-scale storage, Coordinated CER storage, Passive CER storage and DSP with the three matching storage loads; "Generation
excluding rooftop and storage" sums every other technology less "Rooftop and other small-scale solar". Both match the same series in
[`../aemo_scenario_cost/aemo_2026_isp_cdp4_costs_generation.csv`](../aemo_scenario_cost/aemo_2026_isp_cdp4_costs_generation.csv) to the
gigawatt hour.

The first Step Change rows of the extract, verbatim:

> ```text
> scenario,series,financial_year_ending,value,unit
> Step Change,NEM emissions,2027,102.024,Mt CO2-e
> Step Change,NEM emissions,2028,85.796,Mt CO2-e
> ```

## A001 -- Coal blend, 75% black and 25% brown by energy

CDP4 reports one Coal column, while the NGER cross-walk carries separate black (90.24) and brown (93.82) coal factors. The blend weight is
authored here and cited to no source. The two factors are within 4% of each other, so the blend moves the coal factor by at most 0.9% against
either pure coal, and the derived intensities by less than that.

## A002 -- Generation excluding rooftop as the denominator

Intensity is quoted per megawatt hour generated less rooftop photovoltaic output, following the convention
[`../demand_plan/plot_demand_trajectories.py`](../demand_plan/plot_demand_trajectories.py) already uses on these same files: behind-the-meter
rooftop output never crosses the NEM, so the remainder is the closest proxy these generation-basis files offer for grid-supplied energy. It
applies to the draft series only; the 2026 ISP overlay divides by operational demand instead (A006).

## A003 -- Distillate heat rate taken from small open-cycle gas turbines

The IASR heat rate table identifies units by technology, not by fuel, and CDP4 reports no liquid-fuelled technology class. Distillate
therefore takes the small open-cycle gas turbine median (S004), which is the plant class the NGER cross-walk names as the diesel-burning part
of the IASR fleet (S003). Distillate is zero in every CDP4 year of every scenario from 2030 on, so the choice changes no plotted number.

## A006 -- Operational demand as the 2026 ISP overlay's denominator

The 2026 ISP overlay divides AEMO's NEM emissions by operational demand, taken as generation excluding rooftop and storage plus the
(negative) storage and DSP net generation, both from S006. The campaign's `fleet_intensity`, which the overlay sits beside, is emissions per
megawatt hour delivered to the model's loads ([`../../sharp/method_years.py`](../../sharp/method_years.py)), and the same panel row's cost
and demand overlays use the same operational demand (A004 in [`../aemo_scenario_cost/`](../aemo_scenario_cost/)). The draft series keeps
its own generated denominator (A002), because the base chain's caps are read from it unchanged.
