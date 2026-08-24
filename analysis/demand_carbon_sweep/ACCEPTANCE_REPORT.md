# Acceptance report — carbon price × demand sweep

Grid: 4 carbon prices {0, 150, 300, 550} AUD/tCO2e × 4 demand levels {0.8695, 1.0, 1.1, 1.2348}
× 3 milestone years {2030, 2040, 2050} = **16 scenarios, 48 period solves**. Full NEM, ISP
sub-regional topology, myopic recursive-dynamic chains.

Tests 1 and 3 are the brief's. Test 4 is Addendum 1's replacement. Test 2 is the brief's, and is
the one finding.

---

## 1. Summary

| test | quantity | result |
|---|---|---|
| **1** | zero unserved energy in every cell-period | **PASS** — 0.000 MWh in all 48 |
| **2** | gas energy share monotone non-increasing in carbon price | **4 VIOLATIONS**, all at 2030 |
| **3** | total system cost monotone non-decreasing in demand | **PASS** — 0 violations |
| **4** | termination accepted on PDLP relative metrics | **PASS** — 48/48 |
| companion | **total thermal share** non-increasing in carbon price | **PASS** — 0 violations |
| companion | **emissions intensity** non-increasing in carbon price | **PASS** — 0 violations |

The two companion tests were added because test 2 turned out to be specified on the wrong
quantity; §3 sets out why.

---

## 2. Tests that pass

### 2.1 Test 1 — unserved energy

Maximum unserved energy across all 48 cell-periods: **0.000 MWh**. Not a small number, an
exact zero in every cell.

Worth recording that this only became true on PDLP. The Gurobi barrier runs during Stage 1
returned 19.97 MWh of unserved energy on the same LP — an artifact of an interior solution with
crossover off, not a capacity shortfall, and it does not reproduce under PDLP.

### 2.2 Test 3 — cost monotone in demand

Zero violations across all 12 (year, carbon price) blocks. Total system cost rises with demand
everywhere, and the spread is large enough that the test is not vacuous:

| year | carbon | total cost, ×0.87 → ×1.23 |
|---|---|---|
| 2030 | $0/t | 7.48 → 12.71 bn AUD/yr |
| 2030 | $550/t | 14.29 → 25.92 bn AUD/yr |
| 2050 | $0/t | 17.50 → 29.01 bn AUD/yr |
| 2050 | $550/t | 23.03 → 40.60 bn AUD/yr |

Cost is the reconstructed full-fleet figure (fleet capital and fixed costs, plus fuel, plus
carbon), not the LP objective. The objective cannot be used for this test: carried capacity
enters each year's problem at `capital_cost = 0` by design, so the objective is non-monotonic
across the pathway even where true cost is not. In `sweep_c550_d087` the objective runs
7.76 → 9.99 → 6.87 bn across 2030/2040/2050 while reconstructed cost rises 14.3 → 21.6 → 23.0 bn,
carried capex climbing 0 → 6.1 → 11.6 bn.

### 2.3 Test 4 — termination

All 48 period solves accepted. Judged on PDLP's relative metrics against the requested 3e-3
tolerance, never on `model_status`, which reports `Unknown` on this LP class even when every
metric is satisfied (HiGHS logs `Model status changed from "Optimal" to "Unknown" since relative
violation of tolerances is 6.55e+03` — its own stricter internal check).

| diagnostic | worst across 48 solves |
|---|---|
| relative duality gap | 3.00e-3 (at tolerance) |
| relative primal residual | 2.17e-3 |
| largest LP | 13,935,295 rows |
| most iterations | 47,000 |
| period wall time | 118 – 313 min (mean 177) |
| total solver time | 141.5 h |

**One nuance recorded rather than smoothed over.** `sweep_c550_d110_2050` records a gap of
exactly `0.003`. HiGHS logs three significant figures; recomputing from the logged objectives
gives |p−d|/(|p|+|d|) = 6.724e7 / 2.243e10 = **2.9985e-3**, inside tolerance. PDLP terminates
early only on convergence, so a genuine limit hit surfaces as a non-`completed` status instead.
The acceptance comparison is therefore inclusive at the tolerance, and the reasoning is at the
call site in `scripts/build_deliverables.py` so it is not re-litigated.

---

## 3. Test 2 — the finding

### 3.1 What fails

Gas energy share **rises** with carbon price at 2030, in all four demand levels. It behaves as
the test expects at 2040 and 2050.

Gas share, % of generation:

| year | $0 | $150 | $300 | $550 |
|---|---|---|---|---|
| **2030** (×1.00) | **1.25** | **6.51** | **6.96** | 6.56 |
| 2040 (×1.00) | 13.53 | 10.22 | 9.37 | 7.95 |
| 2050 (×1.00) | 14.68 | 9.12 | 7.35 | 6.52 |

At 2030 gas rises as far as $300/t and only turns down at $550/t.

### 3.2 Why — coal is the fuel being displaced

Carbon pricing displaces fuels in emissions-intensity order, and coal carries roughly twice
gas's intensity. The first thing a carbon price does in 2030 is remove coal; gas backfills part
of the gap. 2030 at ×1.00:

| carbon | coal | gas | **total thermal** | CO2e intensity | avg cost |
|---|---|---|---|---|---|
| $0/t | 37.99% | 1.25% | **39.24%** | 0.395 t/MWh | 48.7 AUD/MWh |
| $150/t | 5.52% | 6.51% | **12.03%** | 0.081 | 81.7 |
| $550/t | 0.02% | 6.56% | **6.58%** | 0.022 | 96.7 |

Coal falls 38 points; gas rises 5. Total thermal share and emissions intensity both fall
monotonically. By 2040 coal starts at 12.3% and by 2050 at 4.0%, so there is little left to
displace and gas declines monotonically as the test assumed.

### 3.3 The mandated tighter re-solve confirms it is not solver slack

Per the brief, one offending cell was re-solved at a tighter tolerance with both objectives
reported side by side. `c150 / d087 / 2030`, PDLP 3e-3 against 1e-3:

| solve | gap | objective | gas share | coal share | thermal share |
|---|---|---|---|---|---|
| sweep (3e-3) | 2.97e-3 | 5,610,686,158 | 5.411% | 4.594% | 10.005% |
| **re-solve (1e-3)** | 9.98e-4 | 5,594,575,648 | **5.414%** | 4.520% | 9.934% |
| reference: c0 (3e-3) | — | — | 0.957% | 30.289% | 31.246% |

Tripling tolerance moves the objective 0.29% and gas share **+0.003 pp**, against a violation of
**4.45 pp** — a factor of roughly 1,500. The violation is economics.

The first attempt at this re-solve timed out at the 300-min budget having reached 1.38e-3; it was
relaunched at a 600-min budget and completed at 9.98e-4. Both runs are in the records
(`resolve_c150_d087_2030`, `resolve2_c150_d087_2030`).

### 3.4 Recommendation

Test 2 as written assumes gas is the marginal displaced fuel, which holds only once coal has
left the fleet. It should either be scoped to periods with negligible coal, or replaced by the
two companion monotonicities — **total thermal share** and **emissions intensity** — both of
which hold across the entire grid and express the intent (a carbon price should decarbonise)
without assuming which fuel moves first.

The four cells are reported, not excluded, per the brief.

---

## 4. Deviations from the brief and Addendum 1

Recorded so they are not silent.

1. **Per-period time limit raised twice.** Addendum 1 set 3 h. Measured 2050 solves ran
   174–241 min, so it was raised to 5 h on evidence. Two solves still exceeded that
   (`sweep_c300_d110_2050`, and the §3.3 re-solve) and were relaunched at 10 h, completing in
   313 and 337 min. Every reported solve finished inside its budget; none was truncated.
2. **A flag was added to the run harness.** `run_myopic.py` appended the two *named* stress weeks
   unconditionally, and `temporal_filters.py:145` unions the numbered and named sets, so a
   thirteen-week request silently became fifteen weeks with the two stress weeks carrying 2/15 of
   the sample against an annual frequency of 2/52. `--no-named-weeks` (default off) suppresses
   them. Without it the sample would have been stress-weighted, which is the bias Addendum 1
   existed to remove, and the week-51 sensitivity would have been meaningless.
3. **The week set is demand-matched, not naively spaced.** Both satisfy "one per four-week block".
   The naive set sat +2.536% above annual mean demand and delivered 258.455 TWh against the
   anchor's 251.925; the adopted set delivers 251.938 TWh, **+0.005%**.
4. **Validation was certified at 1e-3 while production ran at 3e-3** — stricter than production,
   the conservative direction. The 3e-3 timing quoted for the demand-matched sample is
   extrapolated from its iteration trajectory, not measured directly.

---

## 5. Artefacts

| path | what |
|---|---|
| `results.csv` | 48 cell-periods: mix, shares, capacity, cost components, emissions, USE |
| `marginals.csv` | 36 finite differences with both endpoints carried |
| `storage.csv` | storage build by duration class |
| `manifest.csv` | per-solve run id, trace directory, solver settings, convergence metrics, wall time, paths |
| `acceptance_per_cell.csv`, `acceptance_per_grid.csv` | machine-readable test results |
| `dashboard.html` | the comparative dashboard (self-contained) |

Run identifiers follow `sweep_c<price>_<demand>_<year>`. No pre-repair evidence appears anywhere
in this report, and nothing from the seven-price frontier family enters any comparison.
