# Return memo — representation contrast explainer

## 1. Working state and repair confirmation

Branch `docs/representation-contrast`, cut from `storage-menu-repair` at **`f40138a`** (clean tree
at start). All four gas-share investigation repairs are present in that state:

| Repair | Commit | Date | Evidence used |
|---|---|---|---|
| PHES storage-candidate inclusion | `7d4acbe` | 2026-08-14 | commit subject "repair the storage menu - offer the IASR PHES candidates"; corroborated by `analysis/calibration/STORAGE_MENU_REPAIR.md` |
| REZ augmentation-cost regex | `7f12fd4` | 2026-08-15 | commit subject "stop the numeric-strip regex truncating 4+ digit values"; `VRE_ARTIFACT_REPAIR.md` §1 records the measured blast radius (REZ augmentation offered 16,135 → 44,670 MW) |
| Offshore wind cap removal | `36ab6c6` | 2026-08-15 | commit subject "stop the onshore land-use limit pinning offshore wind to zero"; `VRE_ARTIFACT_REPAIR.md` §2 |
| ECAA VRE/hydro FOM mapping | `78267c3` | 2026-08-15 | commit subject "source ECAA VRE and hydro FOM from the per-station table"; `VRE_ARTIFACT_REPAIR.md` §3 (274 of 336 rows were `pd.NA` before) |

Repair boundary for run selection: **`78267c3`, committed 2026-08-15T12:57:27+10:00**. A solved run
counts as post-repair only if it started after that instant.

Independent corroboration rather than commit messages alone: re-extracting
`menurep_gbc_c550_2050` (pre-VRE-fix) and `vrefix_gbc_c550_2050` (post) from their solved networks
reproduces the repair memo's headline movement exactly — gas 53.27 → 31.29 TWh, wind 115.65 → 135.78
TWh. That is the repairs' signature in the solved output, not just in the log.

## 2. Run inventory

411 bench records were scanned. Ranked by start time against the repair boundary:

### Post-repair, usable

| Run | Started | Scope | Carbon price | Status |
|---|---|---|---|---|
| `vrefix_gbc_c550_2050` | 2026-08-15 12:58 | full NEM, 2050, full-year 30-min | $550/t | completed; PDLP 3e-3, `model_status: Unknown`, accepted on the standing convergence criterion |
| `ccscon_gbc_c550_2050` | 2026-08-16 13:26 | full NEM, 2050, full-year 30-min | $550/t | completed; conservative CCS sink tranches |

### Post-repair, unusable

| Run | Why |
|---|---|
| `ccsopt_gbc_c550` | **timed out** at 86,401 s (24 h) with `capacity_extract_error`. No usable result. |

### Pre-repair (not used for any model number on the page)

Everything else, including the entire seven-carbon-price frontier families (`frontier_ccx`,
`frontier_2026`, `frontier`, `frontier_storage`) and the `menurep_*`, `gbcfy_*`, `gscfy_*`,
`basrw2_*`, `gscrw2_*` chains. `menurep_gbc_c550_2050` is quoted once, explicitly as the *pre*-repair
side of a repair comparison, and never as a marginal quantity.

### The two gaps this inventory exposes

1. **No post-repair carbon-price variation.** Both usable post-repair runs sit at $550/t. Every
   run set with carbon-price variation predates all four repairs.
2. **No demand variation anywhere, at any vintage.** `run_myopic.py` exposes no demand-scaling
   argument, and neither does the ISPyPSA config schema. There has never been a demand-perturbation
   pair in this repository.

Both gaps fall squarely on the brief's centrepiece, so perturbation solves were required rather than
optional.

## 3. Perturbation solves

### How demand was perturbed without touching the repository

`run_myopic.py` accepts `--parsed-traces-directory`. A scaled trace root was built in the session
scratchpad by `make_scaled_traces.py` (copied into this directory for the record):

- `isp_2026/demand/scenario=Step%20Change/reference_year=2018/data_0.parquet` rewritten with the
  `value` column multiplied by the scale factor;
- `isp_2026/project` and `isp_2026/zone` (the VRE traces) junctioned back to the real store, so the
  two arms differ in demand and in nothing else.

**Both** arms read a rewritten parquet — the reference arm was built at scale 1.00 rather than
pointed at the original — so a parquet round-trip cannot masquerade as a demand effect. Verified
sums: 14,218,933,048 → 14,218,933,048 MW-halfhours at 1.00, and → 15,640,826,352 at 1.10.

No repository file was modified. The generated configs, run directories, records and logs land under
`analysis/benchmarks/`, which the root `.gitignore` excludes (`.gitignore:198:/analysis`), so none of
them can be committed by accident.

### Design

A 2 × 2: demand (reference, +10 per cent) × carbon price ($0/t, $550/t). Held across all four:
New South Wales only, 2040, three representative weeks (numbered week 42 plus the named
residual-peak-demand and peak-demand weeks) at 30-minute resolution, IASR 7.8 Final, 2026 trace
store, single weather reference year 2018, gas and biomass supply curves on, conservative CCS sink
tranches, `tns_price` 0.

Solver: **Gurobi 11.0.3, Method 2 (barrier) with crossover left on, `BarConvTol` 1e-8.** Crossover
was kept deliberately so the solution is basic and the duals are exact — the production PDLP
configuration returns `model_status: Unknown` and approximate duals, which would not support a
marginal-price claim.

### Results

| Arm | Demand root | Carbon price | Termination | Solve | Wall | LP rows | Served demand | Objective | Unserved |
|---|---|---|---|---|---|---|---|---|---|
| `repcon_d100_c0_2040` | traces_d100 (reference) | $0/t | **Optimal** | 34 s | 494 s | 838,877 | 89,895 GWh | 6,681.6 AUD m | 0.0 MWh |
| `repcon_d110_c0_2040` | traces_d110 (+10 per cent) | $0/t | **Optimal** | 36 s | 493 s | 838,877 | 98,884 GWh | 8,063.1 AUD m | 0.0 MWh |
| `repcon_d100_c550_2040` | traces_d100 (reference) | $550/t | **Optimal** | 39 s | 483 s | 838,877 | 89,895 GWh | 10,390.0 AUD m | 0.0 MWh |
| `repcon_d110_c550_2040` | traces_d110 (+10 per cent) | $550/t | **Optimal** | 34 s | 484 s | 838,877 | 98,884 GWh | 13,090.2 AUD m | 0.0 MWh |

Marginal quantities, each the difference of the two totals above divided by the demand difference:

| Carbon price | Δdemand | Δcost | Δemissions | Marginal cost | Average cost | Marginal intensity | Average intensity |
|---|---|---|---|---|---|---|---|
| $0/t | 8,989 GWh | 1,381.4 AUD m | 2,559.0 kt | **153.67** AUD/MWh | 74.33 AUD/MWh | **0.28466** t/MWh | 0.11940 t/MWh |
| $550/t | 8,989 GWh | 2,700.2 AUD m | 1,585.9 kt | **300.37** AUD/MWh | 115.58 AUD/MWh | **0.17642** t/MWh | 0.05078 t/MWh |

Marginal generation share by carrier (Δgeneration ÷ Δdemand):

| Carrier | $0/t | $550/t |
|---|---|---|
| Gas | +0.775 | +0.444 |
| Solar | +0.137 | +0.214 |
| Wind | +0.076 | +0.343 |

**Component check on the $550/t marginal cost.** Of the 2,700.2 AUD m cost difference, the carbon
payment on the emissions difference accounts for 550 x 1,585,900 t = 872.2 AUD m, or 97.03 AUD/MWh
of the 300.37 AUD/MWh marginal. The residual resource-cost marginal is therefore 203.34 AUD/MWh.
Nothing is left over: the two components sum to the whole.

**Why the marginal cost exceeds the average in every arm.** Serving 10 per cent more demand requires
new build at sites and network positions the model did not already want. The ratio is 2.07x at $0/t
and 2.60x at $550/t. A flat per-unit row charges 1.00x by construction, which is the distortion the
explainer exists to make visible.


## 4. Claims table

The full claims table is rendered in the explainer itself (section 5), generated from the same data
object the charts read, so it cannot drift from them. Summary of composition:

- **model output**: 38 entries, each naming its run identifier and the result file or LP field it comes from
- **design note (Aug 2026)**: 15 entries, quoted verbatim from the appendix
- **stylised illustration**: 3 entries, all three being block-curve drawing parameters the design note
  does not specify (the renewables adder, the thermal overflow price, and the block widths). Each is
  labelled in the table with the words 'NOT in the design note'.
- **total**: 56 entries

No number appears in a chart that is absent from this table, because both are generated from the same
data object.


## 5. Model output vs design note vs stylised

**Model output** (38 numbers). Two sources, never combined:

1. `vrefix_gbc_c550_2050` — full NEM, 2050, $550/t. Supplies the LP dimensions for the decision-structure
   chart, the renewable-share tile, and the generation/served-demand figures. Re-extracted from the solved
   network rather than quoted from the run report; the extraction reproduces the repair memo's numbers exactly.
2. `repcon_d100/d110 x c0/c550` — the four perturbation solves. Supply every marginal quantity: marginal
   cost, marginal emissions intensity, and the marginal generation share by carrier.

**Design note (Aug 2026)** (15 numbers). The five pathways' 2030 and 2050 cost and intensity, the 2025
anchor, the 79.6 per cent renewable prose claim, the 254 TWh calibration demand, the 0.915 implied thermal
intensity, the 4.9x ratio, and the ~0.9 thermal overflow intensity. Used verbatim. Two of the note's derived
quantities were checked and both reproduce exactly: 0.1867 / 0.204 = 0.915196, and 1 / (1 - 0.796) = 4.902.
Nothing was adjusted.

**Stylised illustration** (3 numbers). The renewables cost adder (40 AUD/MWh), the thermal overflow price
(110 AUD/MWh) and the nominal block widths (25 TWh). The design note explicitly leaves the adder unspecified.
These exist only so the three-block curve can be drawn, and they were **not** tuned to match the ISPyPSA
result — the block curve lands at 1.25x and 1.46x while ISPyPSA measures 2.07x and 2.60x, and that gap is
an artefact of the stylised adder, not a finding about the proposal's calibration. The page says so.


## 6. Verdict

**Done.** All three contrasts are built on real solved runs, and the load-bearing check is met: every
marginal quantity labelled 'model output' is computed from two solves differing only in the perturbed
dimension, with both totals and the difference shown component-by-component in the explainer's own table.
No stylised number stands in for a model result anywhere.

Three things are worth your attention rather than being buried:

1. **The demand perturbation required a route the harness does not advertise.** There is no demand knob in
   `run_myopic.py` or the config schema, and there never has been. Scaling the parsed demand trace and
   pointing `--parsed-traces-directory` at it is a clean, no-code-change route, and it is probably worth
   knowing about for future sensitivity work. Both arms read a rewritten parquet so the round-trip itself
   cannot masquerade as a signal; the resulting demand ratio came out at exactly 1.1000.

2. **The 'which world' flip is real but partial, and the page says so.** The marginal megawatt-hour goes
   from 78 per cent thermal at $0/t to 44 per cent thermal at $550/t. It crosses the halfway line, so the
   qualitative claim holds, but gas is still the single largest contributor at $550/t. The page reports the
   thermal/renewable split rather than 'mostly gas' or 'mostly renewables', because the latter would be
   true-but-misleading in one direction or the other.

3. **The palette validator could not be executed.** `node` is not installed on this machine, so
   `scripts/validate_palette.js` could not be run. The mitigation was to use the dataviz skill's documented
   default palette unchanged and in fixed slot order, which is exactly the condition under which its published
   validation results apply (slots 1-3 clear the all-pairs floors in both modes; the adjacent pairlist clears
   for all eight). Charts also carry legends plus a table view, so identity is never colour-alone. This is a
   disclosed gap, not a claimed pass.

**Not pushed.** The branch `docs/representation-contrast` is local. Run artefacts under
`analysis/benchmarks/` are gitignored and were not committed.

