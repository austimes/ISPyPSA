# Conventional hydro energy budget -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- AEMO 2026 ISP Step Change modelled hydro generation

**Source:** AEMO workbook "Annual generation and emissions 2026 ISP.xlsx", sheet `SC Gen`, column `Hydro`, sensitivity `FP20403_260508a`.

No verbatim quote is available: no local copy of this workbook exists in or beside this repository. The citation above is quoted verbatim
from the code that carries the transcribed numbers, under S002.

The transcribed series is the 24-entry `_HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY` dictionary reproduced as TWh in `research.md`, from
16,669,580 MWh at FY2027 to 9,833,820 MWh at FY2050. Pumped hydro energy storage is reported separately in that workbook and is modelled
separately here as storage units, so it is not inside this budget.

## S002 -- The budget and ceiling as implemented

**Source:** [`src/ispypsa/pypsa_build/generators.py`](../../../src/ispypsa/pypsa_build/generators.py).

On why a budget is needed at all, verbatim:

> "`_HYDRO_MONTHLY_CF` above is only a ceiling on instantaneous output; paired with hydro's near-zero marginal cost, the LP dispatches Water
> generators at ~that ceiling in almost every hour, which overstates annual hydro generation because real hydro is water-limited, not just
> capacity-limited."

On the source of the budget, verbatim:

> "Source: AEMO 2026 ISP Step Change modelled conventional-hydro generation ("Annual generation and emissions 2026 ISP.xlsx", sheet 'SC Gen',
> column 'Hydro', sensitivity FP20403_260508a; PHES is reported separately in that workbook and is modelled separately here as StorageUnits).
> The trajectory declines from ~16.7 TWh (2027) to ~9.8 TWh (2050)."

On the region-filter skip, verbatim:

> "Each figure is a NEM-wide annual total, so it only describes a network that covers the whole NEM. A run filtered to a subset of regions
> models only part of the hydro fleet, and applying the NEM-wide total to it would leave that fleet effectively uncapped, so the constraint is
> skipped on such runs."

And from the constraint function's own docstring:

> "The budget is a NEM-wide annual total and the NEM-wide hydro capacity it belongs to is not recoverable from the pypsa-friendly tables,
> which are already region-filtered, so the budget cannot be scaled to the modelled share of the fleet. It is therefore skipped, with a
> warning, whenever the caller reports that the run models only a subset of regions."

On the clamping rule, verbatim from `_hydro_annual_budget_mwh`:

> "AEMO SC hydro budget for a financial year, clamped to the published 2027-2050 range (a 2025/2026 chain period uses the 2027 value)."

## S003 -- AEMO Generation Information, monthly hydro generation

**Source:** AEMO Generation Information, NEM monthly hydro generation, long-run averages.

No verbatim quote is available: no local copy exists in or beside this repository. What the code states about its use is quoted below,
under S002's file:

> "Values derived from AEMO Generation Information NEM monthly hydro generation (long-run averages, NSW + Tas hydro dominate the fleet).
> Annual mean of ~0.37, inside the realistic 30-45% CF band for Australian conventional hydro."

The per-month capacity factors themselves are not attributed to a specific published table in the code, so they are recorded as an authored
shape in the assumptions ledger rather than as a sourced series.
