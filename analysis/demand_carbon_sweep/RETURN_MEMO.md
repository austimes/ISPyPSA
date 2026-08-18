# Post-repair 4x4 carbon price x demand sweep: return memo

**Verdict: STOPPED before Stage 2.** Stage 0 is complete and delivered. No cells were built.

Sections 1 to 4 below are the original return, which established that the brief's Stage 1
premise was wrong. Addendum 1 accepted that, banked Stage 0, and replaced Stage 1 with a
13-week even-sampling gate. **Section 8 is the current state and supersedes section 5.** In
short: the replacement sampling gate PASSES, the solver gate FAILS, and the pause is now
narrowly about how termination is judged rather than about the sweep's design.

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

---

## 8. Stage 1 under Addendum 1: sampling passes, the solver does not

Supersedes section 5. Addendum 1 withdrew Config A and Config B, banked Stage 0, and set the
sampling to thirteen evenly spaced weeks at 30-minute resolution with week 51 deliberately
**not** forced in.

### 8.1 An implementation problem that had to be solved first

`run_myopic.py`'s config writer appended the two named stress weeks unconditionally, and
`temporal_filters.py:145` **unions** the numbered and named sets. Asking for thirteen even
weeks therefore produced **fifteen**, two of them the stress weeks, carrying 2/15 = 13.3% of
the sample against an annual frequency of 2/52 = 3.8%. That is the same overweighting mechanism
Addendum 1 set out to remove, and it would also have made the week-51 sensitivity meaningless.

Added `--no-named-weeks` to the run harness (analysis-layer orchestration, not `src/ispypsa/`),
default off. Verified across all three states:

| flags | `representative_weeks` | `named_representative_weeks` |
|---|---|---|
| default | `[2, 6, 10]` | `[residual-peak-demand, peak-demand]` (unchanged) |
| `--no-named-weeks` | `[2, 6, 10]` | `~` |
| `--full-year` | `~` | `~` (unchanged) |

### 8.2 The sampling gate PASSES, and even spacing is what did it

`val13_c550_2050`: 13 even weeks at 30 min, the anchor's own carried tranches, Gurobi Method 2 /
Crossover 0 / `BarConvTol` 1e-6. LP 15,057,871 rows / 6,862,940 columns / 29.1M nonzeros,
presolved to 4,705,263 rows.

| quantity | 3-week (withdrawn) | **13 even weeks** | gate |
|---|---|---|---|
| gas share delta vs anchor | +2.903 pp | **-1.183 pp** | +/-3 pp **PASS** |
| wind share delta | -11.167 pp | **+0.966 pp** | reported |
| solar share delta | +8.638 pp | +0.314 pp | reported |
| wall clock | 0.28 h | **1.26 h** | 4 h **PASS** |

Full mix (% of generation): wind 52.893 (anchor 51.927), solar 32.032 (31.718), gas 10.785
(11.968), water 3.654 (3.761), biomass 0.636 (0.618).

The week count was not the fix; the even spacing was. Thirteen stress-weighted weeks would have
inherited the three-week bias, which is why 8.1 mattered.

### 8.3 Week-51 sensitivity (report only, not a gate)

| sample | gas share |
|---|---|
| week 50 in slot (even spacing) | 10.785 % |
| week 51 in slot (stress week swapped in) | 13.476 % |
| **movement** | **+2.691 pp** |
| full-year anchor | 11.968 % |

Both samples sit inside the 3 pp gate, but the **even sample is closer to the anchor** (-1.18 pp)
than the stress-loaded one (+1.51 pp). Addendum 1's instruction not to force week 51 in is
confirmed by measurement: at a thirteen-week sample size a deliberate stress inclusion
overshoots.

### 8.4 The solver gate FAILS, and the mandated re-solve does not rescue it

| run | `BarConvTol` | status | gap | pinf | dinf | objective |
|---|---|---|---|---|---|---|
| `val13_c550_2050` | 1e-6 | Sub-optimal | 3.73 | 0.0806 | 0.00349 | none |
| `val13x_c550_2050` (mandated re-solve) | **1e-8** | Sub-optimal | **4.05** | 0.112 | 0.00303 | none |
| `val13s51_c550_2050` | 1e-6 | Sub-optimal | 3.84 | 0.0985 | 0.0027 | none |

Against the replacement criterion (gap <= 1e-5) all three fail by five orders of magnitude. The
barrier stalls rather than diverges: over iterations 161-172 of the 1e-6 run, primal
infeasibility held at ~8.1e-02 and complementarity at ~3.7 while the objective moved in the
sixth significant figure. Tightening the tolerance made it marginally worse, as expected of a
stall.

A `NumericFocus 3` + `BarHomogeneous 1` diagnostic (not requested by the addendum; run so the
pause would be actionable) was **far worse**: iteration 85 at 2.49 h with primal infeasibility
**4.87e+01** against the baseline's final 8.06e-02, at ~120 s/iteration. Stopped as
non-viable rather than left to consume the machine.

Acceptance test 1 also fails, at 19.97 MWh of unserved energy against the anchor's zero. On
258 TWh that is 7.7e-8 of energy, consistent with a crossover-off interior point rather than a
genuine capacity shortfall.

### 8.5 Three findings that narrow the pause

1. **The stalled solutions are stable.** 1e-6 and 1e-8 on the identical sample agree to
   **0.002 pp on gas** and 0.036 pp on wind. The failure is in the convergence *certificate*,
   not in the solution. The 3.674 pp spread across the three sampled solves is almost entirely
   the week-51 *sample* difference, not solver noise.
2. **The cost deliverable survives.** Neither `extract_method_years.py` nor
   `extract_frontier_points.py` reads `network.objective`; cost is built from
   `capital_cost x p_nom_opt` plus `marginal_cost x dispatch x weightings`. Run against the
   Sub-optimal network it returns a complete row: 38.903 excl-fuel-carbon + 12.685 fuel + 3.455
   carbon = **55.04 AUD/MWh**, 258.455 TWh delivered, CO2e 0.006282 t/MWh, renewable share
   89.215 %. So total and average system cost, the finite-difference marginals and acceptance
   test 3 are all recoverable. The extractor independently flags `tolerance_robust: False`.
3. **Absent objective is not absent cost.** The `objective_value: None` in the records is a
   PyPSA reporting consequence of Sub-optimal termination, not missing information.

### 8.6 What the pause is actually about

Not the sweep's design, which is validated, and not the cost deliverable, which is recoverable.
It is narrowly: **is a stable Sub-optimal interior solution acceptable, or should the sweep move
to PDLP?** PDLP is the anchor's own solver and the recorded working path for this LP class after
the storage repair. `val13p_c550` (PDLP 1e-3, identical 13-week sample) is in flight so the
choice rests on measurement. If PDLP converges, it is the better basis on every count; if it
does not, the decision is whether to accept Sub-optimal with a stability criterion (the
1e-6/1e-8 agreement above) in place of the unreachable 1e-5 gap.

Runtime note for Stage 2: the 1.26 h validation ran uncontended on all 112 cores. Stage 2 at
four cells wide and 26 threads each will be slower per solve, so the 3-hour per-period limit has
less headroom than the validation suggests.

### 8.7 Additional artefacts

| path | what |
|---|---|
| `scripts/validate_sampling.py` | the Stage 1 gate comparison |
| `scripts/run_sweep.py` | the 16-cell driver (built, dry-run verified, not yet run) |
| `scripts/build_deliverables.py` | results, storage, marginals, manifest, acceptance tables |

Run identifiers: `val13_c550_2050`, `val13x_c550_2050` (1e-8), `val13s51_c550_2050` (week 51),
`val13nf_c550_2050` (NumericFocus, stopped), `val13p_c550_2050` (PDLP, in flight).

---

## 9. Solver settled, sampling corrected, and a live constraint conflict

### 9.1 PDLP converges where the barrier stalls

`val13p_c550_2050`, PDLP at 1e-3 on the even 13-week sample:

| metric | value | target |
|---|---|---|
| `pdlp_final_gap_rel` | 9.83e-04 | < 1e-3 |
| `pdlp_final_pinf_rel` | 2.10e-04 | < 1e-3 |
| `pdlp_final_dinf_rel` | 3.55e-06 | < 1e-3 |
| unserved energy | **0.000 MWh** | zero |
| objective | 10,118,370,749 | present |
| wall clock | 2.58 h | < 4 h |

`model_status` still reads `Unknown`; HiGHS logs `Model status changed from "Optimal" to
"Unknown" since relative violation of tolerances is 6.55e+03`, its own stricter internal
check. Termination is therefore certified on the three relative metrics, never on the status
field. Adopted for Stage 2 at the anchor's own **3e-3**.

Two corroborations of the earlier Gurobi runs: its printed objective agrees with PDLP's to
**6e-5**, and its 19.97 MWh of unserved energy does not reproduce under PDLP, confirming it as
a crossover-off interior artifact rather than a capacity shortfall.

### 9.2 The objective comparison in section 8 was on the wrong basis

The anchor was the terminal period of a five-year-step chain, so PyPSA weighted its period
objective by **4.546**; a single-period run gets 1.0. The raw ratio is ~4.5x and meaningless.
`validate_sampling.py` now divides both sides out. This is why no grid cell should be compared
against the full-year anchor on cost, as Addendum 1 already directed.

### 9.3 The even week set carried a +2.5% demand bias; the corrected set removes it

Chasing the residual cost delta found the substantive defect. A representative-week LP scales
the sample mean up to a year, so a sample whose mean demand differs from the annual mean biases
every absolute quantity.

| week set | demand bias (offline) | VRE bias (offline) | served demand (solved) | vs anchor |
|---|---|---|---|---|
| anchor, full year | — | — | 251.925 TWh | — |
| even `[2, 6, ..., 46, 50]` | +2.536 % | -0.376 % | 258.455 TWh | **+2.592 %** |
| week-51 variant | +2.464 % | -3.089 % | not solved at 3e-3 | — |
| **`[1, 6, 10, 14, 19, 22, 26, 32, 35, 39, 41, 45, 50]`** | **-0.050 %** | **+0.247 %** | **251.938 TWh** | **+0.005 %** |

The offline diagnostic (`week_demand_bias.py`) predicted -0.050 % and the solve came in at
+0.005 %, so it is reliable for choosing future samples without solving. The corrected set is
still one week per four-week block, satisfying Addendum 1's structure literally.

`val13m_c550_2050` on the corrected set: gas share **-1.768 pp** vs anchor (PASS), wind
+0.663 pp, unserved energy **0.000 MWh**, `pdlp_final_gap_rel` 1.00e-03, pinf 7.38e-05, dinf
1.28e-06.

### 9.4 The conflict that stopped the launch

The corrected sample is numerically harder: **41,520 PDLP iterations against 20,800** for the
same tolerance.

| week set | est. wall per period at 3e-3 | 3 h Stage 2 limit |
|---|---|---|
| even | ~2.2 h | fits |
| **demand-matched** | **~3.5 h** | **breaches** |

Extrapolated from the measured trajectory (0.410 s/iteration; gap crosses 3e-3 near iteration
29,500), not measured directly, because the run was launched at 1e-3 before the tolerance was
settled. At 1e-3 it took **4.90 h**, itself over Addendum 1's 4 h validation gate.

So two of the brief's own constraints now conflict: the sampling that is measurably correct on
demand cannot meet the per-period time limit. 48 period solves at ~3.5 h is on the order of a
week sequentially, and PDLP threads too aggressively for much concurrency to help. Every 2050
solve run so far has been a worst case (largest carried fleet); 2030 and 2040 are expected to be
faster but **that has not been measured**, which is the cheapest thing to establish before
committing to the full grid.
