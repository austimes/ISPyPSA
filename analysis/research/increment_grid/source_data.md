# Increment grid -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv);
authored assumption ids match [`assumptions_ledger.csv`](assumptions_ledger.csv).

## S001 -- The increment grid block

**Source:** [`analysis/hpc/demand_plan.json`](../../hpc/demand_plan.json), verbatim:

> ```json
> "increment_grid": {
>   "demand_levels": {
>     "d060": 0.6, "d080": 0.8, "d100": 1.0, "d120": 1.2,
>     "d140": 1.4, "d160": 1.6, "d180": 1.8, "d200": 2.0
>   },
>   "intensity_levels": {
>     "i2000": 2.0, "i1000": 1.0, "i0410": 0.41, "i0170": 0.17,
>     "i0070": 0.07, "i0030": 0.03, "i0012": 0.012, "i0005": 0.005
>   },
>   "cells": "all"
> }
> ```

The per-year cap intensity and source load the grid scales, also verbatim:

> ```json
> "cap_intensity_t_per_mwh": {
>   "2030": 0.19673, "2035": 0.0645, "2040": 0.04136,
>   "2045": 0.02714, "2050": 0.01385, "2055": 0.01385, "2060": 0.01385
> },
> "cap_intensity_basis": "source",
> "demand_paths_source_twh": {
>   "iasr_step_change": {
>     "2030": 202.73, "2035": 246.38, "2040": 282.27,
>     "2045": 307.49, "2050": 322.04, "2055": 341.9, "2060": 361.8
>   }
> }
> ```

The 2030 pipeline settings the corner-behaviour expectations cite, verbatim:

> ```json
> "pipeline_period": 2030,
> "new_entrant_cap_mw_by_year": {"2026": 0, "2030": 20500},
> "new_entrant_storage_cap_mw_by_year": {"2026": 0, "2030": 5100},
> "pipeline_rush_ceiling_mw": {"generation": 41000, "storage": 10200}
> ```

## S002 -- Increment cell arithmetic

**Source:** [`analysis/hpc/increments.py`](../../hpc/increments.py). On what one cell is, verbatim:

> "One increment solve: a snapshot year at one demand level and one intensity level."

On how a cell's trajectory and source load are built, verbatim from `_cell`:

> ```python
> return Cell(
>     trajectory=f"{name}_b{year}_{demand_level}",
>     year=year,
>     demand_level=demand_level,
>     demand_factor=demand_factor,
>     intensity_level=intensity_level,
>     intensity_factor=grid["intensity_levels"][intensity_level],
>     source_twh=knots[str(year)] * demand_factor,
> )
> ```

On what `"cells": "all"` means, verbatim from `cell_levels`:

> "The grid's (demand level, intensity level) pairs: the full product for `"all"`, else the listed pairs."

## S003 -- Branch chain naming and cap arithmetic

**Source:** [`analysis/hpc/manifest.py`](../../hpc/manifest.py). On the branch chain's key, verbatim:

> "Chain key of one increment cell: its own annual intensity as a cap key."

```python
def _branch_key(plan: dict, cell: increments.Cell) -> str:
    return cap_key(_base_intensity(plan, cell.year) * cell.intensity_factor)
```

On the branch row's seeding, verbatim from `_branch_chain_row`'s docstring:

> "One increment cell: a single-year solve seeded from the base chain's earlier state."

## S004 -- Cap key formatting

**Source:** [`analysis/hpc/campaign_grid.py`](../../hpc/campaign_grid.py), verbatim:

> "Chain key for a cap intensity, the inverse of `parse_pressure`: 0.0645 -> `cap00645`."

```python
def cap_key(intensity: float) -> str:
    return "cap" + f"{intensity:g}".replace(".", "")
```

## S005 -- Level-key decode convention

**Source:** [`analysis/dashboard/figures.py`](../../dashboard/figures.py), verbatim:

> "A level key names a percentage of the base cell's own, prefixed by the axis it varies: `d135` is 1.35 times its
> demand and `i010` a tenth of its cap. The digits are the capture group."

```python
INCREMENT_LEVEL_PATTERN = r"^[a-z](\d+)$"
```

## S006 -- ShARP futures demand band

**Source:** [`analysis/research/sharp_grid_reference/research.md`](../sharp_grid_reference/research.md), the
common-basis table under "Common basis with the campaign's measure". Planned demand and futures range, terawatt-hours
(TWh), for the years where the band sits furthest from plan:

| Year | Planned demand (TWh) | Futures range (TWh) | Low / plan | High / plan |
|---|---:|---|---:|---:|
| 2040 | 274.8 | 210.5 to 352.8 | 0.766 | 1.284 |
| 2060 | 347.6 | 301.8 to 571.9 | 0.868 | 1.645 |

On how the band is built, verbatim:

> "The futures range spans the six grid methods in S001: the two current-policy methods share one quantity path, the
> incumbent and delayed-with-gas futures set the floor from 2030 on, and the early near-zero future sets the ceiling
> (A010)."

## S007 -- Near-term pipeline allowance

**Source:** [`analysis/research/near_term_pipeline/research.md`](../near_term_pipeline/research.md). Its own settings
table, verbatim rows:

> "New-entrant generation allowance, 2030 | 19,000 MW, A003; 13,000 MW once the restored generators have traces, A010
> | One NEM-wide cap over every `New Entrant` generator in the 2030 solve"
>
> "New-entrant storage allowance, 2030 | 0 MW on the corrected battery roster, A009 | One NEM-wide cap over every
> `New Entrant` battery in the 2030 solve"

These figures are read from an earlier plan version than the one in [S001](#s001----the-increment-grid-block); the
plan's own `new_entrant_cap_mw_by_year` and `new_entrant_storage_cap_mw_by_year` for 2030 are the figures this topic
uses.

## S008 -- Pre-2030 rush ceiling

**Source:** [`analysis/research/pre2030_rush_charge/research.md`](../pre2030_rush_charge/research.md), verbatim rows:

> "Generation above the allowance | up to the 26,000 MW hard ceiling | 71,400"
>
> "Storage above the allowance | up to the 6,000 MW hard ceiling | 24,900"

As with S007, these ceilings are read from an earlier plan version; the plan's own `pipeline_rush_ceiling_mw` for
2030 is the figure this topic uses.

## S009 -- REZ and corridor binding-limit inventory

**Source:** [`analysis/research/rez_transmission_limits/research.md`](../rez_transmission_limits/research.md). On the
relaxed run doubling every limit, verbatim:

> "The relaxation actually run doubled every REZ limit. The counts reported from that run are 28 REZ corridors and 14
> land-use limits still binding, together with interconnector expansion limits that the factor never touched."

On how to read that finding, verbatim:

> "Treat the direction -- roughly a third of binding ceilings clear at 2x, the rest do not -- as the finding, not the
> counts."

The near-term pipeline topic's own reference run used a larger relaxation than the probed 2x, named in its run
directory, verbatim: `outputs/2026-09-21T16.08_ext41_rezx4_corrx4` (S007).

## S010 -- Biomass residual emissions under a deep cap

**Source:** [`analysis/research/biomass/research.md`](../biomass/research.md), verbatim:

> "Biomass fuel drawn under the 0.0005 ladder in the probed run | 30 PJ byproduct at its cap, plus 2.5 PJ of residues
> | 32.5 PJ"
>
> "Residual emissions from that fuel | 32.5e6 GJ x 1.8 kg CO2e/GJ | 58,500 t CO2e"
>
> "The cap that run was held to at 2060 | 0.0001 t/MWh on the source basis x 568.4 TWh | 56,840 t CO2e"

That probe used an earlier cap ladder (0.0001 t/MWh at 2060) and a different demand trajectory (`iasr_stress`) than
this topic's `i0005` level (0.0000693 t/MWh at 2060 on the base chain's own load), so only the scale of the finding,
not the exact percentage, is carried into this topic's corner-behaviour expectation.

## S011 -- Unserved-energy price and acceptance rule

**Source:** [`analysis/research/carbon_caps/research.md`](../carbon_caps/research.md), verbatim:

> "Unserved energy cost | 10,000 A$/MWh | An emergency price, far above any generator's marginal cost, so the solver
> sheds only when nothing else will serve the load"
