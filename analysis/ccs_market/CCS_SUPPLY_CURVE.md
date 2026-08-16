# A CO2 transport-and-storage supply curve for CCS-gas — research basis, design, and implementation

Companion to [`CCS_TNS_SOURCING.md`](../calibration/CCS_TNS_SOURCING.md) (cost basis)
and [`CCS_CAP_AND_DECISION.md`](../calibration/CCS_CAP_AND_DECISION.md) (project
pipeline, fleet geography, decision surface). Those two are adopted as inputs and are
not re-derived here.

Structural sibling of [`GAS_SUPPLY_CURVE.md`](../gas_market/GAS_SUPPLY_CURVE.md) and
[`BIOMASS_SUPPLY_CURVE.md`](../bioenergy_market/BIOMASS_SUPPLY_CURVE.md), and mirrors
their document structure. It differs from both in one important way, stated in §7: its
data basis is much thinner.

---

## 1. The problem: free, unlimited CO2 disposal

ISPyPSA prices a CCS-gas generator's fuel, VOM and residual (post-capture) carbon, and
then lets it dispose of the captured tonnes at zero cost, in unlimited quantity,
anywhere in the NEM. There is no transport cost, no storage cost, and no injectivity
constraint.

The consequences are visible in the solved `vrefix_gbc_c550_2050` network:

- **9.80 GW / 28.27 TWh / 11.85 Mt CO2 captured per year**, carrying ~90% of the
  residual 6.97 pp gas-share gap to AEMO's published 0.7-5.0% band.
- **57% of that CO2 is at Sydney**, a sub-region whose own basin was ruled out by the
  NSW CO2 Storage Assessment Program, and **10% is in Queensland**, where greenhouse-gas
  storage across the Great Artesian Basin has been prohibited by statute since June 2024.
- The siting is not forced. `CCGT with CCS` is offered in all 15 sub-regions; the LP
  *chooses* NSW, precisely because disposal there costs nothing.

This is the same defect the gas curve addressed for fuel: a scarce, spatially
differentiated input priced as free and unlimited. It is also, for the avoidance of
doubt, **AEMO's own treatment** — the 2026 ISP states it "does not include the costs of
establishing CCS transport and storage infrastructure" and applies no CO2 storage
constraint anywhere. That is why the uncurved configuration is retained as the
AEMO-comparability reference rather than deleted.

A flat scalar `tns_price` was the previous partial answer. It is superseded here,
because a scalar is blind to the two things that actually matter: **where** the CO2 has
to go, and **how much** can be injected at all.

---

## 2. Consistency with energy-economics practice

Pricing CO2 disposal as a transport-plus-storage chain with a quantity limit at the sink
is the standard treatment in CCS-capable capacity-expansion models. It is what
NETL/IECM, the JRC's CO2 infrastructure work and the ETI's UK storage appraisal all do:
a source-sink matching problem where transport is distance-priced and injection is
rate-limited per site.

The structure chosen here follows the same split:

- **Injectivity is the shared scarce resource, so quantity tranches live at the sinks.**
  Two generators competing for the same reservoir compete for the same tonnes per year.
- **Transport is a per-generator price adder**, because pipeline cost is a property of
  the source-sink pair, not of the sink.

This is the standing design decision recorded in the brief and is implemented as
specified. It is a deliberate simplification of a true source-sink network: each bus is
assigned to exactly one sink (§4), rather than being allowed to bid into any sink at a
pair-specific price. §7 states what that costs.

---

## 3. Sink basis

### 3.1 Which sinks are admitted

| basin / project | admitted? | reason |
|---|---|---|
| **Cooper hub (Moomba, SA)** | **yes** | Operating host, published third-party pathway |
| **CarbonNet (Pelican, Gippsland offshore VIC)** | **yes** | Published nameplate and schedule, government proponent |
| **Otway hub (Beach Energy, VIC)** | **yes** | Published nameplate |
| Surat / Denison / Bowen (QLD) | **no — prohibited** | Greenhouse-gas storage and GHG-stream enhanced recovery banned across the Queensland Great Artesian Basin by the Mineral and Energy Resources and Other Legislation Amendment Act 2024 (Qld), passed 12 June 2024, assented 18 June 2024. Existing GHG exploration permits cancelled; the GAB declared unavailable land for future applications |
| SEA CCS (Bream, Gippsland) | **no — withdrawn** | ExxonMobil withdrew the referral March 2025 and is decommissioning Bream A under a NOPSEMA order. The decision memo carried it in its optimistic case with a flag; this curve drops it |
| Darling Basin (NSW) | **no — no rate** | ~555 Mt modelled static capacity from 3 wells, no injectivity testing, no proponent. **No Mt/yr rate has ever been published.** Converting static capacity to a rate would be fabrication |
| Sydney Basin (NSW) | **no — ruled out** | NSW CO2 Storage Assessment Program, 4 wells: "limited geological storage potential in these locations" |
| Bass Basin (TAS/VIC) | **no — no project** | 2023 Commonwealth offshore GHG acreage release only; no award has progressed to a project |
| Arckaringa (SA) | **no — no nameplate** | Listed in GA AECR 2025 Table 8.1 with capacity not stated |

**Moomba CCS Phase 1's demonstrated ~1.3 Mt/yr is not in the Cooper tranche.** It is
fully committed to Santos's own Cooper Basin raw-gas CO2, is defined as an abatement
project on that stream, and earns ACCUs on that basis. Only the announced *third-party*
pathway is available to power.

### 3.2 The tranche quantities

Physical anchors, before any haircut, carried from `CCS_CAP_AND_DECISION.md` §2.4:

| sink | Mt/yr anchors | source | status |
|---|---|---|---|
| Cooper hub | 5.0 (2030) / 10.0 (2035) / 20.0 (2040+) | Santos-JX-ENEOS partner pathway | **APPRAISAL. MoU and feasibility study only, not FID** |
| CarbonNet | 0 until 2040, then up to 6.0 | Vic DJSIR, Pelican "up to 6 Mtpa", "operational late 2030s" | **DEVELOPMENT, pre-FID, no development partner secured**. Declaration of Storage Formation targeted 2026 |
| Otway hub | 0.2 from 2030 | Beach Energy pre-feasibility | **APPRAISAL, no FID**, timing undeclared |

CarbonNet enters at 2040 because "late 2030s" makes 2040 the first milestone year
consistent with its proponent's own schedule; placing it at 2035 would contradict the
source.

**The power-available haircut.** Physical injection is not injection available to NEM
power generation. The Cooper hub's 5/10/20 pathway is explicitly framed as **imported
Japanese CO2** in Santos's own documents. CarbonNet's intended anchor customers are
Latrobe Valley industry and hydrogen. Reservoir CO2 arrives at high concentration and
pressure; CCGT flue gas is ~4% CO2 at atmospheric, so it is far more expensive to
capture and any shared hub will contract the cheap stream first. **Power is the marginal
claimant.** The decision memo carries a 0-50% band; the optimistic variant takes the
upper edge, 50%.

**The realisation band is carried, not applied.** Every Australian CCS project with
operating history has undershot nameplate: Gorgon at ~33% six years after start-up,
Moomba at 76% in year one **and again in FY2025-26** (flat, no ramp toward nameplate).
The observed achieved/nameplate band is **0.33-0.76**. The optimistic variant is defined
as proposals realised *at nameplate*, so no discount is applied to it; applying the band
would give 2050 power-available injection of **4.3-10.0 Mt/yr** instead of 13.1. That is
a stated sensitivity, not a variant.

### 3.3 The two variants

**CONSERVATIVE — the production default. Every tranche cap is zero in every year.**

| milestone | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|---|
| cooper_hub | 0 | 0 | 0 | 0 | 0 |
| carbonnet | 0 | 0 | 0 | 0 | 0 |
| otway_hub | 0 | 0 | 0 | 0 | 0 |
| **total kt/yr** | **0** | **0** | **0** | **0** | **0** |

Not an abstention. It is the arithmetic of the pipeline table: no operating or
sanctioned CO2 sink with spare capacity is connected, or connectable without an
unproposed ~1,000 km trunkline, to any NEM CCS-gas bus. The conservative trajectory
rests on **a single operating project, whose entire output is already spoken for**.
Stated plainly rather than padded.

**OPTIMISTIC — the upper edge. Every live proposal realised at nameplate on its
proponent's schedule, 50% power-available.**

| milestone | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|---|
| cooper_hub | 2,500 | 5,000 | 10,000 | 10,000 | 10,000 |
| carbonnet | 0 | 0 | 3,000 | 3,000 | 3,000 |
| otway_hub | 100 | 100 | 100 | 100 | 100 |
| **total kt/yr** | **2,600** | **5,100** | **13,100** | **13,100** | **13,100** |

The 2050 total is **13.1 Mt/yr, not the decision memo's 14.1**, because SEA CCS is
excluded as withdrawn.

### 3.4 Storage cost, and the offshore flag

**A$18.5/tCO2 on every tranche**, from GHD (2025) for AEMO s3.11 (range 12-25, real 2025
AUD, AACE Class 5 at -50%/+100%). The basis is an **onshore pipeline injecting into a
depleted natural gas reservoir**, and it traces to Rubin et al. (2015), a global
literature value currency-converted, not an Australian site study.

**CarbonNet is offshore, so A$18.5/t is optimistic there by an unquantified margin.**
CarbonNet publishes no $/t. No offshore premium is invented; the onshore figure is
applied uniformly and this flag is the compensating disclosure. The 12-25 range should
be carried on CarbonNet-served tranches in particular. Since CarbonNet serves the
sub-regions holding **the majority of this fleet's captured CO2** (§4), an understated
CarbonNet storage cost understates the whole curve.

The same caveat applies to the TAS transport leg, which crosses Bass Strait and is
priced at the onshore per-km rate (§4).

---

## 4. Transport basis

### 4.1 Distance method, declared

No route study exists for any of these source-sink pairs, so distances are computed, not
sourced, by a uniform declared method:

1. WGS84 positions of each ISP sub-region reference node (the substations named in
   `sub_regions.csv`) and each sink injection area, to ~0.05°.
2. Haversine great-circle distance.
3. **Routing factor 1.25**, applied uniformly. Great-circle is a floor; real trunklines
   follow terrain, tenure and existing corridors. 1.25 sits inside the 1.2-1.3 band and
   being uniform means no route is flattered relative to another.
4. Rounded to the nearest 10 km, which is the honest precision of the method.
5. Each bus is assigned its **nearest permitted sink**.

Transport priced at **A$0.1096/tCO2/km** (GHD 2025 for AEMO, onshore pipeline;
Aurecon 2024 gives 0.1075 on the same basis).

### 4.2 The adder table

| sub-region | reference node | assigned sink | km | transport A$/t | **+ storage = A$/t** | **adder A$/MWh** |
|---|---|---|---|---|---|---|
| SEV | Hazelwood | carbonnet | 80 | 8.77 | **27.27** | **3.68** |
| WNV | Moorabool | otway_hub | 160 | 17.54 | 36.04 | 7.35 |
| MEL | Thomastown | carbonnet | 250 | 27.40 | **45.90** | **11.49** |
| SESA | South East | otway_hub | 270 | 29.59 | 48.09 | 12.41 |
| TAS | George Town | carbonnet | 380 | 41.65 | 60.15 | 17.46 |
| SNSW | Canberra | carbonnet | 490 | 53.70 | 72.20 | 22.51 |
| NSA | Davenport | cooper_hub | 680 | 74.53 | 93.03 | 31.25 |
| CSA | Torrens Island | otway_hub | 720 | 78.91 | **97.41** | **33.08** |
| SNW | Sydney West | carbonnet | 770 | 84.39 | **102.89** | **35.38** |
| CNSW | Wellington | carbonnet | 840 | 92.06 | 110.56 | 38.59 |
| NNSW | Armidale | carbonnet | 1,210 | 132.62 | 151.12 | 55.60 |
| CQ | Broadsound | cooper_hub | 1,370 | 150.15 | 168.65 | 62.95 |
| NQ | Ross | cooper_hub | 1,480 | 162.21 | 180.71 | 68.01 |
| GG | Calliope River | cooper_hub | 1,490 | 163.30 | **181.80** | **68.46** |
| SQ | South Pine | cooper_hub | 1,580 | 173.17 | **191.67** | **72.60** |

Bold rows are the six sub-regions carrying material CCS in `vrefix_gbc_c550_2050`.
The A$/MWh column is transport only, at 0.419232 tCO2/MWh captured; storage is priced at
the tranche, not in marginal cost (§5).

**No bus is left unpriced.** Every sub-region reaches a permitted sink at some distance,
so the brief's stop condition does not fire.

### 4.3 Cross-check against the sourcing memo's regional table

The surface-and-pause test is whether these adders produce an ordering inconsistent with
`CCS_TNS_SOURCING.md` §3.4. They do not, with one explained exception.

| sub-region | this curve, A$/t | sourcing memo | verdict |
|---|---|---|---|
| SEV (Latrobe) | 27.3 | ~15 (Allinson Latrobe→Gippsland) | same rank, higher level. Ours is a GHD build-up including an 80 km leg; Allinson's is a 2009 study escalated |
| SNW (Sydney) | **102.9** | **74-109** (the memo's unresolved two-row ambiguity) | **inside the band, and it resolves the ambiguity**: nearest-permitted-sink picks Gippsland, landing between the memo's "South NSW→Gippsland" (74) and "All NSW→Cooper" (109) |
| CSA (Adelaide) | 97.4 | ~109 (Cooper build-up) | consistent; ours routes to Otway, which is nearer |
| SQ, GG (QLD) | **181.8-191.7** | ~26 (Allinson South Queensland→**Surat**) | **inverted, and correctly so.** The memo priced Queensland's *natural* sink; that sink is now illegal. Queensland CO2 must reach the Cooper Basin, ~1,500 km away. The inversion is the prohibition showing up in the price, not an inconsistency |

The SNW result is the useful one: the memo flagged the Sydney assignment as a judgement
worth A$35/t on the fleet-weighted price, and the nearest-permitted-sink rule settles it
on a stated method rather than a preference.

### 4.4 The consequence the national-total arithmetic missed

`CCS_CAP_AND_DECISION.md` §2.6 concluded that the optimistic cap does not bind at 2050:
11.85 Mt/yr demanded against 14.1 Mt/yr available, 84% utilisation. **At sink level that
conclusion reverses.**

Mapping the solved `vrefix` fleet's captured tonnage through the §4.2 assignment:

| sink | `vrefix` demand Mt/yr | 2050 optimistic cap Mt/yr | utilisation | binds? |
|---|---|---|---|---|
| **carbonnet** | **10.554** (SNW 6.775 + SEV 2.114 + MEL 1.665) | **3.0** | **352%** | **YES, by 7.55 Mt/yr** |
| cooper_hub | 1.201 (SQ 0.688 + GG 0.513) | 10.0 | 12% | no |
| otway_hub | 0.098 (CSA) | 0.1 | 98% | at the margin |
| **total** | **11.853** | **13.1** | **90%** | **no** |

The national total has 10% headroom while the sink that must take 89% of the CO2 is
oversubscribed 3.5x, and the sink with 8.8 Mt/yr of spare capacity is 1,500 km from the
generators that could use it.

**This is a fourth factor, and it is the point of doing this at sink level.** It is a
design-time prediction from the solved `vrefix` fleet, not a result; the optimistic
validation cell tests it. If it holds, the honest reading of the decision memo's
optimistic case is that it was too generous, because it aggregated a spatial problem
into a national one.

---

## 5. Formulation

Two mechanisms, deliberately separated.

**Transport, per generator, in marginal cost.** For each CCS generator at bus *b*:

```
marginal_cost += transport_$/t[b] × isp_captured_co2_t_per_mwh
```

replacing `tns_price × captured`. This is a per-generator column, not a scalar, so the
LP sees Sydney's disposal as more expensive than Latrobe's, and can respond by
relocating rather than only by shrinking.

**Storage and injectivity, per sink, in the linopy model.** Per sink *s*, per investment
period *p*, mirroring `_add_fuel_supply_curve`:

- a purchase variable `ccs_injection_purchases_kt_{s}_{p}`, bounded above by the
  tranche's `cap_kt`;
- a constraint that annual captured tonnage from the generators assigned to *s* is
  covered by that purchase;
- an objective term pricing the purchase at the tranche's `storage_$/t`, weighted by the
  period's objective weighting exactly as other operational costs are.

```
Σ_gen∈s Σ_t  p[t,gen] · w[t] · captured_t_per_mwh[gen] / 1000  ≤  purchases_kt[s]   (kt/yr)
objective   += storage_$/t[s] · 1000 · objective_weight[p] · purchases_kt[s]
```

**Units.** Tranche variables are denominated in **kt/year**, for the same reason the gas
curve uses TJ rather than GJ: it lands the caps (~1e2-1e4), the objective coefficients
(~1e4) and the coupling coefficients (~1e-4) inside the model's existing magnitude
range. Mt would put objective coefficients at ~1e7; tonnes would put caps at ~1e7.

**The curve terminates.** There is no uncapped backstop tranche. This is the deliberate
difference from the gas and biomass curves, where an uncapped high-price tail exists so
the LP prices extreme volumes rather than going infeasible. Injectivity beyond the
enumerated tranches **does not exist at a price** within this horizon: you cannot buy a
reservoir that has not been appraised. In the conservative variant every cap is zero, so
the constraint is `captured ≤ 0` and CCS generation is forced to zero. That is intended
and is the load-bearing behaviour the validation cell tests.

### 5.1 Span weighting — a correction to the decision memo

`CCS_CAP_AND_DECISION.md` §4 and `CCS_TNS_SOURCING.md` §5.1 both state that the cap
constraint needs a `× years` term, mirroring `_add_hydro_energy_budget_constraint`.
**That is wrong for this formulation, and applying it would make every cap 5× too
loose.**

Verified against the installed PyPSA: `define_operational_limit`
(`pypsa/optimization/global_constraints.py:483`) multiplies snapshot weightings by
`investment_period_weightings.years` internally when `_multi_invest` is set. The hydro
budget uses a PyPSA `GlobalConstraint`, so its RHS must carry the matching `× years`.

This curve uses the gas curve's linopy-level pattern instead, because a
`GlobalConstraint` can only group by carrier and cannot express a per-sink group. In
that pattern the constraint is assembled from raw `snapshot_weightings` (which sum to
8,760 h, one year, per period), so the LHS is an **annual** quantity and the RHS is the
**annual** cap, with no `years` factor. Identical to how the gas curve treats `cap_pj`.
The period span enters only through `objective_weight` on the price, as it does for
every other operational cost.

This is covered by a unit test so it cannot silently regress.

---

## 6. Implementation map

| piece | location |
|---|---|
| curve CSV builder | `analysis/ccs_market/build_ccs_supply_curve.py` |
| sink tranches, conservative (default) | `analysis/ccs_market/ccs_sink_tranches_conservative.csv` |
| sink tranches, optimistic | `analysis/ccs_market/ccs_sink_tranches_optimistic.csv` |
| transport adders + sink assignment | `analysis/ccs_market/ccs_transport_adders.csv` |
| config | `CcsSupplyCurveConfig` in `src/ispypsa/config/validators.py` |
| translation | `src/ispypsa/translator/ccs_supply_curve.py` |
| per-generator adder into marginal cost | `src/ispypsa/translator/generators.py` |
| constraint construction | `src/ispypsa/pypsa_build/ccs_supply_curve.py` |
| wiring | `pypsa_build/build.py`, `pypsa_build/update.py`, `translator/create_pypsa_friendly.py` |
| tests | `tests/test_ccs_supply_curve/` |

Selection mirrors the gas curve: `ccs_supply_curve.sink_tranches_csv` unset leaves the
pre-existing behaviour (free unlimited disposal, the AEMO-comparable reference); set to
the conservative CSV for the production default; set to the optimistic CSV for the
branch.

The scalar `carbon_pricing.tns_price` is **superseded but retained inert**, so that the
45 archived `prod_*` configs carrying `tns_price: 20.0` remain reproducible. Setting
both a non-zero `tns_price` and a CCS supply curve raises, rather than silently
double-counting disposal.

---

## 7. Honesty: this curve's basis is thinner than the gas curve's

The gas curve rests on AEMO's GSOO Step Change GPG bands, ACCC gas inquiry reporting and
Rystad marginal-cost-of-supply curves: a market with observed prices, observed volumes,
and multiple independent forecasters. **This curve does not have that.**

What it actually rests on:

- **One operating project in a NEM basin** (Moomba Phase 1), running at 76% of
  nameplate in year one and again in FY2025-26, whose entire output is committed to its
  operator's own gas-processing CO2 and is therefore excluded from the tranches.
- **Three pre-FID proposals**, one of which (CarbonNet) has no development partner, one
  of which (Cooper Phase 2) is an MoU and feasibility study whose stated volumes are for
  imported Japanese CO2, and one of which (Otway) is 0.2 Mt/yr.
- **A global literature cost value** (Rubin et al. 2015) currency-converted by two
  consultants, neither of which shows its FX or escalation working, for an onshore
  reservoir class that does not describe the sink serving most of this fleet's CO2.
- **Computed distances with a declared routing factor**, because no route study exists
  for any pair.
- **Zero Australian power-sector CCS operating experience.** The only attempt at scale
  was refused and is now statutorily impossible.

**The compensating structure is the variant pair and the ranges, not precision in any
single number.** The conservative and optimistic variants are ~13 Mt/yr apart at 2050,
which is wider than the entire quantity being modelled. That span is the honest
statement of what is known. Anyone reading a single number off this curve without the
other variant is misreading it.

Specific things not to over-read:

- The A$18.5/t storage figure has an AACE Class 5 accuracy of -50%/+100%, i.e. the
  sourced range is 12-25 and the true uncertainty is wider still.
- CarbonNet is offshore and priced at an onshore rate. It serves 89% of this fleet's CO2.
- The TAS transport leg crosses Bass Strait at an onshore per-km rate.
- The 0-50% power-available share is a judgement, not a sourced split, and is the
  largest single lever in the optimistic variant.
- The 90% capture rate feeding `isp_captured_co2_t_per_mwh` is a hard-coded translator
  placeholder, corroborated by AEMO's emissions-intensity sheet but not cited to it.
  Every tonnage and every dollar in this document scales linearly with it.

---

## 8. Limitations and next steps

- **Each bus is assigned one sink.** A true source-sink network would let a bus bid into
  any sink at a pair-specific price, so a Sydney generator blocked at CarbonNet could pay
  more to reach the Cooper hub. As built, a bus's price *and* its quantity ceiling are
  both tied to its nearest sink, which makes §4.4's carbonnet oversubscription bind
  harder than a network formulation would. This is the single most consequential
  simplification and the obvious next extension.
- **No CO2 pipeline capital cost or lead time.** The adders are per-tonne operating
  costs. A 1,580 km trunkline from Brisbane to Moomba is priced but not scheduled, and
  no proponent has proposed one.
- **No sink build-out lumpiness.** Caps interpolate linearly between proponent anchors;
  real injection capacity arrives in project-sized steps. Only milestone years are
  consumed by the model, so this affects nothing in practice.
- **The conservative variant only reaches the *fleet* through a chain re-solve.** As
  `CCS_CAP_AND_DECISION.md` §1.2 established, the 9.80 GW CCS fleet is inherited from the
  pre-VRE-fix chain's 2030-2045 tranches and enters the 2050 LP at `capital_cost = 0`.
  A curve applied at 2050 alone silences that fleet as an energy source but cannot
  un-build it. Measuring the curve's real effect requires re-solving the chain from 2030,
  which is wave scope.
- **Not addressed here:** per-plant capture rates and the capture-rate citation gap;
  monitoring for a Queensland GAB reversal; a SEA CCS revival; regional gas supply curves.

---

## 9. Full-year validation

*To be completed from the `ccscon_gbc_c550_2050` and `ccsopt_gbc_c550_2050` cells.*
