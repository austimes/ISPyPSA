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

*(Sections below are appended as stages complete.)*
