# Post-repair 4x4 carbon price x demand sweep: return memo

**Verdict: STOPPED before Stage 2.** Stage 0 is complete and delivered. Stage 1 fired four of
the brief's own surface-and-pause conditions. No cells were built. One decision is needed.

Branch `analysis/demand-carbon-sweep`, not pushed. Run artefacts gitignored.

---

## 1. State verified against

HEAD `1f6d5c9` on `docs/representation-contrast`, branched to `analysis/demand-carbon-sweep`.
All four repairs are ancestors of HEAD and were confirmed **functionally**, not by commit subject.

| repair | commit | evidence |
|---|---|---|
| REZ numeric-strip regex | `7f12fd4` | direct call: `1660` -> `1660`, `2131000` -> `2131000`, `1,660` preserved |
| PHES candidates | `7d4acbe` | anchor network carries storage durations 9/10/12/20/24/48/159 h, 36 Water rows |
| Offshore wind cap | `36ab6c6` | anchor network builds **3.374 GW** offshore across 8 rows, not pinned to 0 |
| ECAA VRE/hydro FOM | `78267c3` | `ecaa_generators.csv`: **0 of 336** FOM values NaN; Wind 41.51, Hydro 108.06, Solar 26.79 $/kW/annum |

Re-extraction of the anchor network also reproduces the recorded post-repair mix (gas 11.97%,
wind 51.93%), which is the brief's accepted repair evidence.

---

## 2. Stage 0 findings (complete, delivered)

### 2.1 Trace provenance

The parsed store `data/trace_data_final/isp_2026/demand` contains exactly one scenario, one POE
and one demand type:

- **Scenario: Step Change**
- **POE50**
- **`OPSO_MODELLING`** (grid-served operational demand)
- 15 ISP sub-regions, 15 reference years (2011-2025)

**Implied FY2050 NEM served energy: 251.925 TWh.**

This value, recomputed independently from AEMO's raw `STEP_CHANGE_POE50_OPSO_MODELLING` CSVs,
matches the parsed store to 3 decimal places. That cross-check is what establishes the
provenance rather than assuming it.

### 2.2 Demand scalars

**Vintage correction, disclosed.** The brief names "Progressive Change" and "Green Energy
Exports". Those are 2024-ISP (workbook v6.0) scenario names. The traces here are 2026 ISP
Final (v7.8), where AEMO renamed them: Progressive Change -> **Slower Growth**, Green Energy
Exports -> **Accelerated Transition**
(`src/ispypsa/iasr_table_caching/schema_normalisation.py:681-682`; `flow_paths.py:358` notes
Green Energy Exports is no longer an ISP scenario). Ratios were therefore derived from the
2026-vintage successors. Using 2024-vintage ratios against 2026-vintage traces would be a
vintage mismatch.

AEMO's raw demand traces for **all three** 2026 ISP scenarios are present in
`iasr inputs/2026 ISP Final/`, so the scalars come from AEMO's own half-hourly data on an
identical basis (POE50, `OPSO_MODELLING`, RefYear 2018, 15 sub-regions, FY2050) rather than a
headline forecast.

| scenario | FY2050 NEM TWh | ratio to Step Change |
|---|---|---|
| Slower Growth | 219.061 | **0.869546** |
| Step Change | 251.925 | 1.000000 |
| Accelerated Transition | 311.065 | **1.234752** |

Grid: **{0.8695, 1.0, 1.1, 1.2348}**. The brief expected "near 0.9 and 1.2"; verified as 0.870
and 1.235. The 1.1 level is a disclosed assumption (an interpolated presentation level, not an
ISP scenario).

Derivation: `scripts/derive_demand_scalars.py`. Machine-readable: `demand_scalars.csv`.

### 2.3 Trace directories

Four rewritten parsed-demand directories built via the `--parsed-traces-directory` route only.
No model code, schema or committed data touched.

- Every level **including 1.0** goes through the same read-scale-write round trip, so the round
  trip cannot masquerade as a demand signal.
- VRE traces (`project/`, `zone/`) are symlinked to the one source store, identically across all
  four, so wind and solar are bit-identical between levels.
- Only `reference_year=2018` written, the cycle every cell would use. Other years fail loudly.

**Realised energy ratios, verified to 4 dp: 0.8695 / 1.0000 / 1.1000 / 1.2348 — all exact.**

Builder: `scripts/build_demand_dirs.py`.

### 2.4 CCS flat transport-and-storage adder

Authored basis exists, so the brief's stop condition does not fire. Derived from
`analysis/ccs_market/ccs_transport_adders.csv` (transport, per `CCS_SUPPLY_CURVE.md` s4.2) plus
**A$18.5/t** storage (GHD 2025 for AEMO s3.11, per s3.4), weighted by the captured CO2 each
sub-region actually carries in the anchor's solved fleet.

| summary | A$/tCO2 |
|---|---|
| **fleet-weighted (proposed)** | **89.93** |
| unweighted mean over 15 sub-regions | 104.50 |
| median over 15 sub-regions | 97.41 |

Fleet-weighted total captured: 11.854 Mt/yr. Dominated by SNW (6.775 Mt at A$102.89/t), SEV
(2.114 at 27.27), MEL (1.665 at 45.90). Derivation: `scripts/anchor_and_ccs_adder.py`.

### 2.5 Thirteen-week selection

Selected on the anchor network, which is a full-year 30-minute post-repair solve, so its
snapshots carry real FY2050 demand against real RefYear-2018 VRE availability and the real
solved fleet. Metric: residual demand = demand - (Wind+Solar `p_max_pu` x `p_nom_opt`). Weeks
indexed as ISPyPSA indexes them (`temporal_filters.py:226-229`).

**Stress week: week 51, starting 2050-06-20.** Residual energy 2,348 GWh (highest of 52), mean
VRE/demand ratio **0.651 (lowest of 52)**, peak residual 39.1 GW. Mid-winter, low VRE.

**Selected: `[2, 6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 51]`** — one per four-week block,
with the final block represented by week 51 rather than its default week 50.

Residual-energy percentiles of the selection span 17.3 to 100.0. The set is deliberately
stress-inclusive, not an unbiased sample of the year. Selector: `scripts/select_weeks.py`.

---

## 3. Stage 1: what stopped it

### 3.1 The anchor is not the configuration the brief describes

The brief calls Config A ("three representative weeks at 30-minute resolution") "the
configuration already validated post-repair". It is not.

`analysis/benchmarks/configs_myopic/vrefix_gbc_c550_2050.yaml` has
`representative_weeks: ~` and `named_representative_weeks: ~` in the `capacity_expansion`
block. The anchor is a **full-year 30-minute** solve:

| | anchor | brief's Config A |
|---|---|---|
| snapshots | **17,520** | 1,008 |
| snapshot weight sum | 8,760 h | 8,760 h |
| LP rows | **60,392,815** | 3,475,951 |
| solve time | **48,855 s (13.6 h)** | 487 s |
| solver | PDLP, tol 3e-3 | Gurobi barrier 1e-6 |
| `model_status` | **`Unknown`** | **`Sub-optimal`** |

The config file's *comment* block describes 3-week sampling; the *values* are null. The comment
is stale and is the likely source of the brief's premise.

The anchor is also the terminal period of a recursive-dynamic chain carrying **54,308.63 MW** of
generators and **6,198.51 MW** of batteries from 2030-2045 tranches, not a standalone single-year
instance.

### 3.2 Stage 1.1 fails by a wide margin, and the failure is temporal resolution

Run as a controlled experiment: `sampprobe_c550_2050` seeded with the anchor's **own** carried
tranches, so the injection matched exactly (126 generators / 89 batteries / 54,308.63 MW /
6,198.51 MW) and the reducible-existing setup matched exactly (290 units, 52,215.3 MW, keeping
cost mean 42,285.73 $/MW). The only differences from the anchor are temporal sampling and solver.

| carrier | anchor TWh | Config A TWh | anchor % | Config A % | delta pp |
|---|---|---|---|---|---|
| Wind | 135.781 | 117.252 | 51.927 | 40.760 | **-11.167** |
| Solar | 82.939 | 116.090 | 31.718 | 40.356 | +8.638 |
| **Gas** | **31.293** | **42.776** | **11.968** | **14.870** | **+2.903** |
| Water | 9.833 | 9.834 | 3.761 | 3.419 | -0.342 |
| Biomass | 1.616 | 1.712 | 0.618 | 0.595 | -0.023 |

- **Gas +36.69% relative.** Brief tolerance: 2%. Exceeded ~18x.
- **Wind -13.65% relative.** Brief tolerance: 2%. Exceeded ~7x.
- Battery build 21.514 -> 30.621 GW (+42%). PHES unchanged at 6.075 GW.
- Total system cost within 1%: **not computable**, the solver returned no objective.

The brief reads a Stage 1.1 failure as "something other than temporal resolution differs". Here
temporal resolution *is* what differs, because the brief believed Config A was the anchor's own
configuration. The three-week set is stress-weighted (residual-peak-demand, peak-demand, week
42), so it systematically over-values firm gas and under-values wind.

**This is the load-bearing finding: the sweep's diagnostic quantity is gas, and reduced
stress-weighted sampling biases gas by an order of magnitude more than the effect being
measured.** The marginal-MWh technology identity would be dominated by sampling artefact.

### 3.3 Acceptance test 1 fails on the pilot

Unserved energy: anchor 0.000 MWh, Config A **5.274 MWh**. The brief requires zero in every
cell-period.

### 3.4 Acceptance test 4 is unsatisfiable as specified

The brief specifies Gurobi barrier, crossover off, `BarConvTol` 1e-6, and requires termination
`Optimal` for every period solve.

- That exact specification returned **`Sub-optimal`** with `objective_value: None`.
- The anchor's own status is **`Unknown`** (PDLP 3e-3).

Neither the specified solver nor the anchor's solver can satisfy the test. This reproduces the
recorded post-repair behaviour that the widened storage menu breaks the Gurobi barrier.

### 3.5 Config B is not implementable without a model-code change

`src/ispypsa/config/validators.py:89`:

```python
if operational_temporal_resolution_min != 30:
    raise ValueError("config operational_temporal_resolution_min must equal 30 min")
```

Hard-validated to exactly 30, carrying a `# TODO properly implement temporal aggregation`.
`TemporalCapacityInvestmentConfig` inherits it. **Two-hour chunks require editing that
validator**, which the invariants forbid and which is its own stop condition.

Note also that `run_myopic.py --full-year`'s help text claims "Default resolution_min=60
(hourly)"; the code always writes 30, and 60 would fail validation. Stale help text.

### 3.6 The battery duration floor has no existing mechanism

Storage candidates carry `storage_duration_hours`, but no CLI flag or pre-pass filters batteries
below a duration. Implementing the >=4h floor needs a new analysis-layer pre-pass. Flagged
rather than written, per the no-code-changes invariant.

For scale: the anchor builds **5.858 GW of sub-4h batteries out of 21.514 GW** total battery
(27.2%), so the floor is not a rounding detail.

### 3.7 A further non-comparability

The anchor has `tns_price: 0.0` and no `ccs_supply_curve` block, i.e. free unlimited CO2
disposal. The sweep would apply an A$89.93/t adder. So sweep gas would differ from the anchor
for a second reason unrelated to temporal sampling.

---

## 4. Runtime arithmetic

At the only configuration with a validated post-repair anchor (full-year 30-min), one period
solve is ~13.6 h. The brief's grid is 16 cells x 3 periods = **48 period solves ~= 27 days**.
Not viable.

---

## 5. The decision needed

Reduced temporal sampling is mandatory for tractability, but the brief's Config A is
demonstrably biased on the sweep's own diagnostic quantity, and its Config B cannot be built
without a code change. Options, in the order I would rank them:

1. **Thirteen weeks at 30 minutes** (recommended). Keeps the brief's week-selection design and
   the evidenced stress week, needs **zero code change** (`--rep-weeks` accepts any list), and
   samples the year evenly instead of stress-weighting it. ~4,368 snapshots, ~15M LP rows.
   Requires one validation solve against the anchor before committing to 48, and the residual
   gas bias must be measured and disclosed rather than assumed small.
2. **Authorise the `resolution_min` change** to get the brief's Config B (13 weeks x 2 h), then
   re-validate. Cheaper per solve than option 1, but it is a model-code change to a validator
   with an open TODO, so it needs explicit sign-off and its own regression check.
3. **Full-year 30-min, fewer cells.** The only path with an existing validated anchor. Fits as
   2050-only across 3-4 demand levels (~12 solves, ~7 days) which still yields the carbon axis
   and adjacent-demand finite differences at full fidelity, but drops the 2030/2040 pathway.

Whichever is chosen, two things need settling with it:

- **Solver and acceptance test 4.** The `Optimal` requirement cannot hold. Either accept PDLP
  at a stated tolerance with a convergence-metric criterion (the anchor's own basis:
  `pdlp_final_*_rel < 1e-3`, not `model_status`), or accept Gurobi `Sub-optimal` with a stated
  check. Acceptance test 4 needs rewording either way.
- **The >=4h battery floor**, which needs either authorisation for a small analysis-layer
  pre-pass or removal from scope.

---

## 6. Caveats block (carry verbatim into any distributed output)

- Uniform demand scaling moves energy and peak together and leaves load shape untouched, whereas
  real electrification reshapes it.
- CCS is represented by a flat transport-and-storage adder (A$89.93/tCO2, fleet-weighted) pending
  the supply-curve design; the tranche machinery is excluded.
- Myopic foresight: each milestone year is solved in sequence without perfect foresight.
- Draft-accuracy solver tolerance; termination status on this LP class is not `Optimal`.
- Demand scalars are 2026-ISP Slower Growth / Accelerated Transition ratios; the 1.1 level is an
  interpolated assumption, not an ISP scenario.
- **Not yet applicable, and must be added if the sweep proceeds:** 2-hour chunk averaging shaves
  peaks and modestly understates peaking capacity; battery candidates floored at 4-hour duration.
  Both are listed in the brief but neither is in force in anything reported here.

---

## 7. Artefacts

| path | what |
|---|---|
| `demand_scalars.csv` | the four levels with ISP provenance |
| `scripts/derive_demand_scalars.py` | scenario ratios from AEMO raw traces |
| `scripts/build_demand_dirs.py` | the four rewritten trace directories |
| `scripts/select_weeks.py` | stress week and 13-week selection |
| `scripts/anchor_and_ccs_adder.py` | anchor quantities and CCS adder derivation |
| `scripts/compare_probe_to_anchor.py` | Stage 1.1 controlled comparison |

Run identifiers referenced: anchor `vrefix_gbc_c550_2050`; Stage 1.1 probe `sampprobe_c550_2050`
(Gurobi Method 2 / Crossover 0 / `BarConvTol` 1e-6, `Sub-optimal`, 3,475,951 rows, 487 s solve,
1,011 s wall).

No pre-repair evidence is used anywhere in this memo. Nothing from the seven-price frontier
family enters any comparison.
