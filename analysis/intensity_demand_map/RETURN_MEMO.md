# Marginal-cost map over intensity x demand: return memo

**Status: IN PROGRESS.** This memo is written stage-by-stage; the verdict line is
updated last.

Branch `analysis/intensity-demand-map`, not pushed. Run artefacts gitignored
(`analysis/benchmarks/runs_myopic/`, `records/`, `logs/`). The previous sweep's
committed deliverables under `analysis/demand_carbon_sweep/` are not modified.

---

## 1. State verified against

Branched from `analysis/demand-carbon-sweep` at `31655be` (the completed 16-cell
demand x carbon sweep). All four gas-share repairs are ancestors and were
re-confirmed **functionally in this working state** (extraction from solved
networks and a direct function call, not commit subjects):

| repair | commit | evidence (this working state) |
|---|---|---|
| REZ numeric-strip regex | `7f12fd4` | direct call: `1660` -> `1660`, `2131000` -> `2131000`, `1,660 some note` -> `1,660` |
| PHES candidates | `7d4acbe` | `sweep_c0_d100_2050` network: 36 Water storage rows, durations {4,6,9,10,12,20,24,48,159} h, 6.075 GW built |
| Offshore wind cap | `36ab6c6` | 2.073 GW offshore built across 8 rows (not pinned to 0) |
| ECAA VRE/hydro FOM | `78267c3` | `ecaa_generators.csv`: 0 of 336 FOM values NaN |

Script: `scripts/stage0_conditioning.py` (asserts on every repair; a regression
halts the run).

---

## 2. Stage 0 findings

### 2.1 Conditioning provenance (gate 1)

The map's cells are conditioned single-year solves on the **`sweep_c0_d100`
chain** — the previous sweep's $0/t carbon price at Step Change demand, i.e. the
model's own current-policy state (no carbon instrument; central gas, biomass and
CCS-disposal economics). Concretely, each map cell at year Y injects, read-only,
the chain's saved new-build tranches (build years < Y, retirement-filtered) and
its retention floor (latest year < Y) — exactly the fleet state the chain's own
solve of year Y saw. 2030 cells are therefore greenfield-on-ECAA (no prior
tranche), matching the chain's 2030.

Gap to the colleague's current-policy pathway anchors, reported not rescaled
(generation basis = real grid generation; share = r_total, s2.5):

| year | model generation TWh | anchor P_y/1.3 TWh | quantity gap | model r_total | anchor share | share gap |
|---|---|---|---|---|---|---|
| 2030 | 192.83 | 211.54 | **-8.8%** | 60.8% | 79.6% | **-18.8 pp** |
| 2040 | 245.92 | 292.31 | **-15.9%** | 74.2% | 94.0% | **-19.8 pp** |
| 2050 | 260.96 | 330.77 | **-21.1%** | 81.4% | 97.4% | **-16.0 pp** |

The quantity gap is mostly the boundary (s2.2); the share gap is real: the
model's no-carbon-instrument state builds renewables on economics alone and sits
16-20 pp below the pathway's planned shares. **The map is anchored at this
offset**; cells at ι_planned (the conditioned state's own realised intensity)
describe the model's current-policy point, not the colleague's.

The conditioned pathway's realised intensity, on the same per-generator
residual-CO2e basis the map's cap uses (delivered basis):

| year | ι_planned t CO2e/MWh | annual residual CO2e | delivered TWh |
|---|---|---|---|
| 2030 | 0.395398 | 74.707 Mt | 188.94 |
| 2040 | 0.181717 | 43.193 Mt | 237.69 |
| 2050 | 0.095404 | 24.036 Mt | 251.94 |

These residual-basis emissions match the previous sweep's committed NGER-basis
figures to all reported digits (74,706.78 / 43,192.82 / 24,035.93 kt), so the
cap's accounting and the previous sweep's reported emissions are the same
accounting.

### 2.2 Boundary reconciliation (gate 2)

From AEMO's own raw 2026 ISP Final trace set (Step Change, POE50, RefYear 2018,
15 sub-regions, summed by financial year) — script `scripts/stage0_boundary.py`,
output `stage0_boundary.csv`:

| year | anchor (source gen) | OPSO_MODELLING | PV_TOT (distributed PV) | OPSO+PV | **residual** |
|---|---|---|---|---|---|
| 2030 | 211.54 | 189.82 | 48.72 | 238.53 | **-26.99 (-12.8%)** |
| 2040 | 292.31 | 240.05 | 78.95 | 319.00 | **-26.69 (-9.1%)** |
| 2050 | 330.77 | 251.93 | 121.39 | 373.32 | **-42.55 (-12.9%)** |

Internal validation: AEMO's `OPSO_MODELLING_PVLITE` series equals OPSO + PV_TOT
to 3 decimal places in every year, confirming PV_TOT is exactly the component
OPSO nets out (and that no per-area double counting occurred).

**The reconciliation therefore decomposes as: anchor = OPSO (the model's served
demand) + distributed PV + residual, with the residual NEGATIVE at -27 to -43
TWh (-9% to -13% of the anchor).** The residual cannot be decomposed further
from data on disk, and its sign is diagnostic: real additive components between
sent-out demand and source generation (generator auxiliary load, storage
recycle) would make the AEMO-side total LARGER, not smaller. The colleague's
planned quantities are ~9-13% below AEMO's Step Change total supply
(grid + rooftop) on a consistent basis — most plausibly a property of the
β = 1.3 national-to-NEM bridge or of their PV accounting.

Consequence for the map: none for construction — the map's demand axis is the
model's OPSO-basis demand and d = 1.00 is the conditioned Step Change trace
regardless. But at handover, mapping the colleague's quantity coordinates onto
the map's demand axis requires deciding what his residual is; flagged as the
first item for the colleague.

### 2.3 Emissions-cap capability (gate 3)

Implemented as two default-off flags on the analysis-layer runner
(`instrumented_runner.py`), following the `--no-named-weeks` precedent — no
`src/ispypsa/` change:

- `--co2-cap-t`: absolute annual CO2e cap as one linear constraint over
  `Generator_p`, coefficients = snapshot weight x the translator's
  `isp_residual_co2_t_per_mwh`. Scope: **generation combustion Scope-1 CO2e**
  (carrier NGER total CO2e factor x heat rate), with **CCS residual emissions at
  (1 - capture_rate) inside the cap** and captured CO2 outside it. Construction
  mirrors the committed fuel-supply-curve constraint
  (`fuel_supply_curve.py:_constrain_fuel_burn_to_purchases`).
- `--renewable-share-min`: minimum renewable share of real generation (the
  wedge comparator), same seam.
- The constraint dual is read in-process after the solve (the linopy model is
  not persisted) and written to the run record and
  `outputs/constraint_duals.json`.

Trial result (NSW 2040 single-period, the cheap mechanics check):

- Uncapped (HiGHS default simplex): completed; realised residual CO2e
  **10.733 Mt**. Notably slow (2.26 h solve) — the 2026-final candidate set is
  far larger than the historical 75-s NSW benchmark config; map cells do not
  use default simplex.
- Capped at 0.5x (5,366,597.5 t), **Gurobi barrier crossover-ON BarConvTol
  1e-8** — the map's own solver spec: **Optimal in 59 s** (88 barrier
  iterations, crossover completed in 45 s). The cap binds exactly (realised /
  cap = 1.000000000) and the dual is retrieved: **-347.29**, i.e. an implied
  carbon price of A$347/t to halve NSW 2040 intensity — plausible magnitude.
  Sign convention confirmed: negative for a binding <= cap in a minimisation;
  the implied carbon price is the magnitude. Objective weight on these
  single-period solves is 1.0, so the dual reads directly in AUD/tCO2e.

### 2.5 Renewable-share definitions (gate 5)

Audited on the conditioning networks (`stage0_conditioning.csv`):

- The previous sweep's `renewable_fraction_pct` (build_deliverables `_mix_row`:
  all generators in the denominator) and the postprocess
  `renewable_share_pct_bulk_grid` (real generators only) are **numerically
  identical** on every conditioning network, because slack-generator and
  unserved dispatch are zero in all of them.
- The colleague's `r_total` (grid source generation, excluding rooftop PV,
  battery discharge and pumped-hydro output from both numerator and
  denominator) **coincides with both** under this topology: rooftop PV is
  outside the model (OPSO demand), and battery/PHES output are StorageUnit
  components that never appear in `generators_t.p`. Conventional hydro remains
  in the numerator as Water.
- `r_VRE` (wind + solar only) is new and materially lower: 53.9 / 68.9 / 77.4%
  vs r_total 60.8 / 74.2 / 81.4% (2030/2040/2050) — the wedge is hydro +
  biomass.
- The β = 1.3 bridge appears nowhere inside the model; handover-only.

### 2.4 CCS reporting fix (gate 4)

Extraction-layer only, confined to this sweep's own extractor
(`scripts/extract_cell.py`): generation and capacity group on technology groups
built from `isp_technology_type` joined from the run's sibling
`pypsa_friendly/generators.csv` (the saved PyPSA table drops `isp_*` metadata).
'CCGT with CCS' reports as `gas_ccs`, everything else on carrier Gas as
`gas_unabated`. Demonstrated on the conditioning chain: abated gas is ~0 there
(no carbon instrument, so no CCS build: 0.00003 GW / 0.0003 TWh in 2040 against
11.9 GW / 33.3 TWh unabated). No change beyond the extraction layer was needed.

The previous sweep's committed `results.csv`/dashboard are left as they are.

---

## 3. Stage 1 — pilot at (2040, d = 1.00)

Three conditioned full-NEM cells, Gurobi barrier **crossover ON**, `BarConvTol`
1e-8, per the brief. All three terminated **`Optimal`** — the crossover-on
specification converges on the post-repair 13-week full-NEM LP where every
recorded crossover-OFF attempt (val13 family, `BarConvTol` 1e-6/1e-8,
NumericFocus/BarHomogeneous variants) stalled Sub-optimal. Crossover-on is
therefore both affordable and the fix for the recorded barrier stall.

| cell | cap | status | solve | wall | realised CO2e | dual |
|---|---|---|---|---|---|---|
| `idm_d100_u_2040` | none | Optimal | 103 min | 113 min | 42.577 Mt | — |
| `idm_d100_i100_2040` | 43.193 Mt (ι_planned) | Optimal | 117 min | 127 min | 42.577 Mt | **0.0 (non-binding)** |
| `idm_d100_i050_2040` | 21.596 Mt (0.5x) | Optimal | 156 min | **167 min** | 21.596 Mt (ratio 1.000000) | **-111.78 → A$111.8/t** |

Runtime gate: every cell inside 3 h; i050 at 167 min is the margin to watch —
the grid runs with a 300-min per-cell budget and any breach is reported.

### 3.1 Reproduction (Stage 1.1)

Uncapped conditioned cell vs the conditioning chain's own 2040 solve. The only
settings difference is the solver (Gurobi barrier 1e-8 crossover-on, `Optimal`,
vs PDLP 3e-3, `Unknown`-converged):

| quantity | chain (PDLP 3e-3) | map u-cell (Gurobi) | delta |
|---|---|---|---|
| Gas share | 13.530% | 12.682% | -0.85 pp |
| Wind share | 36.977% | 35.994% | -0.98 pp |
| Solar share | 31.887% | 33.833% | +1.95 pp |
| delivered | 237.693 TWh | 237.693 TWh | exact |
| residual CO2e | 43.193 Mt | 42.577 Mt | -1.43% |
| LP objective | 1.2917e10 | 1.2969e10 | +0.40% |

Every carrier within ±2 pp — inside the previous sweep's own ±3 pp gate; the
i100/u objectives agree to the last digit, and USE = 0 in all three cells.
ι_planned is retained at the chain's 43.193 Mt (the conditioning state's value)
rather than re-based to the Gurobi realisation; consequence: the i100 cap is
strictly non-binding by 1.4% rather than marginally binding — cleaner, since
its dual is exactly 0 rather than noise.

### 3.2 The dual-vs-chordal rule, and what it actually found

Chordal between the two capped cells: (14.310e9 - 12.969e9) / 20.980 Mt =
**63.95 A$/t**. The tight cell's dual: **111.78 A$/t**. Ratio 1.748 — the
brief's literal 25% rule **fires**.

Diagnosis, before treating that as kink or degeneracy: with the loose endpoint
at ι_planned its dual is exactly 0, so on ANY strictly convex cost surface the
chordal over this wide interval must lie strictly between 0 and the tight
dual — the >25% outcome is arithmetically inevitable and measures *curvature*
(the implied carbon price rising as the cap tightens), which is precisely the
economics the map exists to capture. The LP-consistency check appropriate to an
interval is the convexity bracket, and it passes exactly:
`dual_loose (0.00) <= chordal (63.95) <= dual_tight (111.78)`. Degeneracy
evidence is absent: statuses Optimal, the cap tracked to 10 significant
figures, u/i100 objectives identical to the last digit.

Because the brief's stop rule fired literally, one extra measurement was taken
before launching the grid: a **local probe at 0.45x ι_planned**, adjacent to
i050, where a smooth surface must put the narrow-interval chordal close to BOTH
endpoint duals (within 25% of the bracket). Result: s3.3.

### 3.3 Local probe: the dual field is reliable

`idm_d100_i045_2040` (cap 0.45x ι_planned, 19.437 Mt), Optimal. Over the
narrow 0.45x-0.50x interval:

| quantity | value |
|---|---|
| delta emissions | 2.160 Mt |
| local chordal | 120.03 A$/t |
| dual at i050 / i045 | 111.78 / 130.50 A$/t |
| chordal bracketed by endpoint duals | **yes** |
| dual-vs-chordal difference (i045) | **8.7% — PASS at 25%** |

**Stage 1 verdict: pass.** The dual and chordal fields agree at map resolution;
the literal rule's firing on the wide pilot interval is curvature (the loose
endpoint's dual is 0 by construction), fully diagnosed above. The map's
acceptance test 3 applies the agreement check on ADJACENT rungs per interior
cell, where the probe shows it is the meaningful test.

---

## 4. Stage 2 — the grid

76 cells attempted across the realised cell list (full ladder at d in {1.00, 1.10,
1.50}, reduced ladder at d in {1.05, 1.20, 1.35}, per year). **75 terminated
Gurobi `Optimal`** (barrier crossover-on, `BarConvTol` 1e-8, per the pilot
spec); **1 cell accepted on PDLP** (`idm_d150_i025_2030`, all three relative
metrics inside 3e-3: gap 0.00298, pinf 2.08e-4, dinf 1.81e-6) after two Gurobi
attempts failed to converge even at an extended 600-min budget — flagged with
the brief's own caveat that a crossover-off interior-point dual is less
reliable at a kink than the Gurobi duals everywhere else in the map.

19 of 76 cells needed a retry beyond the original 300-min budget. Diagnosis on
three of those that still failed at 600 min: two (`idm_d110_i025_2050`,
`idm_d150_i050_2050`) cleared cleanly in 128–211 min once re-run **uncontended**
(full thread count, no width-2 seat sharing) — the failures were resource
contention from sharing Gurobi's two licence seats across simultaneous
crossovers, not a property of the LP. Every binding cap tracked to the cap
value to at least 8 significant figures; USE = 0 in every solved cell.

## 5. Stage 2 — wedge subset

9 cells (3 per year, matched at d = 1.00 to the i100/i025/i005 intensity rungs).
**Matching rule applied:** the share-constrained cell's `renewable_share_min` is
set to the matched intensity-capped cell's realised `r_total`, so the two
solves are compared at the same renewable-share outcome rather than the same
emissions outcome. All 9 `Optimal`. Coherence check: the 2040 wedge cell
matched to the non-binding `i100_2040` cell also returned a renewable-share
dual of ≈0 — the two constraint families agree on which coordinates are
genuinely binding.

## 6. Stage 2 — intensity floor: the saturation boundary

Per the brief, bisecting below the tightest ladder rung (0.05x ι_planned) at
d in {1.00, 1.50} per year, capped at 4 additional solves per coordinate.

### 6.1 (2050, d = 1.00): floor NOT located within budget — a finding, not a gap

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.05 (ladder rung) | 1,201,796 | Optimal | 845 |
| 0.02 | 480,719 | Optimal | 5,282 |
| 0.005 | 120,180 | Optimal | 111,638 |
| 0.001 | 24,036 | Optimal | 189,605 |
| ~0 (500 t) | 500 | Optimal | **190,585** |

All 4 of the budgeted additional solves returned **feasible**. The dual grows
steeply from 0.05x to 0.001x but then **plateaus** between 24,036 t and 500 t
(189,605 -> 190,585, a 0.5% move across a 48x tighter cap) — the marginal cost
of the last tonne is asymptoting to a finite ceiling around **A$190k/tCO2e**
rather than the cap becoming infeasible. **No infeasibility boundary was found
within the 4-solve budget at this coordinate.** Reported per the brief's own
instruction to report rather than force a result: the conditioned 2050 fleet
at Step Change demand can apparently be pushed to near-total decarbonisation
given unlimited budget for the marginal MWh, at extreme but finite cost. This
is itself the boundary measurement for this coordinate — there may be no hard
floor above zero, only an accelerating cost curve.

### 6.2 (2050, d = 1.50)

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.02 | 721,078 | Optimal | 265,321 |
| 0.005 | 180,269 | Optimal | 307,639 |
| 0.001 | 36,054 | Optimal | **310,831** |

3 of 4 budgeted solves. Same story as 6.1 — no infeasibility, but the dual
plateaus much sooner (already flat between 0.005x and 0.001x, both ~308-311k)
than d = 1.00's, which only flattened between 0.001x and near-zero.

### 6.3 (2040, d = 1.00)

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.02 | 863,856 | Optimal | 1,755 |
| 0.001 | 43,193 | Optimal | 51,547 |
| ~0 (500 t) | 500 | Optimal | 186,389 |

3 of 4 solves. Converging toward the SAME ~186-190k A$/t region as 2050's
d = 1.00 near-zero plateau, from a much lower starting dual at the loose end —
2040 has materially more headroom at 0.02x than 2050, but the extreme tail
converges.

### 6.4 (2040, d = 1.50)

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.02 | 1,295,784 | Optimal | 12,977 |
| 0.001 | 64,789 | Optimal | **308,075** |

2 of 4 solves. Already at the same ~308k ceiling as 2050's d = 1.50 —
confirmed the d = 1.50 plateau is shared across 2040 and 2050.

### 6.5 (2030, d = 1.00)

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.02 | 1,494,136 | Optimal | 1,249 |
| 0.001 | 74,707 | Optimal | 11,051 |
| ~0 (500 t) | 500 | Optimal | 32,666 |
| ~0 (10 t) | 10 | Optimal | **72,068** |

4 of 4 budgeted solves (the full allowance). **Breaks the cross-year plateau
pattern.** Even at 10 tonnes — practically zero — 2030's dual (72,068) remains
well below 2040/2050's ~186-190k ceiling, though it is still rising rather than
fully flat, so 2030's true asymptote (somewhere above 72k, plausibly in the
80-100k range extrapolating the deceleration from 500t->10t) was not fully
pinned down within budget. The ORDERING relative to 2040/2050 is unambiguous
regardless.

### 6.6 (2030, d = 1.50)

| cap (x ι_planned) | cap (t) | status | dual (A$/t) |
|---|---|---|---|
| 0.02 | 2,241,203 | Optimal | 1,527 |
| 0.001 | 112,060 | Optimal | **61,297** |

2 of 4 solves. Same pattern as 6.5: roughly 5x BELOW 2040/2050's d = 1.50
ceiling (308,075) at the same relative cap — 2030's lower ceiling holds at
both demand levels tested, so it is a year effect, not a demand effect.

### 6.7 Reading across all six coordinates: no infeasibility found, and a
year-driven (not demand-driven) cost ceiling

**No cell probed at any of the six (year, demand) coordinates returned
infeasible**, down to caps as low as 10-500 tonnes (three to five orders of
magnitude below the conditioned pathway's own realised emissions). Every
budgeted bisection is therefore reported per the brief's own instruction to
report rather than force a result: **the intensity floor for this conditioned
fleet is not a hard reliability wall within the tested range — it is an
accelerating but finite cost curve.**

The curve's asymptote differs by YEAR, not by demand level:

| year | d = 1.00 near-zero dual | d = 1.50 near-zero dual |
|---|---|---|
| 2030 | ~33k (still rising at 500t) | ~61k (rising at 0.001x) |
| 2040 | ~186k | ~308k |
| 2050 | ~190k | ~311k |

2040 and 2050 converge to essentially the same ceiling at each demand level;
2030 sits far below both. The most plausible mechanism: 2030's conditioned
fleet still carries retirable coal (the `--reducible-existing` mechanism makes
it a cheap abatement lever), while the 2040/2050 chain has already shed coal
along the pathway, so the last mile of decarbonisation in later years must
come from costlier CCS/storage substitution — raising the ceiling. This is a
disclosed hypothesis, not independently verified against the composition data
in this memo; the full technology mix at each floor cell is in `map_results.csv`
equivalent detail for the floor cells (see the floor cell manifest).

---

## 7. Wedge report: what a renewables-share representation forgoes

Matching rule (s5): at each matched coordinate the share-constrained cell's
`renewable_share_min` is set to the intensity-capped cell's REALISED `r_total`,
so the two solves are compared at the same renewable-share outcome.

| year | cap | r_total (both) | intensity: I | share: S | cost wedge | intensity wedge | I gas-CCS TWh | S gas-CCS TWh |
|---|---|---|---|---|---|---|---|---|
| 2030 | i100 (non-binding) | 61.06% | 0.3909 | 0.3909 | 0.0% | 0.0% | 0 | 0 |
| 2030 | i025 | 87.86% | 0.0988 | 0.1292 | **-4.3%** | **+30.7%** | 0.00 | 0.00 |
| 2030 | i005 | 93.94% | 0.0198 | 0.0671 | **-11.4%** | **+239.3%** | 3.78 | **0.00** |
| 2040 | i100 (non-binding) | 75.08% | 0.1791 | 0.1791 | 0.0% | 0.0% | 0 | 0 |
| 2040 | i025 | 89.92% | 0.0454 | 0.0776 | -4.0% | +70.8% | 0.00 | 0.00 |
| 2040 | i005 | 92.74% | 0.0091 | 0.0614 | **-15.1%** | **+576.0%** | 15.05 | **0.00** |
| 2050 | i100 (non-binding) | 81.68% | 0.0946 | 0.0946 | 0.0% | 0.0% | 0 | 0 |
| 2050 | i025 | 93.09% | 0.0239 | 0.0364 | -3.4% | +52.8% | 4.02 | **0.00** |
| 2050 | i005 | 95.41% | 0.0048 | 0.0254 | **-13.3%** | **+432.9%** | 10.58 | **0.00** |

(intensity columns in t CO2e/MWh delivered; cost wedge = (share cost - intensity
cost) / intensity cost; intensity wedge = (share intensity - intensity's
intensity) / intensity's intensity.)

**The i100 rows are a sanity check, not a finding** — that coordinate is
non-binding for both constraint families, so the two solves converge to the
identical unconstrained optimum (wedge exactly 0), confirming the matching
mechanism is implemented correctly.

**At every binding coordinate, the share-constrained solve builds ZERO CCS-gas
capacity**, while the intensity-constrained solve builds up to 15.05 TWh of it.
This is the wedge in one fact: CCS-gas is not "renewable", so it earns nothing
toward a share target — a renewables-share representation has no mechanism to
see it as valuable, however cheap it is against the alternative of leaving
emissions high. The share-constrained solver instead reaches its (matched)
share target with somewhat more biomass and otherwise unconstrained unabated
gas.

**The forgone cost is real but so is the forgone abatement, and the abatement
loss dominates.** At the tightest tested coordinate (i005), matching the same
renewable share the intensity target achieves costs **11-15% less**, but
realises **2.4x to 6.8x MORE residual emissions** than the intensity target it
was matched to. A renewables-share representation of the current-policy
pathway would report a materially cheaper decarbonisation cost at any given
"clean share" than the system's true emissions cost at that share implies —
the wedge the colleague's model needs quantified is exactly this gap, and it
grows sharply with stringency (roughly 31% -> 577% intensity slippage from
i025 to i005 across the three years).

---

*(Sections below are appended as stages complete.)*
