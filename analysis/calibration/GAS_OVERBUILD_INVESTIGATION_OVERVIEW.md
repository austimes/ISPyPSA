# High gas use vs the ISP: investigation overview

**Date:** 2026-08-14. **Scope:** consolidated status of the investigation into why the
model builds and burns far more gas than AEMO's 2026 ISP, across all tests run to date,
with conclusions and stated confidence levels. Individual test documentation is linked
throughout; this file is the synthesis.

## 1. The observation

Against AEMO's 2026 ISP scenarios (bulk-grid renormalised both sides,
`ccx_vs_aemo_2026_scenario_calibration.md`):

- **Gas share of generation, 2050:** model 22.9–29.3% (across carbon prices $0–550/t)
  vs AEMO 0.7–5.0% (across all three scenarios). Gas burn ~536 PJ/yr at c550-2050 vs
  AEMO's GSOO GPG outlook of 60–110 PJ/yr.
- The gap **opens from the first solved year and widens monotonically** (11.8 pp at 2030
  → 20.1 pp at 2050 vs Step Change, at the model's own highest carbon price).
- It persists although the model serves **less demand than AEMO at every year** (−5%
  opening to −17.5% by 2050, demand-vintage effect) — the demand handicap runs the
  *wrong way* for an over-build, strengthening the case that the driver is structural.

## 2. Tests run and what each established

### 2.1 Carbon price as the lever — RULED OUT (high confidence)

> **WITHDRAWN 2026-08-15 — the shadow-price analysis, not merely caveated.** The
> $3,500–11,700/t figure for matching AEMO's generation mix was computed against a wind
> side carrying three independent defects, all since fixed on `storage-menu-repair`
> (`vre_margin_diagnostic.md`; commits `7f12fd4`, `36ab6c6`, `78267c3`):
> 14 of 38 REZ augmentation options offered at a tenth of their capacity and ten times
> their unit cost, all 104,362 MW of offshore wind hard-capped at exactly 0 MW, and
> 16.3 GW of existing VRE life-extended free of any FOM or repowering charge. A
> carbon-price elasticity measured against a wind supply curve that was truncated,
> mispriced and competing with free incumbents does not measure the economics it claims
> to. The *mechanism* claim (carbon price decarbonises by retiring coal and swapping
> CCS for unabated gas, not by displacing gas energy with VRE) is untested rather than
> disproven. Re-derive from a repaired frontier before quoting any elasticity. The gas
> share range 29.3% → 22.9% is likewise a pre-fix quantity.

The 7×5 ccx frontier + shadow-price analysis: matching AEMO's *emissions intensity*
takes a plausible $100–400/t through 2045, but matching AEMO's *renewable share /
generation mix* takes $3,500–11,700/t (extrapolated) — economically meaningless. Carbon
price decarbonises this model by retiring coal and swapping CCS gas for unabated gas,
not by displacing gas energy with VRE. Gas share at 2050 barely responds ($0/t: 29.3% →
$550/t: 22.9%). *Confidence: high — full frontier, verified cost axis, monotone
behaviour, mechanism identified.*

### 2.2 Perfect foresight vs myopic chaining — NOT THE PRIMARY DRIVER (medium-high)

Tier-2 (`TIER2_PERFECT_FORESIGHT.md`): a 5-period PF LP vs the myopic chain at equal
(rep-week) coverage. PF front-loads the build but its 2050 endpoint is *not* cleaner —
comparably or slightly more gas than myopic. Myopic chaining shapes the trajectory, not
the endpoint gas level. *Confidence: medium-high — the PF primal was read at diagnostic
tolerance (gap 5e-2) and at rep-week coverage; directionally robust, magnitudes soft.*

### 2.3 USE-penalty strictness — RULED OUT (high)

Full 5-period chain at $1,000/MWh vs the production $10,000/MWh, all else identical:
gas/CCS-gas/coal/REZ-transmission decisions unchanged within solver noise; the only
response was 0 → 0.374 TWh of accepted unserved energy by 2050 (~0.15% of generation).
The bite is coverage (the year must be survived), not the dollar strictness of the
penalty. *Confidence: high — clean paired design, null result.*

### 2.4 Rep-week sampling as a confound — CONFIRMED AND EXCLUDED (high)

Tier-3 (`TIER3_REPWEEK_AUDIT_AND_SYNTHESIS.md`): rep-week selection is 100%
demand-based (no VRE criterion exists), catches sustained VRE droughts only
coincidentally, and cannot represent an 11-day event in ≤8-day blocks; its bias is a
*general* ~18% capacity-mix distortion (≈2× wind:solar swing), not firming-specific.
All production results are therefore full-year; rep-week is screening-only. The
gas-curve experiment (§2.7) re-confirmed the direction: rep-week made gas look ~4×
more displaceable than full-year. *Confidence: high — audited by construction and
empirically, twice.*

### 2.5 The drought-survival mechanism — CONFIRMED (high)

Tier-3 empirics on the solved production networks: during the identified sustained
multi-day VRE drought window, storage drains to near-total depletion and gas dispatch
~doubles, across 7 cells spanning the full carbon-price range **including $0/t** — the
firm-gas fleet demonstrably exists to survive real drought events, orthogonal to carbon
price. *Confidence: high — direct reads of solved dispatch, replicated across cells.*

### 2.6 Weather-year basis — RECHARACTERISED, THEN RULED OUT AS THE FIX (high)

- **Recon finding:** the "2018" VRE store is AEMO's synthetic `RefYear5000` sequence — a
  16-slot tile of 15 historical years (2011–2025, chronological, FY2031≡FY2042
  duplicate). Milestone cells face draws of inconsistent severity (2030→2014, the most
  severe; 2045→2013, mild; 2050→2018) and never the tile's worst junction event. The
  famous "11-day drought" partly straddles the artificial tile-wrap seam; no single real
  year has a >8-day CF<0.20 run. Demand↔VRE weather correlation is broken under the
  relabelled store (demand pinned to 2018-shape while VRE varies).
- **Data acquired:** all 15 per-reference-year 2026 VRE archives ingested (14 real years
  live in the store; real 2018 pending a label decision), full-NEM end-to-end validated.
- **Stage-1a elasticity test** (`stage1_weather_addendum.md`): re-solving the c550/2050
  cell against severe/median/mild real years moves total firm gas only 18.7–20.7 GW vs
  baseline 19.8 (±5%), **non-monotonically** with drought severity; USE=0 everywhere.
  Every real year contains enough sustained stress that ~19–21 GW is the answer.
- **Stage-1b:** a two-weather-year shared-capacity LP is tractable (no PF-style stall)
  but gap-floors at ~5.2e-3; its value is moot given 1a's null.

*Conclusion: the weather draw is not the driver, and multi-year coverage will not close
the gap. Confidence: high for the per-milestone result (clean paired design, full
severity range); medium that whole-chain re-solves would not compound differences
(untested, but the per-milestone margin is flat and ~85% of the 2050 gas fleet is
carried, so the prior is weak).*

### 2.7 Flat gas price / missing supply feedback — REAL, NOW CORRECTED; TRIMS BUT DOES NOT CLOSE (high)

The model bought unlimited gas at flat IASR prices (~5× AEMO's GPG outlook, ~today's
entire domestic market, with no price response). A sourced stepped supply curve
(GSOO/ACCC/Rystad/ACIL basis, `analysis/gas_market/GAS_SUPPLY_CURVE.md`) was
implemented, unit-tested, and validated. Full-year c550/2050 confirmation
(`gscfy`/`gbcfy`, both CONV 3e-3, ~7h):

- Gas burn 536 → 471 PJ (**−12%**); firm gas capacity 19.8 → 19.1 GW (**−0.7 GW only**).
- The model *pays* the +$6/GJ LNG-import premium for ~131 PJ rather than shed the fleet
  — gas demand is quite inelastic between +$4 and +$18/GJ because the fleet is
  reliability-driven. Fuel premium ~$1.6B/yr at 2050 (~+$6/MWh on the cost coordinate).
- Biomass substitution is small and robust to honest feedstock pricing via the biomass
  supply curve (75 → 63 PJ).
- The rep-week paired pilot's −45%/−3.6 GW was a rep-week artifact — quote full-year.

*Conclusion: a genuine partial-equilibrium error, now corrected; it reprices gas energy
(material $ effect) far more than it removes gas capacity. Confidence: high for the 2050
c550 cell; medium-high for the trajectory shape (rep-week suggests binding from
~2035–40; full-year confirmed only at 2050).*

### 2.8 Adjacent finding: the wind-share plateau (medium-high)

> **SUPERSEDED 2026-08-15 by `vre_margin_diagnostic.md`.** Two of the three mechanisms
> below are retracted:
>
> - *"REZ transmission-augmentation economics, exercised selectively because CCS gas is
>   cheaper at the margin"* — the options recorded as available-but-declined were being
>   offered at a tenth of their published capacity and ten times their true unit cost
>   (14 of 38; N13 among them). A refusal of a 10x-mispriced option is not an economic
>   judgement. The source memo's utilisation figures additionally double-count carried
>   capacity that `adjust_capacity_caps_for_carried` has already netted off the RHS.
> - *"2030-vintage wind reaching end-of-life through the 2040s"* — **withdrawn
>   outright.** New-entrant wind and solar carry 30-year IASR technical lives and the
>   earliest chain vintage is 2030, so no wind or solar vintage retires anywhere in the
>   horizon; the only cohort that ever drops is the 2030 batteries at 20 years. The REZ
>   capacity swings read as a replacement cycle are per-period new build, not standing
>   capacity.
>
> What replaces them: wind's availability-weighted capture price is $64/MWh against a
> $127/MWh mean bus price, because ~90% of an incremental wind MWh lands in hours that
> already carry spill. The marginal built candidate sits at a margin of $0.39/MW/yr.
> That shape penalty is genuine economics and survives the fixes; the mispriced
> transmission and the zero-capped offshore did not.

`rez_headroom_check_wind_solar_plateau.md`: model wind share plateaus ~41–43% from 2040
while AEMO climbs to ~58–61% — driven by REZ transmission-augmentation economics (a
finite AEMO-enumerated option list, exercised selectively because CCS gas is cheaper at
the margin) plus 2030-vintage wind reaching end-of-life through the 2040s. This is the
"why doesn't VRE grow instead" half of the gas story. *Confidence: medium-high —
diagnostic reads of solved networks, not a controlled experiment.*

## 3. Current synthesis — the decomposition of the gap

The gas over-build decomposes into, in order of evidential strength:

1. **Reliability architecture (primary driver of the firm GW).** A deterministic LP that
   must survive a real weather year with effectively zero unserved energy builds
   ~19–21 GW of firm gas at 2050 — under *any* tested weather year, any USE penalty, any
   carbon price, with or without foresight, and (as of §2.7) at any plausible gas price.
   AEMO instead plans against a stochastic ensemble with a probabilistic USE target
   *plus* administered/policy-driven renewable build. Every cheap lever that would have
   falsified this has been tested and returned null. *Confidence: high.*
2. **AEMO's non-price renewable drivers (primary driver of the energy-mix share).** No
   carbon price reproduces AEMO's renewable trajectory; AEMO's buildout is carried by
   levers a cost-minimising LP with a bare carbon price does not represent (CIS-style
   underwriting, jurisdictional targets, REZ co-optimisation). *Confidence: high on the
   shadow-price evidence; the specific attribution to policy instruments is inference.*
3. **Flat gas pricing (real, corrected, second-order for capacity).** Worth ~65 PJ/yr of
   burn and ~$1.6B/yr of honest repricing at 2050, not a capacity-mix fix. *Confidence:
   high.*
4. **Demand vintage** runs the other way (model serves less demand yet builds more gas)
   — it strengthens rather than weakens the structural story. *Confidence: high.*

**Ruled out as fixes** (all tested): carbon price (any plausible level), USE-penalty
tuning, weather-year selection, multi-year weather coverage, perfect foresight,
rep-week/sampling artifacts (excluded from production), gas-price elasticity (mostly).

**The residual divergence is a modelling-philosophy difference, not a bug**: a
zero-failure deterministic reliability test + pure price-signal decarbonisation versus
AEMO's probabilistic adequacy + administered renewable build. Closing it would mean
modelling AEMO's policy instruments (renewable underwriting/targets as constraints),
not further reliability or fuel-price work.

### 3.1 Vintage annotation (2026-08-14): the ccx frontier predates the hydro budget

The hydro annual-energy-budget constraint (commit `4326148`, 2026-08-10) postdates
the ccx frontier solves (2026-07-10): the frontier networks carry **zero
GlobalConstraints** and their conventional hydro dispatches ~20.2–20.8 TWh/yr at the
synthetic seasonal ceiling, versus the constraint's 12.06 TWh/yr (binding in the
gscfy/gbcfy runs, shadow price −1.66 $/MWh). Two consequences
(`analysis/calibration/PHES_BEHAVIOUR_CHECK.md` §3):

1. **Every ccx frontier gas figure sits on ~8.5 TWh/yr of over-generated free
   hydro** — re-solved under current code, baseline gas burn would be higher still,
   so the frontier's gas over-build vs AEMO is *understated*, not caused, by this
   defect.
2. **The §2.7 gas-curve deltas are conservative**: gscfy lost ~8.1 TWh/yr of free
   hydro relative to its ccx baseline and still cut gas burn 536→471 PJ; the
   equal-hydro curve effect is larger than −65 PJ.

No pre/post-`4326148` network pair may be compared without this annotation. The
budget itself has since been re-sourced to AEMO's 2026 ISP Step Change hydro
trajectory (declining 16.7→9.8 TWh/yr, 2027→2050; see
`analysis/calibration/aemo_2026_isp_sc_hydro_generation.csv`), which tightens
2045–2050 further.

### 3.2 ccx frontier usability (2026-08-15): cost axis and mix shares are unusable

Separate from, and additional to, the §3.1 hydro annotation. The three defects fixed on
`storage-menu-repair` (`vre_margin_diagnostic.md`; commits `7f12fd4`, `36ab6c6`,
`78267c3`) all sit upstream of the ccx solves, so every ccx network was built against a
transmission option set offering 16,135 MW where AEMO publishes 44,670 MW at the
correct least-cost selection, a candidate menu with all 104,362 MW of offshore wind
pinned to zero, and 16.3 GW of existing VRE carrying no fixed cost at all.

| ccx output | status for ShARP Pass 2 |
|---|---|
| Cost coordinate (`$/MWh`, frontier points) | **UNUSABLE** — transmission capex wrong on 14 of 38 REZ options and 1 of 10 flow paths, and the option *selection* was ranked on the corrupted values |
| Generation mix shares (gas %, wind %, renewable %) | **UNUSABLE** — measured against a truncated, mispriced wind supply curve |
| Carbon-price elasticity / shadow prices (§2.1) | **WITHDRAWN** — see the §2.1 annotation |
| Reliability findings (USE = 0, drought-survival mechanism §2.5, firming adequacy) | **STAND, pending re-verification** — these are capacity-adequacy results driven by the demand and outage traces and the storage/hydro architecture, none of which the three fixes touch. Re-verify on the repaired frontier before publishing, but there is no identified mechanism by which the fixes would overturn them. |
| Emissions intensity (tCO2/MWh) | **treat as indicative only** — dispatch-driven, so not directly corrupted, but it moves with the mix |

The three defects were all upstream shared-templater or translator code, not fork
analysis code, so this applies to every frontier this project has produced, not only
ccx. Realising the repair needs a full re-solve.

## 4. Open items

- **Whole-chain weather compounding** — untested (Stage-1a was per-milestone,
  conditional on the committed chain); weak prior it matters.
- **Winter/peak-day gas deliverability** — the curve's budgets are annual; seasonal
  deliverability is the binding constraint in the real market and could bite harder
  than the annual caps (design doc §6.1).
- **CCS-gas candidate-set decision** — the standing human decision from the ccx
  frontier (is CCS-gas a legitimate menu candidate at high carbon prices?); this
  investigation reframes it as a rational response to the reliability architecture.
- **Adopting the supply curves into the production frontier** — the one actionable
  model change on the table: re-solve the 7×5 menu with gas+biomass curves (~7h/cell,
  no tractability penalty) to carry the repriced cost coordinates into Pass-2.
- **Policy-instrument representation** (renewable underwriting/targets) — the only
  identified path that could genuinely close the *mix* gap; a scope decision, not a
  calibration task.

## 5. Provenance

Tests: `outputs/frontier_ccx/*` (ccx frontier, Tier-1/2/3), USE-penalty sweep
(`uset1000full_c550_*`), calibration (`ccx_vs_aemo_2026_scenario_calibration.md`),
weather program (`WEATHER_COVERAGE_DESIGN_OPTIONS.md`, `TRACE_ACQUISITION_BRIEF.md`,
`benchmarks/stage1_weather_addendum.md`, runs `ws14/ws21/ws23/ws2y_c550`), gas market
(`gas_market/GAS_SUPPLY_CURVE.md` incl. §5a full-year validation, runs
`gscrw2/basrw2/gscfy/gbcfy_c550`), bioenergy (`bioenergy_market/BIOMASS_SUPPLY_CURVE.md`),
wind plateau (`calibration/rez_headroom_check_wind_solar_plateau.md`).
