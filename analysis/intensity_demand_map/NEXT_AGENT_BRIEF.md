# Brief — ShARP electricity pathways from the ISPyPSA result sets

## Objective

Explore and recommend how ShARP (the whole-of-economy optimisation) should
derive its electricity-supply pathways from the two internally-consistent
ISPyPSA result sets, so that ShARP's chosen pathway responds endogenously to
(a) the electricity demand the rest of the economy pulls, and (b) the
carbon-pricing pressure the scenario applies.

## Start here

Clone `https://github.com/nickvanschoten/ISPyPSA`, branch
`analysis/intensity-demand-map`, and read
`analysis/intensity_demand_map/SHARP_HANDOVER.md` first — it carries the data
contract, conventions, validated bridge between the two datasets, trust
boundaries, and file manifest. Treat every number there as a prior to verify
against the CSVs it points to.

## What exists

- **Dataset B (trajectories):** 16 whole-horizon myopic pathways over carbon
  price {0, 150, 300, 550} A$/t x demand {0.87, 1.00, 1.10, 1.235}, 2030/40/50,
  path-consistent fleets (`analysis/demand_carbon_sweep/`).
- **Dataset A (marginals):** a 78-cell response surface around the
  current-policy pathway — cost over (demand x intensity) with BOTH duals per
  cell: implied carbon price and marginal supply cost
  (`analysis/intensity_demand_map/`).
- **The bridge is measured:** Dataset A's duals reproduce Dataset B's applied
  prices where conditioning matches (ratio 0.999 at $550/t, 2030) and diverge
  10-45% where it does not — that divergence is the size of conditioning
  path-dependence, and it bounds how far either dataset can be stretched.

## The exploration asked for

Propose and compare at least two translation designs — for example: (i)
interpolate Dataset B's trajectory family directly in (price, demand) as
ShARP's supply block; (ii) embed Dataset A's cost surface piecewise-linearly
per year and let ShARP select intensity via the dual as first-order condition;
(iii) a hybrid — B selects the trajectory family, A prices local deviations.
Evaluate each against ShARP's actual solver structure and deliver a
recommendation with a concrete data-mapping specification (which CSV columns
feed which ShARP parameters, with unit conversions).

## Constraints that are not free to relax

- Intensity, not renewable share, is the deviation coordinate (the measured
  CCS wedge makes them non-interchangeable below ~0.25x pathway intensity).
- The beta = 1.3 national bridge applies only at handover; the -9..-13%
  anchor-quantity residual must be resolved with the ShARP owner before any
  quantity mapping.
- Do not smooth or extrapolate the deep tail without carrying the measured
  sampling bias (~-10% dual, -45% gas-CCS); do not treat the intensity floor
  as a hard bound (it is a year-driven price asymptote).
- ShARP selections far from current policy warrant a re-conditioned Dataset A
  (the solve machinery on the branch is reusable) rather than a transformation
  of this one.
