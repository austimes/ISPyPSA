# REZ and transmission limits

## Purpose and scope

AEMO publishes a ceiling on how much renewable generation each renewable energy zone (REZ) may host and how much power each REZ corridor
may carry. In the deep carbon-cap chains those ceilings, not the generation technologies, are what the campaign runs out of first. The fork
therefore carries a single sensitivity switch, `rez_limit_factor`, that multiplies every REZ limit by one number so a second campaign run set
can show how much of the deep-cap cost sits in the ceilings rather than in the plant.

The switch lives in [`analysis/model/rez_limits.py`](../../model/rez_limits.py) and is applied to the templated ISPyPSA tables between the
templater and the translator. A factor of 1.0, or none at all, leaves every table exactly as the templater produced it.

## What the factor multiplies, and what it deliberately does not

| Table | Columns scaled | Effect |
|---|---|---|
| `renewable_energy_zones` | `rez_transmission_network_limit_summer_typical` | Each REZ link's PyPSA `p_nom` |
| `renewable_energy_zones` | `wind_generation_total_limits_mw_{high,medium,offshore_floating,offshore_fixed}`, `solar_pv_plus_solar_thermal_limits_mw_solar` | REZ resource-quality custom constraints |
| `renewable_energy_zones` | `land_use_limits_mw_wind`, `land_use_limits_mw_solar` | REZ land-use build-limit custom constraints |
| `rez_transmission_expansion_costs` | `additional_network_capacity_mw` | Headroom each REZ expansion option may add |
| `custom_constraints_rhs` | `rhs` for constraints whose left-hand side has `term_type == "link_flow"` | AEMO's REZ group and transmission-limit constraints |

Three exclusions matter for reading any relaxed run:

| Not scaled by `rez_limit_factor` | Consequence |
|---|---|
| Per-megawatt expansion costs | Relaxed capacity is still paid for at AEMO's published price, so the sensitivity changes the ceiling and not the price |
| Interconnector and intra-region flow paths | The corridors between sub-regions answer to a second factor, `flow_path_limit_factor` in [`flow_path_limits.py`](../../model/flow_path_limits.py), which scales `flow_path_expansion_costs.additional_network_capacity_mw` and nothing else. Templated corridor capacity is scaled by neither factor, so a run relaxed on REZ limits alone can still be bound by corridor expansion |
| Constraints summing generator or storage capacity | The fork's own caps (biomass, PHES site limits) keep their authored ceilings |

**confidence: high.** Every column in the table above is read directly from `_SCALED_COLUMNS` and `_scale_group_transmission_limits` in
`rez_limits.py`, and the flow-path row from `_CAPACITY_COLUMN` in `flow_path_limits.py`; nothing is inferred.

## What binds

The full enumeration is the limits inventory filed as S001: 296 numeric limits, of which 288 carry a binding flag against two reference
solves and 8 (the hydro annual budget and the biomass capacity cap by year) are marked unknown because the probe script that produced the
flags does not inspect those constraint families. A limit counts as binding when its solved left-hand side sits within 1% of its
right-hand side.

| Family | Limits enumerated | Binding in the deepest cap (2060 stress) | Binding in the 2050 central run |
|---|---:|---:|---:|
| REZ transmission: existing transfer and expansion limits | 56 | 18 | 18 |
| Flow paths: interconnector and intra-region expansion limits | 16 | 7 | 7 |
| REZ wind and solar resource and land-use build limits | 203 | 24 | 13 |
| Biomass supply-curve tranches | 4 | 1 | 2 |
| PHES shared-site limits | 9 | 0 | 1 |
| Conventional hydro annual energy budget | 2 | unknown | unknown |
| Biomass capacity cap by year | 6 | unknown | unknown |

The tightest ceilings by absolute headroom, all from S001:

| Limit | Value | Expansion cost (A$/MW, FY2029-30) | Binding in the deepest cap |
|---|---:|---:|---|
| `SESA-CSA` flow-path expansion | 120 MW | 699,811 | yes |
| `SWQLD1_expansion_limit` (Darling Downs) | 330 MW | 21,485 | yes |
| `SNSW-CNSW` flow-path expansion | 450 MW | 508,825 | yes |
| `CQ-NQ` flow-path expansion | 500 MW | 436,536 | yes |
| `NSA1` north South Australia transfer | 585 MW | 565,966 | yes |

Published per-megawatt expansion prices span two orders of magnitude, from 21,485 A$/MW at Darling Downs to 1,674,664 A$/MW at NQ1, so
which ceiling binds is not a good guide to what relaxing it would cost.

**confidence: high** for the enumerated limits and their binding flags, which are read from each run's own
`custom_constraints_rhs.csv` and `custom_constraints_lhs.csv`; **confidence: medium** for the binding rule itself, since a 1% tolerance on a
barrier solution can call a near-degenerate constraint either way.

## The relaxed run

The relaxation actually run doubled every REZ limit. The counts reported from that run are 28 REZ corridors and 14 land-use limits still
binding, together with interconnector expansion limits that the factor never touched.

**confidence: low.** These three counts come from a probe transcript that is not committed to this repository, and the corridor figure does
not reconcile with the committed inventory: the reported pre-relaxation corridor count is 42, while S001's tables carry 18 binding REZ
transmission constraints plus 7 binding flow-path expansion limits, or 25 in the deepest cap. The land-use figure does reconcile exactly
(24). The two corridor counts are counting different things: the 42 came from a run-time probe that listed every binding REZ group constraint
and every binding expansion constraint together, so one corridor can contribute a row from each family, while the inventory's 25 counts one
row per corridor. Both are recorded rather than one being preferred, because neither can be re-derived from the other without the probe
transcript. Treat the direction -- roughly a third of binding ceilings clear at 2x, the rest do not -- as the finding, not the counts.

## Plot

[`plot_binding_limits.py`](plot_binding_limits.py) draws binding counts by family for the deepest cap, with the probe-reported
post-relaxation counts alongside and labelled as unreconciled. It writes `binding_limits.html` and `binding_limits.png` beside itself.
