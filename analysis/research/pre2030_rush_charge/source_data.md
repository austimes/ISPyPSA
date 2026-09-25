# Pre-2030 rush charge -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- ShARP assumption A045, overflow-growth bands and the FY2030 short-lead-time adjustment

**Source:** `library/roles/generate_grid_electricity/assumptions_ledger.csv` in `austimes/sharp` at commit `eaf1ca27`,
read with `gh api repos/austimes/sharp/contents/<path>?ref=eaf1ca27`.

`assumption_statement`, verbatim:

> "Positive overflow-growth is charged through two annualised vintage bands: A$2.155449/MWh through 12 TWh/year and
> A$3.531277/MWh above 12 TWh/year; an additional A$37.447769/MWh applies only to growth installed in FY2030."

`rationale`, verbatim:

> "The persistent bands are provisional assumptions informed by one tenth of the lowest and highest later-year
> Constrained Delivery whole-system cost differences. Each positive clean-plus-gas increment carries its band price
> annually from installation through the solve horizon, with no refund if overflow later falls. The FY2030 adjustment
> makes the combined growth price A$39.603218/MWh for the renewable-target rush and expires after that year because
> persisting the full amount contradicts the later comparison. It represents insufficient lead time rather than an
> inherently special calendar year."

`sensitivity` is `exploratory`; `source_ids` are `["S050","S060"]` in ShARP's own ledger, AEMO grid-authoring guidance
from the 2026 ISP PLEXOS runs and a restricted AEMO scenario-workbook synthesis. Neither was read for this topic.

The same role's `README.md` at the same commit:

> "Growth ending in FY2030 also carries a one-year A$37.447769/MWh short-lead-time adjustment."

## S002 -- ShARP overflow-growth adjustment table

**Source:** `library/roles/generate_grid_electricity/overflow_supply_growth_adjustments.csv` at the same commit.

The one data row, verbatim fields:

> `installation_year` `2030`, `adjustment_id` `renewable_target_short_lead_time`, `overflow_growth_adjustment_per_unit`
> `37.447769`, `cost_basis_year` `2024`, `currency` `MAUD_2024`, `estimate_confidence` `exploratory`

`evidence_summary`, verbatim:

> "The 2030 adjustment represents the exceptional cost of increasing supply beyond plan quickly enough to reach the
> national renewable objective, after allowing for the annual cost already carried by the persistent overflow-growth
> estimate."

## S003 -- ShARP assumption A052, delivery factor

**Source:** the same assumptions ledger, row `A052`. Already quoted and used for the common basis in
[`../sharp_grid_reference/source_data.md`](../sharp_grid_reference/source_data.md) (S007 there). The part used here,
verbatim:

> "the existing geographic factor of 1.3 and delivery factor of 0.7914939324516337 establish planned output rounded
> once to 5 TWh."

## S004 -- AEMO draft 2026 ISP, Step Change CDP4 capacity and energy

**Source:** [`../../../iasr outputs/NEM-aemo2026draft-step_change-CDP4 (ODP)-capacity.csv`](../../../iasr%20outputs/)
and `NEM-aemo2026draft-step_change-CDP4 (ODP)-energy.csv` in this repository. Data tables, no quote. The rows used,
verbatim (columns `date`, `Demand Response`, `Coal`, `Bioenergy`, `Distillate`, `Gas`, `Hydro`, `Wind`,
`Solar (Utility)`, `Solar (Rooftop)`):

| File | Row |
| ---- | --- |
| capacity | `"1 Jan 2026 12:00 am","0","21","0","0","11","7","11","9","25"` |
| capacity | `"1 Jan 2030 12:00 am","1","13","0","0","12","7","26","32","36"` |
| energy | `"1 Jan 2026 12:00 am","0","111","0","0","8","15","37","20","30"` |
| energy | `"1 Jan 2030 12:00 am","0","43","0","0","3","14","81","68","45"` |

## S005 -- Campaign base chain of run 2026-09-22T22.46_sc5, 2030 period

**Source:** `outputs/2026-09-22T22.46_sc5/exports/results.csv` and `exports/storage.csv` under the campaign `IO_DIR`,
rows for cell `ext_step_change_sc`, year 2030. Model output, no quote.

| Field | Value |
| ----- | ----: |
| `twh_Battery` | 12.016 |
| `new_gw_Battery` | 0.000 |
| Battery `power_gw`, summed over duration classes | 14.59 |
| Battery `energy_gwh`, summed over duration classes | 41.62 |
