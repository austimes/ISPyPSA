# ShARP grid reference

## Purpose and scope

ShARP, the whole-of-economy model the campaign feeds, prices grid electricity with its own complete national futures and a
common "clean ladder" for supply beyond plan. This topic takes ShARP's current-policy future, which is built on AEMO's Step
Change, and commits it as a CSV so the campaign dashboard can draw it as a dashed reference beside the modelled results:

| Dashboard panel | ShARP reference drawn |
|---|---|
| Pathway intensities: conversion cost | Planned non-fuel cost on the common basis (A$2025/MWh of operational demand) |
| Pathway intensities: emissions | Planned emissions intensity (t CO2e/MWh) |
| Pathway intensities: input | Planned fuel input intensity, coal, lignite and gas summed (PJ/TWh) |
| Pathway intensities: cost, emissions and input | A band from the planned value to the clean ladder's 99% point |
| Pathway intensities: demand | Planned quantity as NEM operational demand (TWh), over a band spanning every ShARP grid future |
| Increment surfaces: demand arm | Approximate price of one extra MWh, flat across the arm |
| Increment surfaces: intensity arm | The clean ladder cleaner than the planned share, converted to intensity |

The reference is a comparison aid, not a target or a constraint. Nothing in the campaign model reads it.

Scope and boundaries:

- One ShARP method, `electricity__grid_supply__current_policy_clean_transition`, for the financial years 2030 to 2050 in
  five-year steps. The demand band alone spans every grid method in ShARP's planned pathway states (S001).
- ShARP's boundary is national net-delivered grid electricity excluding rooftop solar (S006). The campaign's boundary is
  NEM operational demand. The cost and demand panels restate ShARP on the campaign's basis, described under
  [Common basis](#common-basis-with-the-campaigns-measure); intensities are drawn unscaled (A004).
- Every ShARP cost is in 2024 Australian dollars (A$2024) and excludes fuel and carbon, which ShARP prices separately
  (S006).

## Derivation

Each year's planned state is read straight from ShARP (S001, S002). The clean ladder is ShARP's renewable fraction against
average cost (S003), extended to a nominal 99% endpoint along its last published segment's slope, as ShARP's README
describes (A002). The conversion to intensity then assumes the non-renewable remainder keeps the planned year's emissions
factor (A001):

```text
residual_factor        = planned_intensity / (1 - planned_renewable_fraction)
ladder_intensity       = (1 - ladder_renewable_fraction) x residual_factor
extra_mwh_price        = ladder cost interpolated at planned_renewable_fraction + overflow-scale premium
```

The overflow-scale premium is ShARP's per-MWh price on standing supply beyond plan (S004). ShARP's own beyond-plan price
also adds fuel and carbon allowances and an overflow-growth charge (S006); the proxy above leaves those out (A003).

### Placing ShARP on the increment arms

**Intensity arm.** The arm plots each cell's intensity as a multiple of its base cell against its change in average non-fuel
cost (A$/MWh). ShARP goes on the same axes as `ladder_intensity / planned_intensity` against `ladder_cost - ladder cost at
the planned share`, for the ladder points cleaner than the planned share, anchored at (1, 0) like the arm itself (A006).
Because the residual factor cancels, the x value is simply `(1 - ladder share) / (1 - planned share)`.

**Demand arm.** The arm plots the change in total annual cost, including fuel and carbon, over the change in delivered TWh.
That is already a cost per extra unit of energy, in A$ per TWh, so ShARP's extra-MWh price needs only the factor of 10^6
MWh per TWh to share its axis. No conversion through the base cell's average cost or TWh is needed (A005). The one mismatch
left is scope: the arm includes fuel and carbon, while the ShARP proxy excludes ShARP's fuel allowance of A$3 to A$6/MWh
over these years (S001).

## The numbers

From [`sharp_grid_reference.csv`](sharp_grid_reference.csv):

| Year | Planned TWh | Planned renewable share | Planned cost (A$/MWh) | Planned intensity (t/MWh) | Fuel input (PJ/TWh) | Residual factor (t/MWh) | Ladder cost at planned share (A$/MWh) | Scale premium (A$/MWh) | Extra-MWh price (A$/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2030 | 213.9 | 0.794 | 87.85 | 0.1876 | 2.173 | 0.911 | 95.89 | 7.89 | 103.79 |
| 2035 | 264.0 | 0.918 | 98.15 | 0.0698 | 0.832 | 0.853 | 90.77 | 7.89 | 98.66 |
| 2040 | 299.3 | 0.938 | 110.13 | 0.0433 | 0.550 | 0.696 | 89.38 | 11.72 | 101.10 |
| 2045 | 324.5 | 0.952 | 122.11 | 0.0312 | 0.406 | 0.657 | 88.74 | 12.64 | 101.39 |
| 2050 | 339.7 | 0.973 | 135.08 | 0.0116 | 0.195 | 0.429 | 88.36 | 11.01 | 99.37 |

The ladder points cleaner than each planned share, as the intensity arm draws them:

| Year | Ladder share | Ladder intensity (t/MWh) | Intensity multiple of planned | Cost above planned share (A$/MWh) |
|---|---:|---:|---:|---:|
| 2030 | 0.868 | 0.1198 | 0.64 | 2.21 |
| 2030 | 0.968 | 0.0288 | 0.15 | 8.74 |
| 2030 | 0.990 | 0.0091 | 0.05 | 10.15 |
| 2035 | 0.968 | 0.0270 | 0.39 | 3.25 |
| 2035 | 0.990 | 0.0085 | 0.12 | 4.65 |
| 2040 | 0.968 | 0.0220 | 0.51 | 1.89 |
| 2040 | 0.990 | 0.0070 | 0.16 | 3.23 |
| 2045 | 0.968 | 0.0208 | 0.67 | 0.98 |
| 2045 | 0.990 | 0.0066 | 0.21 | 2.30 |
| 2050 | 0.990 | 0.0043 | 0.37 | 1.05 |

Two features worth naming. ShARP's planned cost rises from A$88 to A$135/MWh over 2030 to 2050, while the ladder cost at
the planned share stays near A$90: the planned cost is ShARP's own authored trajectory and the ladder is CSIRO's
whole-system comparison, so the two need not agree. And the converted ladder is much cheaper than the campaign's own
intensity arm: in 2030, ShARP reaches 0.15 of the planned intensity for about A$9/MWh, where the campaign's i=0.25 cell
costs about A$19/MWh.

## Confidence

**Planned points, confidence: medium.** Quantity, share, cost, intensity and fuel input are read directly from ShARP's
pinned files, but ShARP labels its own planned costs as provisional authored assumptions, and its national boundary differs
from the NEM's.

**Converted ladder, confidence: low.** It rests on the constant-residual-factor assumption, which the campaign's own cells
contradict: renewable share and intensity are not one-to-one there, because the emissions factor of the thermal remainder
changes as the cap deepens. The ladder costs themselves are tagged exploratory in ShARP, and the 99% endpoint is an extension.

**Clean ladder reach band, confidence: low.** The cost, emissions and input panels each shade from the planned value to the
ladder's 99% point:
cost rises by the ladder cost at 99% less the ladder cost at the planned share, and emissions and fuel input both scale by
`(1 - 0.99) / (1 - planned share)`, so the band inherits the converted ladder's constant-residual-factor assumption.

**Extra-MWh price, confidence: low.** It is a proxy that leaves out ShARP's fuel and carbon allowances and overflow-growth
charge, and it inherits the ladder's exploratory status.

## Common basis with the campaign's measure

The campaign's cost and demand are per MWh and TWh of the load its model serves, which is NEM operational demand, in real 30
June 2025 dollars. ShARP's are per MWh and TWh of national delivered electricity in A$2024. ShARP's own translation from AEMO
generation sets the bridge: NEM source generation times a geographic factor of 1.3 and a delivery factor of 0.7915 gives
ShARP's planned delivered quantity (S007). The CSV's `common_` columns reverse that step and apply the demand plan's 0.97 from
generation to operational demand:

```text
common cost (A$/MWh)  = ShARP cost x 0.7915 / 0.97 x CPI June quarter 2025 / mean CPI of the four 2024 quarters
common quantity (TWh) = ShARP quantity / (1.3 x 0.7915) x 0.97
```

Per MWh, the geographic factor cancels: a national total cost over a national delivered quantity carries the same ratio as the
NEM share of each.

| Factor | Value | Basis |
|---|---:|---|
| Delivered to NEM generation, per MWh | 0.7915 | S007 |
| NEM generation to operational demand, per MWh | 1 / 0.97 = 1.031 | A008 |
| A$2024 to real June 2025 dollars | 141.7 / 138.675 = 1.0218 | A009 (S008) |
| Cost, all three together | 0.8338 | A007 |
| Quantity: national delivered to NEM operational demand | 0.97 / (1.3 x 0.7915) = 0.9427 | A007, A008 |

On that basis, from [`sharp_grid_reference.csv`](sharp_grid_reference.csv):

| Year | Planned cost (A$2025/MWh) | Reach cost at 99% (A$2025/MWh) | Planned demand (TWh) | Futures range (TWh) |
|---|---:|---:|---:|---|
| 2030 | 73.3 | 81.7 | 201.7 | 168.7 to 211.1 |
| 2035 | 81.8 | 85.7 | 248.9 | 192.4 to 296.1 |
| 2040 | 91.8 | 94.5 | 282.1 | 216.1 to 362.3 |
| 2045 | 101.8 | 103.7 | 305.9 | 239.9 to 419.0 |
| 2050 | 112.6 | 113.5 | 320.2 | 263.6 to 475.7 |

The futures range spans the six grid methods in S001: the two current-policy methods share one quantity path, the incumbent
and delayed-with-gas futures set the floor from 2030 on, and the early near-zero future sets the ceiling (A010). The
current-policy demand lands within 2% of the campaign's Step Change base chain in every milestone year, which supports the
two factors as a pair.

**Cost factor, confidence: medium.** The delivery factor is ShARP's own, but it maps national delivered energy to generation
as one flat ratio, and ShARP's cost may carry network costs that do not scale with it.

**Quantity factor, confidence: medium.** It inverts ShARP's own translation, which rounds planned output once to 5 TWh and
removes landfill electricity (S007), so the restated quantity carries up to about 2.5 TWh of that rounding.

**Price-index factor, confidence: high.** Both index values are ABS-published; the only choice is taking A$2024 as the 2024
mean, and the June quarter 2024 alone (138.8) would move the factor by 0.1%.

## Plot

[`plot_sharp_grid_reference.py`](plot_sharp_grid_reference.py) reads the five ShARP files at the pinned commit through the
`gh` command line, writes [`sharp_grid_reference.csv`](sharp_grid_reference.csv), and renders
[`sharp_grid_reference.png`](sharp_grid_reference.png) and its HTML twin: each year's converted ladder as cost against
intensity in A$2024 per delivered MWh, with the planned point marked. The CSV also carries the futures range and the
`common_` columns the dashboard's cost and demand panels draw. The dashboard reads the same committed CSV, so the figure and the
overlays cannot disagree.

Run it with:

```bash
uv run --with kaleido python analysis/research/sharp_grid_reference/plot_sharp_grid_reference.py
```
