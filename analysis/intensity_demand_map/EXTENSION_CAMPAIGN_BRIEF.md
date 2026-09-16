# Brief: extend the ISPyPSA histories so ShARP can install the grid pathways

Revised 2026-09-16 by the ISPyPSA owner-side agent from the original ShARP-side
draft, using the measured evidence of the completed campaigns on this branch
(`analysis/demand_carbon_sweep/`, `analysis/intensity_demand_map/`,
`RETURN_MEMO.md` x2, `MAP_ANALYSIS.md`). Target: ISPyPSA, this branch lineage.
Solve host: Optimus-NC (the machine holding all run artefacts; two Gurobi
token-server seats). A separate ShARP agent ingests the result; the two ShARP
diagnostics and their thresholds are unchanged from the original draft.

Read first: `SHARP_HANDOVER.md` (conventions), both RETURN_MEMOs (what already
failed and why). Treat every number here as a prior to re-verify.

## Goal (unchanged)

Complete grid histories installable in ShARP, passing:
1. `diagnose_menu_against_system_demand.mjs --cases=all` — every 2027 IASR
   draft scenario's grid demand trajectory reproduced by a blend of histories
   within 0.5% in every decision year through 2060.
2. `diagnose_candidates_in_system.mjs --cases=all` — every scenario solves on
   the menu with grid emissions not exceeding the default representation's
   **in every decision year, measured against the REBUILT default** (the
   checked-in grid scenario settings are dropped on substitution, and three
   IASR cases do not solve under the checked-in settings at all — the rebuilt
   default is the only well-defined control).

## Methodology position (settled by measurement — do not relitigate silently)

**The decarbonisation instrument is the absolute annual CO2e cap, not a carbon
price and not a renewable-share constraint.**

- Prices cannot reach Gap 2. The measured 2050 duality curve (d = 1.00):
  A$550/t realises 0.0136 t/MWh; the cap duals put 0.0095 t/MWh at ~A$958/t,
  0.0048 at ~A$2,284/t, and the 0.001 t/MWh class at order A$20k-110k/t
  (`map_results.csv`, floor probes in `RETURN_MEMO.md` s6). **The original
  draft's A$1000/t check chains are therefore already answered: A$1000/t lands
  near 0.009 t/MWh at 2050, an order of magnitude short of the 0.001 target.
  Do not run them** (saves ~16 solves). Keep the A$0/150/300/550 price chains
  only for menu continuity and the duality cross-check.
- Renewable share fails the brief's own diagnostic 2: at matched shares the
  share-constrained solve builds ZERO gas-CCS and realises 2.4-6.8x the
  emissions of the intensity-capped solve (wedge subset, memo s7). Share is a
  reported output, never a control.
- The cap machinery exists and its duals are validated: `--co2-cap-t` on
  `instrumented_runner.py`, caps binding to 8+ significant figures, dual field
  externally validated against the price instrument (ratio 0.999 at $550,
  2030, `duality_check.csv`).

## Authored inputs the original draft omitted (fatal without them)

**2060 and 2070 have no source data.** Every AEMO input ends ~FY2055: demand
and VRE traces, fuel and technology cost trajectories, closure schedules, the
biomethane blend table. A 2060 investment period fails loudly at timeseries
generation. The 2060/2070 milestones therefore require an authored extension,
disclosed in every export:

- Traces: reuse the FY2050 demand and VRE trace shapes, re-labelled to the
  milestone FY, demand scaled to the trajectory's target level (the same
  read-scale-write route as `build_demand_dirs.py`; extend it to relabel
  years). RefYear 2018 throughout, as all prior campaigns.
- Economics: hold every trajectory-valued input (new-entrant costs, fuel
  prices, FOM, build limits) at its last published year. No extrapolated
  declines — the post-2050 capital-drift knob remains a ShARP-side MC term,
  not a source input.
- Closures: scheduled closures beyond 2055 apply as published (Callide C /
  Millmerran 2051 are inside range); nothing new is authored.
- Label all 2060/2070 cells `authored_horizon_extension = true` in the
  manifest. ShARP already accepts this class of assumption (its own
  stationary-hold direction); a solved 2060 on authored inputs is better
  evidence than a held 2050 account, but it is not AEMO data and must not be
  presented as such.

## Harness deltas required before any run (small, named, analysis-layer only)

1. **Per-period cap schedule in chains.** `instrumented_runner.py` has
   `--co2-cap-t`; `run_myopic.py` does not thread it, and a capped CHAIN needs
   a different cap each milestone. Add `--co2-cap-t-schedule 2030:X 2040:Y ...`
   to `run_myopic.py`, threading per-period values into the existing runner
   flag. The map used single-year conditioned solves; these are full
   recursive-dynamic chains with caps active — the tranche/retention
   write-back already works under caps (the runner is agnostic) but has never
   been exercised in a chain: smoke-test one 2-period NSW chain first.
2. **Per-period demand directories.** `run_myopic.py` passes one
   `--parsed-traces-directory` for the whole chain; year-varying trajectories
   need per-period dirs (`--parsed-traces-directory-schedule`), with one
   rewritten dir per (trajectory, milestone). Every dir goes through the
   read-scale-write round trip including any 1.0 scalars.
3. **Exports.** Add curtailment (per-VRE `p_max_pu x p_nom_opt - p`, weighted)
   and biogenic CO2 (biomass burn x 1.8 kg/GJ) to the extraction; both duals
   and realised intensity are already exported. Fix the two cost defects below
   IN THE EXTRACTOR before any new extraction.

## Conventions to pin (deep caps are meaningless without them)

- **CCS disposal: flat A$89.93/t T&S adder, tranche machinery OFF**
  (`--ccs-supply-curve none --tns-price 89.93`) — continuity with both prior
  campaigns. This is knowingly optimistic: the conservative sink curve has
  ZERO connectable capacity (`CCS_SUPPLY_CURVE.md`), and at 0.001 t/MWh the
  fleet leans hard on CCS. Do not switch conventions mid-campaign; carry the
  optimism as a headline caveat on every deep cell. If ShARP needs the
  pessimistic branch, that is a separate priced campaign.
- Gas: 100% fossil convention (owner decision, on record). For NEW runs,
  un-blend the gas price (use `gas_prices` without the biomethane blend) so
  price and emissions agree; this supersedes the old histories' disclosed
  blend bias. Consequence: the corrected A$0-550 chains will NOT numerically
  match the 16 old histories — the new menu supersedes, never mixes with, the
  old one.
- Gas and biomass supply curves: central CSVs, as both campaigns
  (`gas_supply_curve_central.csv`, `biomass_supply_curve_central.csv`).
- Emissions account: `co2e_total` (residual, CCS residual inside, captured
  outside), biogenic CO2 exported separately.
- Weather: RefYear 2018 only. Demand shape fixed within each year.

## Corrections to apply first (verify, fix, prove absence)

1. **Retained-fleet FOM double count** (ShARP audit finding): the extractor
   sums `capital_cost x p_nom_opt` over all generators (which for reducible
   ECAA units IS the FOM keeping charge) AND adds `existing_fleet_fom_aud_per_yr`.
   Verify with a one-cell reconciliation against the LP objective, fix in the
   map/extension extractor only (never edit the old sweep's committed
   deliverables), and add the acceptance check: retention component == LP
   charge, once.
2. **Five inherited policy-supported 2030 assets passing the carry predicate**
   (A$120.2m/yr duplicated into 2040/2050): reproduce the audit, tighten the
   carry-exclusion (ECAA-name filter) accordingly, and re-verify on the smoke
   chain.
3. **Dubbo Firming Power Station AND Lockyer Valley GT** (both, not one):
   NaN heat rate and VOM in the IASR v7.8 ECAA summary. Patch at templating
   with the same technology medians the gas supply curve already uses. This
   matters MORE here than in the old campaign: the omitted emissions are
   ~8.5% of the cleanest cells, and every Gap-2 target cell is a cleanest
   cell.
4. **Chronology validation, solver-controlled**: the old comparison confounded
   solver and sampling. Run one full-chronology 2050 validation per core
   trajectory with the SAME solver as its sampled counterpart (accept PDLP
   for both if full-year Gurobi crossover again proves non-viable — it
   failed at 20h on the only attempt; see map memo s12.1). Measured prior:
   sampled tails understate duals ~10% and gas-CCS ~45%.

## Campaign design (amended)

Trajectories (source-NEM load, TWh at 2030/2040/2050/2060), each a
recursive-dynamic chain with year-varying demand:

- `iasr_low`: 180 / 253 / 336 / 402; `iasr_central`: 183 / 268 / 365 / 431;
  `iasr_high`: 185 / 282 / 393 / 460; brackets `iasr_low x 0.92` and
  `iasr_high x 1.08` every year.
- Note the bracket margin also absorbs delivery-bridge drift: the 0.91-loss /
  1.3-national bridge is ShARP-authored and unratified; +/-8% covers a
  revision of either factor. State this in the manifest.

Pressure ladder per trajectory:

- Prices A$0/150/300/550/t: full chains, 4 milestones (continuity + duality
  cross-check set).
- Caps: 2050 targets 0.005 / 0.002 / 0.001 / 0.0005 t/MWh on the SHARP
  DELIVERED basis. **Caps are always written into the solver as absolute
  annual tonnes, with the basis conversion shown in the manifest**: delivered
  intensity = source intensity / 0.91, so a delivered target ι_d at source
  load Q_source TWh is cap_t = (0.91 x ι_d) x Q_source x 1e6. Example: the
  2030 cap of 0.12 t/MWh delivered = 0.109 t/MWh source-basis (the map's
  ladder rungs 0.198 and 0.099 are source-basis; 0.109 sits between them at
  duals of A$73-135/t, confirming feasibility). Never quote a cap without its
  basis.
  Schedule — REVISED per the accepted ShARP-side objections (2026-09-16):
  **2030 capped at 0.12 t/MWh delivered** (low end of the IASR default range),
  2040 cap = geometric interpolation from the 2030 cap to the 2050 target,
  2060 held at the 2050 target — EXCEPT the deepest (0.0005) chain, whose
  **2060 rung tightens to 0.0001 t/MWh source-basis (near-zero)**: the rebuilt
  default's 2060 grid is 0.0-1.1 Mt and the s1/s2 scenario class sits near
  zero, so a 2060 held at 0.0005 (~0.2 Mt at 460 TWh) would fail criterion 2
  for exactly those cases. Near-zero feasibility is measured (2050 floor
  probes solved to 10-500 t at duals of A$190-311k/t). If the tightened rung
  still exceeds an s1/s2 default year, criterion 2 carries a small absolute
  tolerance at 2060 only (the default's 2060 is itself an authored trajectory,
  so a stated tolerance is defensible); record which of the two closed the
  gap. Rationale for the capped 2030: ShARP blends histories with ONE weight
  per history across the whole horizon, so a cap chain must be admissible in
  EVERY year on its own — an uncapped (A$0) 2030 at ~0.4 t/MWh strands the
  chain regardless of its 2050 depth. The A$0 2030 fleet remains represented
  by the A$0 price chains (the incumbent family) only. No change to solve
  count. Deviations from the schedule are recorded per chain.
- NO A$1000/t chains (see methodology position).

Count: 5 trajectories x 8 chains x 4 milestones = **160 annual solves** (+40
if 2070 is added), plus 1 smoke chain, plus 3-5 full-chronology validations,
plus acceptance re-solves. Same as the draft's count, with the A$1000 chains
replaced by the validations.

## Compute plan (corrected — the draft's is not executable)

- **There are 2 Gurobi seats, not 40 workers** (CSIRO token server; the map
  campaign ran width 2). PDLP allows width 3-4 (it thread-saturates).
- Measured priors on this host: sampled-week annual solves 0.7-5.2 h
  uncontended; **width-2 Gurobi crossover contention caused every timeout in
  the map campaign** (19 of 76 cells; all cleared uncontended). Deep-cap +
  high-demand cells are the slow class (up to 10 h).
- Certification: Gurobi barrier crossover-on `BarConvTol 1e-8` (the validated
  spec for sampled LPs, and the duals are the product). Budget 300 min/cell
  first pass, 600 min uncontended retries, PDLP 1e-3 as the recorded fallback
  with gap exported.
- Realistic wall-clock: ~480 solver-hours central at mean ~3 h; at effective
  width ~3 (2 Gurobi seats + contention losses) that is **7-10 days**, not
  12 hours. 2060 cells and deep caps skew slower. Record host, threads, and
  contention (concurrent solves) per record — the old records did not.
- Chains are sequential internally: 8 chains x 5 trajectories = 40
  independent lanes; the binding constraint is seats, not lanes.

## Acceptance before handover (amended)

1. Convex-hull demand coverage through 2060 (diagnostic 1, `--cases=all`).
2. Per trajectory, at least one history at or below 0.001 t/MWh in 2050,
   held through 2060. If a cap is infeasible-in-practice, the LP will shed
   load rather than report infeasible (USE is an emission-free slack at
   A$10k/MWh): **the boundary criterion is USE > 0, and any USE > 1 MWh cell
   is a boundary measurement, reported with its binding constraints, not a
   menu member.**
3. Certification: Gurobi `Optimal`, or exported PDLP relative gap. **The
   draft's <0.1% gap bound contradicts its own PDLP fallback (3e-3 = 0.3%);
   set the bound at <=0.1% for Gurobi-certified cells and <=0.3% (PDLP 1e-3
   target, 3e-3 ceiling) for fallback cells, and let ShARP weight them.**
   Report, do not hide, which cells are which.
4. Cap tracking: realised intensity within 1% of the cap in every binding
   cell.
5. Cost-defect absence: retention charged once (acceptance query on every
   cell), no carried policy-asset duplicates, Dubbo/Lockyer emissions present.
6. Duality spot-check: at one matched (trajectory, year), the price-chain
   realised intensity and the cap-chain dual bracket each other on the
   measured curve (the map's validated consistency test).
7. Manifest with commit, config hash, network hash, host, threads,
   concurrency, per the existing pattern plus the gaps noted above.

## Exports per cell-year (as the draft, plus)

Draft list stands (load served, generation and capacity by carrier with the
gas CCS/unabated split, storage charge/discharge, curtailment, USE, fuel burn
by carrier in PJ incl. hydrogen, co2e_total + biogenic + captured with T&S
cost, conversion expenditure decomposed with retention once, renewable share,
solver block, provenance). Add: **both duals per cell** (cap shadow price
A$/t; demand-weighted marginal supply cost A$/MWh), realised intensity on the
delivered basis, and the `authored_horizon_extension` flag.

Plus three solve-free evidence exports:

- **Per-milestone NEM operational demand** (the trace-derived series already
  in `demand_components_traces.csv`, extended to every milestone used),
  published alongside whatever national-demand denominator the ShARP side
  sources, so the stipulated 1.3 NEM-to-national factor becomes a
  year-varying evidenced series. The national denominator is not in the IASR
  data; the bridge itself remains applied only at handover.
- **The ANNUAL demand series per trajectory** (the authored year-by-year
  source loads each trajectory follows, not just its four milestone values).
  Diagnostic 1 tests every IASR decision year (2027, 2029, 2033, 2037, ...);
  ShARP interpolates between milestones, and a milestone hull that covers
  every milestone can still miss an intermediate year by more than 0.5% if
  the IASR path is not linear between them. The ShARP-side fix (interpolate
  along the trajectory's authored annual demand) needs this series exported.
- **The forward-basis 2025 anchor** (`anchor_2025_forward_components*.csv`,
  already on the branch): 2025 fleet FOM and per-carrier VOM as A$/yr
  components. **The ShARP side must bridge the anchor identically to the
  cells (C = beta x kappa x C_source, beta = 1.3, kappa = 0.972411530) —
  never divide NEM-fleet A$ by the national denominator directly.** Bridged
  correctly the anchor lands near A$26/MWh delivered, ABOVE the ~A$21.5 2030
  row: a smooth join whose downward step is the measured coal-retirement FOM
  decline, not a level error. FY2025-commissioning units (11, listed
  separately) are RULED: charge FOM only, no construction annuity — the same
  decided-before-first-decision convention every ECAA committed/anticipated
  unit already gets in every cell. Storage FOM is zero in the IASR ECAA
  storage table; leave it out UNIFORMLY (cells and anchor alike) rather than
  patching the anchor alone.

## Staging (gate the spend — the prior campaigns' pattern, kept because it
caught every defect early)

- **Stage 0**: harness deltas + corrections + one NSW 2-period capped smoke
  chain; verify cap binding, tranche carry under caps, per-period demand dirs,
  FOM-once acceptance query. Nothing else runs until this passes.
- **Stage 1**: one full pilot chain (`iasr_central`, 0.001 cap, 4 milestones)
  at production settings. Gates: every milestone certified or fallback-
  converged; USE = 0; cap tracking <=1%; wall time per milestone <=10 h. The
  2060 milestone exercising the authored extension is the novel risk — if it
  fails structurally (build limits, REZ caps at 431 TWh), stop and report
  before the grid.
- **Stage 2**: the 40 chains, price chains first (they are the fast,
  well-understood class), then caps shallow-to-deep so infeasibility
  boundaries are approached with context.
- Surface-and-pause on: any Stage 0/1 gate failure; USE > 0 above the 0.001
  cap class; the 2060 authored extension proving structurally infeasible at
  `iasr_high x 1.08`; solver certification failing on >20% of a class.

## Handover (as the draft)

Absolute-profile bundle, non-default and selectable; incumbent family = the
corrected A$0 histories; both diagnostics rerun `--cases=all`; promotion is
the electricity author's decision after bridge ratification. The 16 old
histories and the 109-cell map remain evidence, superseded as menu members by
the corrected set — never mix the two vintages in one menu.
