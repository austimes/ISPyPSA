# AEMO scenario cost intensity -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv); authored assumption ids
match [`assumptions_ledger.csv`](assumptions_ledger.csv).

## S001 -- AEMO 2026 ISP generation and storage outlook, CDP4 costs and generation

**Source:** AEMO's final 2026 ISP "2026 ISP generation and storage outlook", published 25 June 2026 at
<https://www.aemo.com.au/energy-systems/major-publications/integrated-system-plan-isp/2026-integrated-system-plan-isp> as
`2026-isp-generation-and-storage-outlook.zip`. Three workbooks inside it were read, one per scenario:

- `Core scenarios/2026 ISP - Step Change - Core.xlsx`
- `Core scenarios/2026 ISP - Slower Growth - Core.xlsx`
- `Core scenarios/2026 ISP - Accelerated Transition - Core.xlsx`

The zip is not tracked in this repository; the rows used are extracted to
[`aemo_2026_isp_cdp4_costs_generation.csv`](aemo_2026_isp_cdp4_costs_generation.csv), long format
`scenario,series,financial_year_ending,value,unit`, 1,224 rows covering financial years ending 2027 to 2050.

Sheet `Costs`, titled "Annual costs by class ($000s)": the `CDP4 (ODP)` rows, 14 cost classes. The sheet's note, verbatim:

> "Real July 2023 dollars. Flow path augmentation costs include capital and operating expenditure. Capital costs are annualised for
> modelling purposes. Some rounding errors may be present."

The 14 classes, as extracted: generation, storage and electrolyser capital, FOM, VOM and retirement costs; fuel costs; DSP+USE costs;
flow path capital and O&M costs; REZ capital and O&M costs; distribution capital and O&M costs; system security costs; emissions costs.

Sheet `Capacity`, titled "Installed Generator Capacity by Technology" (MW), note verbatim: "Capacity calculated on 1 July. In early
study years some wind and solar projects enter later in the financial year and are reflected in the following financial year's
capacity." Its `CDP4 (ODP)` rows sum to the same 2029-30 wind, utility solar and utility storage capacity as S006.

Sheet `Generation`, titled "Annual as-generated generation by technology (GWh)": the `CDP4 (ODP)` rows summed into three series,
"Generation excluding rooftop and storage", "Rooftop and other small-scale solar generation" and "Storage and DSP net generation".

The first Step Change rows of the extract, verbatim:

> ```text
> scenario,series,financial_year_ending,value,unit
> Step Change,"Generation, storage and electrolyser capital costs",2027,36386,$000 real Jul-2023
> Step Change,"Generation, storage and electrolyser capital costs",2028,427762,$000 real Jul-2023
> ```

## S002 -- IASR workbook dollar basis

**Source:** sheet "Assumptions Summary" of the AEMO 2026 ISP inputs and assumptions workbook,
`2026-isp-inputs-and-assumptions-workbook.xlsm`, in the input package on the data share (path resolved by
[`../../env.py`](../../env.py) as `Env.iasr_workbook`). The campaign's costs are built from this workbook. Verbatim:

> "All values in this workbook are as at 30 June 2025 real dollars except were explicitly noted otherwise."

The "Build costs" sheet heading agrees, verbatim: "Capital cost projections ($/kW, real 2025 dollars)".

## S003 -- ABS Consumer Price Index, All groups, weighted average of eight capital cities

**Source:** Australian Bureau of Statistics (ABS), Consumer Price Index, Australia: quarterly index numbers, All groups CPI, original
series, weighted average of eight capital cities (series A2325846C). Read through the ABS data API at
<https://data.api.abs.gov.au/rest/data/ABS,CPI,1.1.0/1.10001.10.50.Q?startPeriod=2023-Q1>, whose dimension codes decode, from the same
API's code lists, to "Index Numbers", "All groups CPI", "Original" and "Weighted average of eight capital cities". The rows used,
verbatim:

> ```text
> DATAFLOW,MEASURE,INDEX,TSEST,REGION,FREQ,TIME_PERIOD,OBS_VALUE,UNIT_MEASURE,OBS_STATUS,DECIMALS,OBS_COMMENT
> ABS:CPI(1.1.0),1,10001,10,50,Q,2023-Q2,133.7,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q1,137.4,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q2,138.8,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q3,139.1,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2024-Q4,139.4,IN,,1,
> ABS:CPI(1.1.0),1,10001,10,50,Q,2025-Q2,141.7,IN,,1,
> ```

The 2024 quarters are used by the ShARP reference in [`../sharp_grid_reference/`](../sharp_grid_reference/); this topic uses the June
quarters of 2023 and 2025.

## S004 -- IASR workbook price index

**Source:** sheet "Change Log" of the same IASR workbook as S002. AEMO names the index it rebases dollar years with, verbatim:

> "Australian dollars have been updated from $ 2019 to $ 2020 using All groups CPI index values - June 2020 from the Australian Bureau of
> Statistics"

## S005 -- 2026 ISP, costs counted in the optimal development path

**Source:** AEMO, *2026 Integrated System Plan for the National Electricity Market*, June 2026,
<https://www.aemo.com.au/-/media/files/major-publications/isp/2026/2026-integrated-system-plan-isp.pdf>. Page 115, "ISP Explainer:
Calculating the ODP's benefits and costs", verbatim:

> "Existing, committed and anticipated investment decisions are not costed or re-evaluated, as they do not affect future planning."

> "Similarly, capital costs of committed and anticipated projects are common to all potential development paths and therefore do not
> affect the cost-benefit analysis."

Page 117, verbatim:

> "some generation, storage and transmission projects have progressed to become 'committed', 'anticipated' or 'policy-supported'
> projects, so $48 billion is excluded in the costs of the 2026 ODP."

## S006 -- 2026 ISP chart data, Step Change capacity

**Source:** AEMO 2026 ISP chart data workbook, `2026-isp-chart-data.xlsx`, sheet "Figure 1", titled "NEM capacity (GW, 2010 to 2050,
Step Change, financial year ending)", values in MW. The 2029-30 column, verbatim: "Onshore wind" 29818.2, "Utility solar" 31188.8,
"Utility storage" 35779.8. Sheet "Figure 20" splits utility storage into Snowy 2.0 (2.202 GW), deep, medium and shallow storage; medium
and shallow storage together are 33.3 GW in 2029-30.

## S007 -- ISP Methodology, time sampling and reliability

**Source:** AEMO, *ISP Methodology*, June 2025,
<https://www.aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2024/2026-isp-methodology/isp-methodology-june-2025.pdf>.
Verbatim:

> "The SSLT uses the "sampled" chronology setting which preserves a specified number of periods (typically day(s) per month
> or week(s) per year) for modelling." (p.41)

> "'Sampled' and 'fitted' chronology settings are used for the SSLT and DLT models, respectively" (p.41)

> "AEMO uses a 'rolling reference years' approach in the capacity outlook models." (p.26)

> "If the time-sequential models show the reliability standard is being exceeded, then the reserve levels are increased." (p.44)

> "The time-sequential model optimises electricity dispatch for every hourly or half-hourly interval" (p.61)

## A001 -- Generation excluding rooftop and storage as the denominator

The drawn measure divides by generation excluding rooftop and storage. Rooftop output never crosses the NEM, and storage and DSP net
generation is a small negative number (storage round-trip losses) that would otherwise net against grid supply. The same rooftop exclusion
is used for the emissions overlay in [`../aemo_scenario_intensity/`](../aemo_scenario_intensity/).

## A002 -- Dollar year converted by the ABS All groups CPI

AEMO's costs are in real July 2023 dollars (S001) and the campaign's in real 30 June 2025 dollars (S002). The common-basis cost multiplies
by the June quarter 2025 index over the June quarter 2023 index, 141.7 / 133.7 = 1.0598 (S003), the index AEMO itself names (S004). July
2023 dollars are taken as the June quarter 2023 index, the quarter that ends the day before; the September quarter (135.3) would lower the
factor to 1.047.

## A003 -- Cost classes the campaign does not model

The common-basis cost also leaves out generation, storage and electrolyser retirement costs, system security costs and distribution
capital and O&M costs. The campaign's model carries no counterpart for any of the four. Flow path, REZ, and DSP and unserved energy costs
stay in, because the campaign builds transmission and REZ capacity and prices unserved energy.

## A004 -- Operational demand as generation net of storage losses

Operational demand is taken as each scenario's generation excluding rooftop and storage plus its (negative) storage and DSP net
generation, both from S001, per year: the demand plan's measured factor ([`../demand_plan/`](../demand_plan/), A010 there). The ratio
is carried as `operational_share` and sets both `operational_demand_twh` and the common-basis cost's denominator. AEMO publishes no
such factor.
