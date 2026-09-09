# Electricity supply for ShARP: the capacity-expansion response surface

**Purpose.** Everything a fresh agent needs to translate the NEM
capacity-expansion results into ShARP's whole-of-economy optimisation, so ShARP
can select the optimal grid emissions intensity jointly with the electricity
demanded by the rest of the economy. Two complementary datasets are packaged:
a **trajectory menu** (the demand x carbon sweep — 16 whole-horizon pathways)
and a **response surface with true marginals** (the intensity x demand map —
comparative statics around the current-policy pathway, with both duals per
cell). They were produced by different instruments on the same model and have
been cross-validated against each other (s4).

Source repository: `ISPyPSA` fork, branch `analysis/intensity-demand-map`
(includes `analysis/demand-carbon-sweep` history). Working records:
`analysis/intensity_demand_map/RETURN_MEMO.md` (this map),
`analysis/demand_carbon_sweep/RETURN_MEMO.md` (the sweep). Economics read:
`analysis/intensity_demand_map/MAP_ANALYSIS.md`. Dashboards: the sweep's
cost-of-supply page (artifact `6058d274-aab9-4dab-b706-8772928cef67`) and this
map's `analysis/intensity_demand_map/dashboard.html`.

---

## 1. The object ShARP should consume

For each milestone year y in {2030, 2040, 2050}, the electricity sector is
characterised by an annual cost function over two decision coordinates:

    C(d, iota; y)   [A$/yr]
      d    = annual electricity delivered to the grid boundary (see s5 for the
             boundary), expressed as a multiple of the Step Change baseline
      iota = grid emissions intensity, t CO2e (Scope-1 combustion, CCS residual
             inside) per MWh delivered

with both partial derivatives measured directly as LP duals, per cell:

    lambda(d, iota; y) = -dC/dE  [A$/tCO2e]  the implied carbon price
                                             (E = iota x delivered MWh)
    p(d, iota; y)      =  dC/dD  [A$/MWh]    marginal cost of supply
                                             (load-weighted bus price)

Measured properties ShARP can rely on:

- **C is convex and steep in iota** (duals rise superlinearly as intensity
  falls) and **near-linear and shallow in d** (marginal supply cost moves
  modestly with demand at fixed intensity). Cost is monotone in both axes
  across all 36 tested axis-lines (zero violations).
- **The dual fields are trustworthy at grid resolution**: 56/60 adjacent
  intensity pairs and 59/60 demand pairs pass a dual-vs-chordal consistency
  check; every exception is diagnosed (near-zero-denominator or weakly-binding
  boundary), none is an unexplained kink.
- **Externally validated**: interpolated at the sweep's realised intensities,
  the map's lambda reproduces the sweep's independently applied carbon prices
  at ratios 1.165 / 1.056 / 0.999 ($150/$300/$550, 2030, the
  conditioning-matched year). Details s4.

**Recommended embedding.** Per year, embed C as piecewise-linear convex in
iota at each sampled d (the LP-native representation; cell values below and in
`map_results.csv`), interpolating linearly across d. Equivalently, use lambda
directly in ShARP's first-order condition: the optimal iota* satisfies
lambda(d, iota*; y) = ShARP's economy-wide marginal damage / abatement value
at that year. Do NOT fit a smooth global functional form through the deep tail
(iota below 0.10x pathway intensity) without carrying the tail caveat in s7.

## 2. Dataset A — the intensity x demand map (marginals; this work)

Conditioned single-year solves on the model's current-policy pathway state
(the $0/t chain at Step Change demand). 78 grid cells: intensity caps
{1.5, 1.0, 0.5, 0.25, 0.10, 0.05} x iota_planned crossed with demand
{1.00, 1.10, 1.50}, plus a reduced ladder {1.0, 0.25, 0.05} at demand
{1.05, 1.20, 1.35}. Solver: Gurobi barrier crossover-on 1e-8 (75 cells
Optimal; 1 PDLP-accepted with caveat), caps binding to 8+ significant figures,
USE = 0 (max artefact 0.00036%).

The conditioning anchor (iota_planned = the current-policy pathway's realised
intensity; delivered energy at d = 1.00):

| year | iota_planned t/MWh | annual CO2e | delivered TWh |
|---|---|---|---|
| 2030 | 0.395398 | 74.707 Mt | 188.94 |
| 2040 | 0.181717 | 43.193 Mt | 237.69 |
| 2050 | 0.095404 | 24.036 Mt | 251.94 |

Core surface at d = 1.00 (full 78-cell table: `map_results.csv`):

| iota / iota_planned | 2030 cost | 2030 lambda | 2040 cost | 2040 lambda | 2050 cost | 2050 lambda |
|---|---|---|---|---|---|---|
| 1.00 | 48.6 | 0 | 76.7 | 0 | 86.2 | 0 |
| 0.50 | 57.4 | 73 | 82.8 | 112 | 91.4 | 174 |
| 0.25 | 67.3 | 135 | 90.3 | 291 | 99.0 | 513 |
| 0.10 | 77.5 | 320 | 100.6 | 532 | 108.0 | 958 |
| 0.05 | 86.1 | 597 | 106.0 | 845 | 115.1 | 2,284 |

(cost = average A$/MWh delivered; lambda = A$/tCO2e.)

Three structural facts for ShARP's formulation:

1. **The thermal-overflow direction is free.** Every cap above iota_planned
   (1.5x) is slack at every demand level including +50%: the optimiser meets
   marginal demand slightly CLEANER than the conditioned average. ShARP should
   not price an intensity penalty on demand growth at current-policy
   economics; the overflow-by-gas branch of a pathway representation never
   activates inside the sampled range.
2. **There is no hard intensity floor in the tested range — encode a price
   asymptote, not a bound.** Bisection to caps of 10-500 t (five orders below
   pathway emissions) never went infeasible. The dual plateaus at a
   year-driven ceiling: ~186-190k A$/t (2040/2050) and ~33-72k (2030, still
   rising) at d = 1.00; ~308-311k (2040/2050) and ~61k+ (2030) at d = 1.50.
   If ShARP explores near-zero intensity, use these ceilings as the tail
   slope rather than declaring infeasibility.
3. **Intensity, not renewable share, must be the coordinate.** At matched
   renewable shares the share-constrained system builds ZERO CCS-gas, runs
   3-15% cheaper, and carries 1.3-6.8x the emissions (the wedge subset,
   9 matched cells). A share-parameterised supply block materially
   understates the cost of actual emissions outcomes below ~0.25x pathway
   intensity.

## 3. Dataset B — the demand x carbon sweep (trajectories; previous work)

16 whole-horizon **pathways** (not comparative statics): carbon price
{0, 150, 300, 550} A$/t crossed with demand {0.870, 1.00, 1.10, 1.235} x Step
Change, each solved as a recursive-dynamic chain over 2030 -> 2040 -> 2050
(each year inherits the prior years' surviving build). 48 cell-years, PDLP
3e-3, zero USE, cost monotone in both axes. Dashboard + full tables: artifact
`6058d274-aab9-4dab-b706-8772928cef67`; repo `analysis/demand_carbon_sweep/`
(`results.csv`, `marginals.csv`, `storage.csv`).

This is the **range of internally-consistent capacity-expansion
trajectories**: average cost spans 45.5 A$/MWh ($0/t, x0.87, 2030) to 130.6
($550/t, x1.23, 2040/2050); realised intensity spans 0.454 (2030, $0, x1.23)
down to 0.014 t/MWh (2050, $550); renewable share 52.5-95.4%. Its
finite-difference demand marginals and the marginal MWh's technology
composition per price point are in `marginals.csv` (composition swings from
87% thermal at $0/t-2030 to ~16-20% at $550/t — a supply block needs its own
composition per price point).

**How the two datasets divide the labour for ShARP:**

- Use **B** to pick or interpolate a whole-horizon trajectory family
  (path-consistent fleets, vintaging effects included, myopic foresight).
- Use **A** to price deviations from the current-policy trajectory — its cells
  are single-year comparative statics with clean duals, exactly the
  deviation-pricing object; but they carry NO vintaging response (a sustained
  deviation would re-optimise later fleets, which A does not represent).
- The gap between them is measured, not assumed: s4.

## 4. The bridge between the datasets is validated

The map's lambda, log-linearly interpolated at the sweep's realised
intensities (d = 1.00):

| year | sweep price | map lambda at same iota | ratio |
|---|---|---|---|
| 2030 | 150 / 300 / 550 | 175 / 317 / 550 | 1.165 / 1.056 / **0.999** |
| 2040 | 150 / 300 / 550 | 172 / 327 / 550 | 1.149 / 1.089 / 1.000 |
| 2050 | 150 / 300 / 550 | 184 / 378 / 802 | 1.230 / 1.259 / 1.458 |

2030 is the strictly clean comparison (identical conditioning) and agrees to
0.1-17%. The growing 2040/2050 drift is the measured size of **conditioning
path-dependence**: sweep cells carry price-conditioned fleets, map cells carry
the $0-chain fleet. Two consequences for ShARP: (i) near the current-policy
path, A's duals can be used as if produced by a price instrument; (ii) if
ShARP selects a trajectory far from current policy, the deviation prices
should be regenerated conditioned on THAT trajectory — a ~10-45% effect at
2050 stringencies, not a rounding error. Full table: `duality_check.csv`.

## 5. Conventions and boundary bridges (whole-of-economy coupling)

- **Demand axis basis**: NEM operational sent-out demand (OPSO_MODELLING,
  Step Change, POE50), i.e. grid-served demand with rooftop PV already netted
  out. d = 1.00 absolute values in s2. Both datasets scale this trace
  uniformly (shape fixed — real electrification would reshape it; caveat).
- **ShARP-side quantity mapping**: the pathway anchors provided earlier
  (P_y/1.3 "source generation": 211.54 / 292.31 / 330.77 TWh) decompose as
  anchor = OPSO + distributed-PV generation + residual, with PV_TOT =
  48.7 / 78.9 / 121.4 TWh and the residual NEGATIVE at -27.0 / -26.7 / -42.5
  TWh (-9% to -13%). AEMO's PVLITE series confirms OPSO + PV_TOT exactly, so
  the residual sits in the beta = 1.3 national-to-NEM bridge or the anchors'
  PV accounting. **UNRESOLVED — the ShARP side must decide what its quantity
  coordinate means before mapping onto the demand axis.** The beta = 1.3
  bridge is applied only at handover, never inside the electricity model.
- **Intensity axis basis**: t CO2e per MWh **delivered** (divide by the
  delivered TWh in s2 to convert to absolute Mt). Scope-1 generation
  combustion, NGER total CO2e factors; CCS residual at (1 - capture rate)
  inside the accounting, captured CO2 outside it. Identical accounting to the
  sweep's reported emissions (verified digit-for-digit).
- **Renewable share** (reported, never a control): r_total = {wind, solar,
  hydro, biomass} share of real grid generation (rooftop excluded by
  topology; storage output excluded by construction); r_VRE = wind + solar
  only. Both per cell in `map_results.csv`.
- **Cost basis**: average A$/MWh delivered, full-fleet (carried vintages'
  capex re-attributed at original cost — the LP objective alone understates
  fleet capital); components (capital+FOM ex fuel, fuel, carbon payment)
  separable per cell. Real A$ on the 2026 ISP Final (IASR v7.8) cost basis.
  The sweep's $/t cells include the carbon cheque as a component; strip it
  (as its dashboard's "resource cost" does) when comparing against
  fraction- or intensity-targeted costs.
- **Conditioning offset, disclosed not rescaled**: the model's current-policy
  state sits below the earlier pathway anchors by 9-21% on quantity
  (mostly the boundary above) and 16-20 pp on renewable share (real: no
  policy instrument in the model's current-policy state). All map
  coordinates are relative to the MODEL's state (iota_planned in s2), not
  the anchors.

## 6. File manifest

| object | path |
|---|---|
| Map per-cell results (both duals, tech mix incl. gas-CCS split, shares) | `analysis/intensity_demand_map/map_results.csv` |
| Chordal marginals, both axes, with dual comparisons | `analysis/intensity_demand_map/marginals_intensity.csv`, `marginals_demand.csv` |
| Duality cross-validation | `analysis/intensity_demand_map/duality_check.csv` |
| Run provenance (solver settings, status, gap, wall time per cell) | `analysis/intensity_demand_map/manifest.csv` |
| Acceptance tests | `analysis/intensity_demand_map/acceptance_per_cell.csv`, `acceptance_per_grid.csv` |
| Map dashboard (self-contained) | `analysis/intensity_demand_map/dashboard.html` |
| Working record / analysis | `analysis/intensity_demand_map/RETURN_MEMO.md`, `MAP_ANALYSIS.md` |
| Sweep trajectories (48 cell-years) | `analysis/demand_carbon_sweep/results.csv`, `marginals.csv`, `storage.csv`, `manifest.csv` |
| Sweep dashboard | artifact `6058d274-aab9-4dab-b706-8772928cef67` (also `analysis/demand_carbon_sweep/cost_dashboard.html`) |
| Boundary reconciliation data | `analysis/intensity_demand_map/stage0_boundary.csv` |
| Solved networks (regenerable, not committed) | `analysis/benchmarks/runs_myopic/idm_*`, `sweep_*` |

## 7. Trust boundaries — carry these into ShARP

1. **Deep-tail sampling bias (measured)**: cells at iota <= 0.10x pathway
   intensity use 13-week sampling; one full-year validation pair puts the
   bias at **~-10% on lambda, -45% on gas-CCS build, +12% on solar** at that
   coordinate. Direction: sampled tail cells make deep decarbonisation look
   slightly cheaper and less firming-dependent than a full chronology.
   Single-coordinate measurement; not extrapolated as a correction.
2. **Comparative statics vs trajectories**: map cells have no anticipation or
   vintaging; sweep chains do but are myopic (no perfect foresight). Neither
   is a perfect-foresight plan.
3. **Conditioning is load-bearing** (~10-45% on 2050 duals; s4). ShARP
   selections far from current policy warrant a re-conditioned map — a new
   solve campaign, not a transformation of this one.
4. One map cell (`idm_d150_i025_2030`) carries a PDLP interior dual (flagged
   in the manifest); 28 cells carry unserved energy at most 0.00036% of
   delivered (solver tolerance artefacts, reported per-cell).
5. Uniform demand scaling holds the hourly shape fixed; electrification that
   reshapes load (peakier or flatter) is outside both datasets.
6. Weather is the single RefYear-2018 draw (AEMO synthetic tile) in all cells.

## 8. Open items for the receiving agent

1. Resolve the anchor-quantity residual (s5) with the ShARP owner before
   mapping quantity coordinates — it is 9-13% of the anchor and sits on their
   side of the boundary.
2. Decide the deep-tail acceptance (use as-is with the s7.1 bias disclosed,
   or commission full-year re-solves of the 27 tail cells at ~17 h each).
3. If ShARP's selected trajectory departs materially from current policy,
   commission a re-conditioned map on that trajectory (the machinery is
   committed and reusable: `scripts/run_cell.py` + a conditioning chain).
