# Biomass -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- National Greenhouse Accounts Factors 2024

**Source:** [National Greenhouse Accounts Factors 2024](https://www.dcceew.gov.au/sites/default/files/documents/national-greenhouse-account-factors-2024.pdf),
Department of Climate Change, Energy, the Environment and Water, Table 4, fuel "Primary solid biomass fuels other than those mentioned in
the items above". The underlying legal basis is the National Greenhouse and Energy Reporting (Measurement) Determination 2008, Schedule 1.

No verbatim quote is available: no local copy of this document exists in or beside this repository. The cross-walk that reads it is quoted
under S002.

## S002 -- Carrier emission-factor cross-walk

**Source:** [`analysis/sharp/nger_factors.py`](../../sharp/nger_factors.py).

On the biomass row, verbatim:

> "\"Biomass\" -> NGA \"Primary solid biomass fuels other than those mentioned in the items above\" (Table 4). CO2 is biogenic (zero);
> CH4 + N2O combustion residuals only."

The factor table itself, verbatim:

> ```python
> "Biomass": (0.0, 0.8, 1.0, "Table 4", "Primary solid biomass fuels"),
> ```

read as carbon dioxide, methane as carbon dioxide equivalent, and nitrous oxide as carbon dioxide equivalent, all in kg CO2e/GJ on a gross
calorific value basis. On the units and weighting, verbatim:

> "All factors are Scope 1 (direct combustion), in kg CO2-e per GJ on a Gross Calorific Value basis. CO2 / CH4 / N2O are reported separately
> (in CO2-e units already, i.e. multiplied by AR5 GWP-100); the \"combined\" column is their sum."

The matching constant on the modelling side, verbatim from
[`src/ispypsa/translator/mappings.py`](../../../src/ispypsa/translator/mappings.py):

> ```python
> "Biomass": 1.8,  # biogenic CO2; CH4 + N2O combustion residuals
> ```

## S003 -- The carbon cap constraint

**Source:** [`analysis/hpc/instrumented_runner.py`](../../hpc/instrumented_runner.py), verbatim:

> "Absolute annual CO2e cap on generation combustion. Coefficients are the translator's isp_residual_co2_t_per_mwh (carrier total Scope-1
> CO2e factor x heat rate x (1 - capture_rate)), so CCS residual emissions at the configured capture rate are INSIDE the cap and captured CO2
> is not."

Because the constraint selects every generator whose residual is above zero, the biomass 1.8 kg CO2e/GJ factor puts biomass inside the cap.

## S004 -- Biomass supply curve

**Source:** [`analysis/model/data/biomass_supply_curve_central_held_to_2060.csv`](../../model/data/biomass_supply_curve_central_held_to_2060.csv),
verbatim header and first tranche block:

> ```text
> tranche,financial_year,cap_pj,adder_$/gj
> existing_industry_byproduct,2025,30.0,0.0
> collected_residues,2025,5.0,5.5
> energy_crops,2025,0.0,10.0
> imported_pellet_backstop,2025,,15.0
> ```

The blank `cap_pj` on the backstop row is what makes it unbounded. No file in this fork states where the tranche sizes, their ramp rates or
their price adders came from; the filename's "central" and "held to 2060" describe the shape, not a source.

## S005 -- Biomass capacity cap

**Source:** [`analysis/model/biomass_cap.py`](../../model/biomass_cap.py).

On why the cap exists, verbatim:

> "The IASR-default biomass economics ($0.66/GJ fuel cost, unconstrained p_max_pu=1.0) make biomass structurally the cheapest firm-capacity
> option whenever coal is retired without a storage mandate, which drove biomass dispatch to tens of times current Australian consumption in
> early production runs."

On the 2050 value, verbatim:

> "At ~90 % CF the 2050 cap of 5 GW corresponds to ~39 TWh annual generation -- still optimistic relative to the ~5-15 TWh range AEMO/industry
> projections suggest, but a defensible ceiling given the data available."

On its stated sources, verbatim:

> "Sources:
>   - ARENA Bioenergy Roadmap 2021 -- 4-7 GW upper-bound for bioenergy-for-electricity by 2050 across all bioenergy categories.
>   - AEMO ISP 2024 Step Change technology projections -- modest biomass deployment baseline (<1 GW capacity through 2050).
>   - Clean Energy Council 2024 Australian Renewable Energy Investment Report -- current Australian biomass-for-electricity capacity ~1 GW."

None of the three is cited to a page or table, and none of the three documents is present in or beside this repository, so no verbatim quote
from them is available.

On the acknowledged limitation, verbatim:

> "This is a CAPACITY cap, not a strict fuel-availability cap. A methodologically rigorous approach would constrain annual generation (TWh)
> directly via a snapshot-weighted Generator.p sum constraint."

## S006 -- Tranche usage in the probed runs

**Source:** the limits inventory described in [`../rez_transmission_limits/source_data.md`](../rez_transmission_limits/source_data.md), plus
a probe transcript that is not committed.

From the inventory, verbatim:

> "`existing_industry_byproduct` (30 PJ, no cost adder) was at its cap (binding) in both reference runs, `collected_residues` was additionally
> binding (90 PJ cap) in the 2050-central run only."

The additional 2.5 PJ of `collected_residues` drawn in the deepest-cap run is reported from the probe transcript. No verbatim quote is
available for it and the transcript is not committed.
