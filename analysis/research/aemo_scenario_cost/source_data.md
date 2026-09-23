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

## A001 -- Generation excluding rooftop and storage as the denominator

The drawn measure divides by generation excluding rooftop and storage. Rooftop output never crosses the NEM, and storage and DSP net
generation is a small negative number (storage round-trip losses) that would otherwise net against grid supply. The same rooftop exclusion
is used for the emissions overlay in [`../aemo_scenario_intensity/`](../aemo_scenario_intensity/).

## A002 -- Dollar year left unconverted

AEMO's costs are in real July 2023 dollars (S001) and the campaign's in real 30 June 2025 dollars (S002). The overlay is drawn as
published, with no inflation factor: no consumer price index series is tracked in this repository, so any factor would be an uncited
number. Two years of inflation is a few per cent, small beside the gap between scenarios, so the band still reads correctly as a range.
