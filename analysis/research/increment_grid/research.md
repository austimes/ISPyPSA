# Increment grid

## Purpose and scope

The increment grid is a set of single-year conditioned re-solves layered on top of the Step Change base chain, used to
measure what one step in demand or one step in carbon pressure costs at a given milestone year. Two axes are documented
here: the demand level (a multiple of the base chain's load for that year) and the intensity level (a multiple of the
base chain's own cap intensity for that year). Their arithmetic, naming and grid-building code live in
[`analysis/hpc/increments.py`](../../hpc/increments.py) and [`analysis/hpc/manifest.py`](../../hpc/manifest.py); the
plan's own numbers live in [`analysis/hpc/demand_plan.json`](../../hpc/demand_plan.json)'s `increment_grid` block.

## Grid size

| Axis | Levels | Values |
|---|---:|---|
| Demand | 8 | 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0 |
| Intensity | 8 | 2.0, 1.0, 0.41, 0.17, 0.07, 0.03, 0.012, 0.005 |
| Increment years | 7 | 2030, 2035, 2040, 2045, 2050, 2055, 2060 |

With `"cells": "all"` every demand level is crossed with every intensity level at every increment year: 8 x 8 x 7 =
**448 branch rows** (S001, S002).

**confidence: high.** Arithmetic on the plan's own lists.

## Level keys

Demand keys are the factor times 100 in three digits (`d060` = 0.60, `d200` = 2.00); intensity keys are the factor
times 1000 in four digits (`i0005` = 0.005, `i2000` = 2.000). Both read as a units digit followed by decimals, the
convention the dashboard's level-key parser already applies to its three-digit keys (S005):

> "A level key names a percentage of the base cell's own, prefixed by the axis it varies: `d135` is 1.35 times its
> demand and `i010` a tenth of its cap."

The intensity axis needs one more digit than that three-digit pattern, because its two deepest levels, `i0012` and
`i0005`, need a fourth significant digit to stay distinct from each other. The demand axis keeps the three-digit
width because none of its eight levels needs a fourth digit.

**confidence: medium.** The decode rule is read from the dashboard's own comment; whether its regular expression is
widened to parse a four-digit intensity key is a code change outside this topic.

## Demand levels

| Key | Factor |
|---|---:|
| d060 | 0.6 |
| d080 | 0.8 |
| d100 | 1.0 |
| d120 | 1.2 |
| d140 | 1.4 |
| d160 | 1.6 |
| d180 | 1.8 |
| d200 | 2.0 |

Source National Electricity Market (NEM) load each level scales, terawatt-hours (TWh) per financial year, from the
base chain's own knots (S001):

| Year | d060 | d080 | d100 | d120 | d140 | d160 | d180 | d200 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2030 | 121.64 | 162.18 | 202.73 | 243.28 | 283.82 | 324.37 | 364.91 | 405.46 |
| 2035 | 147.83 | 197.10 | 246.38 | 295.66 | 344.93 | 394.21 | 443.48 | 492.76 |
| 2040 | 169.36 | 225.82 | 282.27 | 338.72 | 395.18 | 451.63 | 508.09 | 564.54 |
| 2045 | 184.49 | 245.99 | 307.49 | 368.99 | 430.49 | 491.98 | 553.48 | 614.98 |
| 2050 | 193.22 | 257.63 | 322.04 | 386.45 | 450.86 | 515.26 | 579.67 | 644.08 |
| 2055 | 205.14 | 273.52 | 341.90 | 410.28 | 478.66 | 547.04 | 615.42 | 683.80 |
| 2060 | 217.08 | 289.44 | 361.80 | 434.16 | 506.52 | 578.88 | 651.24 | 723.60 |

**confidence: high** on the arithmetic, factor times the base chain's own knot (S001); **confidence: low** on the
spread itself, see [Rationale for the ranges](#rationale-for-the-ranges).

## Intensity levels

| Key | Factor |
|---|---:|
| i2000 | 2.0 |
| i1000 | 1.0 |
| i0410 | 0.41 |
| i0170 | 0.17 |
| i0070 | 0.07 |
| i0030 | 0.03 |
| i0012 | 0.012 |
| i0005 | 0.005 |

The ladder spans a factor of 2.0 / 0.005 = 400 over seven steps. An exactly log-spaced ladder would hold a constant
step ratio of 400^(1/7) = 2.354; the levels actually used step down by 2.00, 2.44, 2.41, 2.43, 2.33, 2.50 and 2.40 in
turn, close to that constant ratio but rounded to clean two- or three-significant-digit values rather than held
exact.

**confidence: high** on the arithmetic; **confidence: low** on the spread itself, see
[Rationale for the ranges](#rationale-for-the-ranges).

Absolute cap intensity each level implies, tonnes of carbon dioxide equivalent (t CO2e) per megawatt hour (MWh)
generated, level times the base chain's own intensity for that year (S001, `cap_intensity_t_per_mwh`):

| Year | i2000 | i1000 | i0410 | i0170 | i0070 | i0030 | i0012 | i0005 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2030 | 0.39346 | 0.19673 | 0.080659 | 0.033444 | 0.013771 | 0.005902 | 0.002361 | 0.000984 |
| 2035 | 0.12900 | 0.06450 | 0.026445 | 0.010965 | 0.004515 | 0.001935 | 0.000774 | 0.000323 |
| 2040 | 0.08272 | 0.04136 | 0.016958 | 0.007031 | 0.002895 | 0.001241 | 0.000496 | 0.000207 |
| 2045 | 0.05428 | 0.02714 | 0.011127 | 0.004614 | 0.001900 | 0.000814 | 0.000326 | 0.000136 |
| 2050 | 0.02770 | 0.01385 | 0.005679 | 0.002355 | 0.000970 | 0.000416 | 0.000166 | 0.0000693 |
| 2055 | 0.02770 | 0.01385 | 0.005679 | 0.002355 | 0.000970 | 0.000416 | 0.000166 | 0.0000693 |
| 2060 | 0.02770 | 0.01385 | 0.005679 | 0.002355 | 0.000970 | 0.000416 | 0.000166 | 0.0000693 |

The 2060 corner at `d200_i0005` is the naming worked example: 0.005 x 0.01385 = 0.00006925 t CO2e/MWh, giving the
branch chain id `ext_step_change_b2060_d200_cap00006925` (S002, S003, S004). 2050 to 2060 repeat the same row because
the base chain holds its cap intensity at the 2050 value, described in [`../carbon_caps/`](../carbon_caps/).

**confidence: high.** Arithmetic on two committed series in S001.

## Reference cell

`d100_i1000`, demand factor 1.0 and intensity factor 1.0, holds both axes at the base chain's own value, so its
source load and cap intensity exactly reproduce the base chain's row at that year. It is still solved as its own
branch row, single-year, seeded from the base chain's state at the prior milestone with the base stock pinned (S002),
rather than read off the base chain directly, so the grid method itself can be checked: a correctly built grid should
reproduce the base chain's own reported cell at `d100_i1000` to numerical tolerance. It is the cell every other
increment in the grid is differenced against, not the base chain's own multi-year result, because only the branch
stage isolates one year's cross-sectional response from the recursive-dynamic build-up of the years before it.

The reference cell's annual cap tonnage matches the base chain's own committed figures exactly (S001, cross-checked
against [`../carbon_caps/`](../carbon_caps/)):

| Year | Cap (t CO2e/y) |
|---:|---:|
| 2030 | 39,883,073 |
| 2035 | 15,891,510 |
| 2040 | 11,674,687 |
| 2045 | 8,345,279 |
| 2050 | 4,460,254 |
| 2055 | 4,735,315 |
| 2060 | 5,010,930 |

**confidence: high.** Arithmetic on S001, reproducing figures already committed in `../carbon_caps/research.md`.

## Cap tonnage range

Annual cap tonnage scales with both axes, `cap_t = intensity_level x base_intensity x demand_level x base_source_twh x 1e6`, with no delivery factor because the base intensity is quoted on the source basis (S001). The
narrowest and widest corners each year:

| Year | Min (`d060_i0005`, t CO2e/y) | Reference (`d100_i1000`, t CO2e/y) | Max (`d200_i2000`, t CO2e/y) |
|---:|---:|---:|---:|
| 2030 | 119,649 | 39,883,073 | 159,532,292 |
| 2035 | 47,675 | 15,891,510 | 63,566,040 |
| 2040 | 35,024 | 11,674,687 | 46,698,749 |
| 2045 | 25,036 | 8,345,279 | 33,381,114 |
| 2050 | 13,381 | 4,460,254 | 17,841,016 |
| 2055 | 14,206 | 4,735,315 | 18,941,260 |
| 2060 | 15,033 | 5,010,930 | 20,043,720 |

The widest corner allows about 1,300 times more annual carbon than the narrowest corner in the same year (2050:
17,841,016 / 13,381 = 1,333 times).

**confidence: high.** Arithmetic on S001.

## Expected corner behaviour

These are expectations set before any grid cell is solved, not results read from a solve.

| Corner | Expectation | Why |
|---|---|---|
| High demand (`d160` to `d200`) at any intensity level, 2030 | May exceed the 2030 pipeline ceiling and be infeasible or shed load | The 2030 period caps near-term new-entrant build at `pipeline_rush_ceiling_mw`, 41,000 MW for generation and 10,200 MW for storage, above a free allowance of 20,500 MW and 5,100 MW (`new_entrant_cap_mw_by_year`, S001); a cell asking for enough new capacity to serve 1.6 to 2 times demand can exceed that ceiling. [`../near_term_pipeline/`](../near_term_pipeline/) and [`../pre2030_rush_charge/`](../pre2030_rush_charge/) derive how the allowance and rush ceiling are built, though their own worked examples carry different generation and storage totals than the plan's current figures (A006) |
| High demand (`d160` to `d200`) at any year | May run into renewable energy zone (REZ) or transmission ceilings even after the campaign's REZ and corridor relaxation | About a third of the binding REZ and corridor ceilings in the deepest-cap reference run still bind after doubling every limit; the campaign's own launches relax further still, but the direction, that some ceilings do not clear at any plausible relaxation, still sets the expectation for the highest demand levels (A008, S009) |
| Deepest intensity (`i0012`, `i0005`) at 2050 to 2060 | May be infeasible, or meet the cap only through unserved energy | At those years the base cap intensity holds at 0.01385 t/MWh; `i0005` implies 0.0000693 t/MWh, a level the fork's own carbon-cap probe already found a biomass fleet's residual methane and nitrous oxide emissions alone can approach or exceed at a comparably deep cap (A007, S010). Unserved energy is priced at A$10,000/MWh (S011), so an infeasible cap shows up as load shedding rather than a solver failure |
| `d100_i1000` | Reproduces the base chain's own year | Both axes hold the base chain's own demand and cap intensity; see [Reference cell](#reference-cell) |

**confidence: medium** on the corner expectations themselves, which project findings from the cited topics onto
levels those topics did not test directly; **confidence: high** on the cited figures at their own source.

## Rationale for the ranges

**Demand, 0.6 to 2.0.** ShARP's own current-policy futures band for national grid electricity, restated to the
campaign's basis, spans roughly 0.77 to 1.65 times its planned quantity across the campaign's milestones (S006,
widest below plan at 2040 and widest above plan at 2060). The grid's 0.6 to 2.0 span sits outside that band on both
ends, so it is an authored choice to sample beyond ShARP's own disclosed futures rather than a range ShARP's data
directly supports (A001).

**Intensity, 2.0 to 0.005.** The span runs from twice the Step Change path's own pressure down to close to zero, so
the grid samples both a looser-than-planned world and a near-complete decarbonisation. Log spacing keeps the
marginal abatement cost curve sampled evenly across orders of magnitude, rather than crowding samples at the shallow
end the way a linear ladder would (A002).

**confidence: low** on both spreads: they are authored campaign method, chosen to bracket a wide range of futures
rather than measured against one source.

## Plot

[`plot_increment_grid.py`](plot_increment_grid.py) reads `analysis/hpc/demand_plan.json`'s `increment_grid` block and
draws two panels: the absolute cap intensity by year for each intensity level, log scaled, with the Step Change base
path (`i1000`) highlighted, and the source NEM load by year for each demand level, with the base path (`d100`)
highlighted. It writes `increment_grid.html` and `increment_grid.png` beside itself. Run it with:

```bash
uv run --with kaleido python analysis/research/increment_grid/plot_increment_grid.py
```
