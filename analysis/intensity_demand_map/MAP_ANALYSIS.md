# Post-modelling analysis: what the intensity x demand map says

Companion to `RETURN_MEMO.md` (the working record). This document reads the
assembled map (`map_results.csv`, `marginals_*.csv`, `duality_check.csv`) as
economics. Presentation dashboard: `dashboard.html` (self-contained; rebuilt by
`scripts/build_analysis.py` + `scripts/build_dashboard.py`).

## 1. The dual field is externally validated by an independent instrument

The previous sweep applied carbon **prices** {150, 300, 550} and realised
intensities; this map fixed **intensities** and read dual prices. If the model
is internally coherent these are inverse views of the same marginal-abatement-
cost curve: the map's dual, interpolated at the sweep's realised intensity,
should equal the sweep's price. Interpolation is log-linear in the dual (the
curve is exponential-convex); full table in `duality_check.csv`.

| year | sweep price | sweep realised ι | map dual at ι | ratio |
|---|---|---|---|---|
| **2030** (conditioning matched) | 150 | 0.0812 | 174.8 | 1.165 |
| **2030** | 300 | 0.0403 | 316.8 | 1.056 |
| **2030** | 550 | 0.0224 | 549.6 | **0.999** |
| 2040 (conditioning differs) | 150 | 0.0691 | 172.4 | 1.149 |
| 2040 | 300 | 0.0402 | 326.7 | 1.089 |
| 2040 | 550 | 0.0175 | 550.0 | **1.000** |
| 2050 (conditioning differs) | 150 | 0.0464 | 184.4 | 1.230 |
| 2050 | 300 | 0.0306 | 377.7 | 1.259 |
| 2050 | 550 | 0.0136 | 802.1 | 1.458 |

2030 is the only strictly clean comparison (both experiments condition on the
same greenfield-on-ECAA state), and there the map reproduces the price
instrument to **0.1% at $550/t**, 5.6% at $300/t, 17% at $150/t. The 2040/2050
drift grows with stringency and year exactly as path-dependence predicts: the
sweep's 2040 cell at $300 carries a fleet built under $300 since 2030, where
the map's 2040 cell carries the $0-chain fleet. **The map's duals are not just
internally consistent (the chordal check) — they reproduce an independent
experiment run with a different instrument.** For the colleague, the practical
reading: near the current-policy pathway, the map's implied-carbon-price axis
can be trusted as if it had been produced by a price sweep, at a fraction of
the cells.

## 2. The map surface: demand is cheap, intensity is expensive

Average cost (A$/MWh, d = 1.00 column of the full surface):

| ι / ι_planned | 2030 | 2040 | 2050 |
|---|---|---|---|
| 1.00 | 48.6 | 76.7 | 86.2 |
| 0.50 | 57.4 | 82.8 | 91.4 |
| 0.25 | 67.3 | 90.3 | 99.0 |
| 0.10 | 77.5 | 100.6 | 108.0 |
| 0.05 | 86.1 | 106.0 | 115.1 |

Two structural readings:

- **Along the demand axis the surface is nearly linear and shallow**: the
  demand-balance dual sits within 25% of the chordal in 59/60 adjacent pairs,
  and marginal supply cost rises only modestly with demand at fixed intensity
  (the model meets +50% demand mostly with more of the same renewables).
- **Along the intensity axis the surface is convex and steep**: halving
  intensity from the pathway point costs ~9-18% on average cost, but the
  MARGINAL price rises super-linearly (0 -> 112 -> 291 -> 532 -> 845 A$/t down
  the 2040 ladder). A pathway-deviation representation that prices intensity
  deviations linearly will be wrong by construction; the map's per-rung duals
  are the piecewise slopes to use.

## 3. The thermal-overflow direction is empty

Every 1.5x ι_planned cell is slack (dual exactly 0), at every demand level and
year — including +50% demand. Realised intensity at the uncapped/loose cells
DROPS slightly with demand (2040: 0.1791 at d = 1.00 vs 0.174 at d = 1.50):
marginal demand is met marginally CLEANER than the conditioned average, by
renewables plus storage, not by gas. **The colleague's overflow-by-gas
direction does not materialise in this optimiser at current-policy economics**;
if his representation needs a thermal-overflow branch, its activation lies
outside the sampled demand range (or outside cost-optimal dispatch altogether).

## 4. The saturation boundary is a price ceiling, not a wall

No probed coordinate went infeasible, down to caps of 10-500 t (five orders of
magnitude below pathway emissions). The dual asymptotes to a finite ceiling
that is **year-driven, not demand-driven**: ~186-190k A$/t (2040/2050, d=1.00),
~308-311k (2040/2050, d=1.50), and an order of magnitude lower for 2030 (~72k
at 10 t, still rising). Practical translation for the pathway model: there is
no hard quantity floor on intensity to encode — encode instead an
asymptotically-priced tail, and note that the ceiling roughly doubles from
d = 1.00 to d = 1.50.

## 5. The CCS wedge is the difference between the axes

At matched renewable shares (s7 of the memo), the share-constrained solve
builds **zero** CCS-gas everywhere it binds, is 3-15% cheaper, and carries
1.3x-6.8x the residual intensity. The two axes stop being interchangeable
precisely where the map is most interesting (below ~0.25x ι_planned). Since
the colleague settled the axis as intensity, this is confirmation the choice
is load-bearing, with the forgone-abatement magnitude quantified per cell.

## 6. Trust boundaries (carry with any use of the map)

- Deep-tail cells (ι <= 0.10x ι_planned) are sampled-week solves; the one
  full-year validation pair puts the sampled-week bias at **~-10% on the dual,
  -45% on gas-CCS build, +12% on solar** at that coordinate (memo s12) —
  direction: sampled cells make deep decarbonisation look slightly cheaper and
  less firming-dependent than a full chronology does.
- The map is anchored at the model's current-policy state, which sits 16-20 pp
  below the colleague's planned renewable shares (memo s2.1); the 2050 duals'
  divergence from the sweep (s1) shows conditioning matters at exactly the
  10-20% level, so re-conditioning on his other four pathways is not a
  refinement — it is a different map.
- One cell (`idm_d150_i025_2030`) carries a PDLP interior dual; 28 cells carry
  numerically negligible unserved energy (max 0.00036%).
