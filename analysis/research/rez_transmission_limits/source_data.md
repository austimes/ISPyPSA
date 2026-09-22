# REZ and transmission limits -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- Limits inventory with binding flags

**Source:** working note `rez_transmission_limits.md`, held outside this repository. It enumerates every REZ, flow-path, biomass, PHES,
hydro and unserved-energy limit the campaign enforces, with a proposed relaxed value for each, and flags which were binding in two
reference solves.

On what it covers:

> "Numeric limits (AEMO 2026 ISP Inputs, Assumptions and Scenarios Report, IASR, values) that the ISPyPSA extension campaign enforces on
> renewable energy zones (REZ) and transmission, with a proposed relaxed value for each, for a sensitivity that tests whether the deep-CO2-cap
> load shedding seen in the 2060 stress run disappears once these limits are relaxed."

On the binding rule and the two reference runs:

> "Binding-constraint lists | `/scratch3/wes148/limits_probe.py`, run against `ext_stress_cap00005_2060__cost_optimal` and
> `ext_central_cap0001_2050__cost_optimal` (binding = solved LHS within 1% of RHS)"

On the proposal rule:

> "every limit found binding (its solved value sits within 1% of its right-hand side, RHS) in either reference run gets two proposed values
> to test in sequence: **2x the IASR value** as the first sensitivity, and **unbounded** (limit removed) as a diagnostic upper bound."

On what the note could not settle, verbatim from its footer:

> "Binding status for the NEM-wide hydro annual energy budget and the `biomass_cap_<year>` constraint could not be read from the
> `limits_probe.py` console output supplied"

The per-family counts in `research.md` were recomputed from this note's own tables rather than taken from prose: 56 REZ transmission rows,
16 flow-path rows, 203 REZ resource and land-use rows, 4 biomass tranche rows, 9 PHES site rows, 2 hydro budget rows and 6 biomass capacity
cap rows, for 296 limits in total.

## S002 -- The relaxation switch as implemented

**Source:** [`analysis/model/rez_limits.py`](../../model/rez_limits.py), verbatim from its module docstring:

> "AEMO's REZ limits are the binding ceiling on renewable build in the deep-cap chains: a chain held to a 0.005 t CO2e/MWh 2050 intensity
> runs out of REZ transmission capacity and REZ wind and solar resource before it runs out of candidate projects."

On the exclusion of price from the relaxation:

> "The per-MW expansion costs are untouched, so relaxed capacity is still paid for at AEMO's published price."

On the exclusion of the backbone:

> "Interconnector flow paths are deliberately left alone: this sensitivity is about REZ headroom, not about the transmission backbone between
> sub-regions."

And the scaled-column constant itself, verbatim:

> ```python
> _SCALED_COLUMNS = {
>     "renewable_energy_zones": [
>         "rez_transmission_network_limit_summer_typical",
>         "wind_generation_total_limits_mw_high",
>         "wind_generation_total_limits_mw_medium",
>         "wind_generation_total_limits_mw_offshore_floating",
>         "wind_generation_total_limits_mw_offshore_fixed",
>         "solar_pv_plus_solar_thermal_limits_mw_solar",
>         "land_use_limits_mw_wind",
>         "land_use_limits_mw_solar",
>     ],
>     "rez_transmission_expansion_costs": ["additional_network_capacity_mw"],
> }
> ```

## S003 -- AEMO 2026 IASR REZ and flow-path tables

**Source:** the templated ISPyPSA inputs each run writes to `ispypsa_inputs/`: `renewable_energy_zones.csv`, `flow_paths.csv`,
`flow_path_expansion_costs.csv` and `rez_transmission_expansion_costs.csv`, all derived from the AEMO 2026 IASR workbook.

No verbatim quote is available: these are generated CSV extracts of a spreadsheet, and neither the run directories nor the workbook are in
this repository. Their values reach `research.md` only through S001's tabulation of them.

## S004 -- Probe counts from the doubled-limit run

**Source:** a probe of a run set solved with `rez_limit_factor = 2`.

No verbatim quote is available and no transcript is committed. The reported counts are 42 REZ corridors and 24 land-use limits binding
before relaxation, and 28 and 14 respectively still binding afterwards, with interconnector expansion limits also still binding. Only the
land-use figure of 24 reconciles with S001; the corridor figure does not, and `research.md` records that discrepancy rather than choosing
between them.
