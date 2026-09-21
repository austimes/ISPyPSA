# Carbon caps

## Purpose and scope

The campaign applies carbon pressure two ways: a price in Australian dollars per tonne, and an absolute annual cap in tonnes. The ladder of
settings, the cap arithmetic and the run naming all live in [`analysis/hpc/manifest.py`](../../hpc/manifest.py); the constraint itself is
added in [`analysis/hpc/instrumented_runner.py`](../../hpc/instrumented_runner.py); the rule for deciding when a capped result is a usable
answer rather than a boundary lives in [`analysis/sharp/deliverables.py`](../../sharp/deliverables.py).

## The pressure ladder

| Setting | Kind | Applies to | Count |
|---|---|---|---:|
| `c0` | Price, A$0/t | Every trajectory | 5 |
| `c150`, `c300`, `c550` | Price, A$150/300/550/t | `iasr_central` and `iasr_stress` only | 6 |
| `cap002` ... `cap00005` | Absolute tonnage schedule | Every trajectory | 30 |

That is 41 chains in total. The price chains exist to bracket the cap duals: a cap chain prices carbon at zero and exerts its pressure
through the constraint, so its price signal is the cap's shadow price read from the solve and negated.

Each cap schedule is named by its 2050 target intensity in tonnes of carbon dioxide equivalent per megawatt-hour delivered. Every schedule
holds 2030 at an anchor of 0.12, sets 2040 to the geometric mean of the anchor and the target, and holds the target through 2060 -- except
the deepest, whose 2060 rung tightens further and switches basis.

| Schedule | 2030 | 2040 (geometric mean) | 2050 | 2060 | 2060 basis |
|---|---:|---:|---:|---:|---|
| `cap002` | 0.12 | 0.048990 | 0.02 | 0.02 | delivered |
| `cap001` | 0.12 | 0.034641 | 0.01 | 0.01 | delivered |
| `cap0005` | 0.12 | 0.024495 | 0.005 | 0.005 | delivered |
| `cap0002` | 0.12 | 0.015492 | 0.002 | 0.002 | delivered |
| `cap0001` | 0.12 | 0.010954 | 0.001 | 0.001 | delivered |
| `cap00005` | 0.12 | 0.007746 | 0.0005 | 0.0001 | source |

The geometric mean gives a constant proportional tightening per decade rather than a constant absolute step, so every schedule falls at its
own steady rate rather than deferring most of the work to one decade.

**confidence: high** on the arithmetic, all of which is read from `_cap_rungs` and `CAP_LADDER`; **confidence: low** on the 0.12 anchor and
on the six target values, for which no basis is recorded anywhere in this fork -- they are a spread chosen to span from an achievable
near-term intensity to something close to zero, not calibrated to a published target.

## From intensity to tonnes

`cap_t = delivery_fraction x intensity x source_twh x 1e6`, where `source_twh` is that trajectory's source NEM load for that year and the
delivery fraction is 0.91. A rung already quoted on the source basis skips the delivery factor. Every manifest row records its basis, so no
cap is ever quoted without one.

Worked example on `iasr_central`, whose source load is 183, 268, 365 and 431 TWh.

| Year | Rung | Basis | Arithmetic | Cap (t CO2e/y) |
|---|---:|---|---|---:|
| 2030 | 0.12 | delivered | 0.91 x 0.12 x 183e6 | 19,983,600 |
| 2040 | 0.007746 | delivered | 0.91 x 0.007746 x 268e6 | 1,889,086 |
| 2050 | 0.0005 | delivered | 0.91 x 0.0005 x 365e6 | 166,075 |
| 2060 | 0.0001 | source | 1.00 x 0.0001 x 431e6 | 43,100 |

Two consequences follow from the delivered basis. First, a cap said to be "0.0005 t/MWh delivered" is enforced as a tonnage derived from
source load, so the two only agree if the 0.91 delivery fraction is right; that fraction is an unratified placeholder, documented in
[`../demand_plan/`](../demand_plan/). Second, because the tonnage scales with demand, the same named rung is a materially different physical
budget on each trajectory: at 2050 the `cap00005` budget is 216,716 t on `iasr_stress` against 108,836 t on `iasr_low_bracket`.

**confidence: high** on the arithmetic; **confidence: low** on the delivered basis itself, which inherits the demand plan's unratified 0.91.

## What the constraint covers

The constraint sums `isp_residual_co2_t_per_mwh` over every generator with a positive residual, weighted by snapshot weights.

| In the cap | Out of the cap |
|---|---|
| Combustion emissions of coal, gas, liquid fuel and biomass | Carbon dioxide captured by a carbon capture and storage plant, at its configured capture rate |
| Residual emissions of a capturing plant after capture | Upstream and fuel-cycle emissions of any fuel |
| Biomass methane and nitrous oxide residuals, at 1.8 kg CO2e/GJ | Biogenic carbon dioxide from biomass, which is zero by the accounts convention |

The biomass line matters more than its size suggests: see [`../biomass/`](../biomass/), where at the deepest rung the biomass residual
accounts for essentially the whole annual budget.

**confidence: high.** The included set is exactly the generators with a positive residual coefficient, which is stated in the constraint's
own comment and follows from how the coefficient is built.

## Unserved energy and the acceptance rule

Deep caps can leave demand unserved. The generated ISPyPSA config prices load shedding at A$10,000/MWh with a limit of 100,000 MWh per node.

| Rule | Value | Effect |
|---|---|---|
| Unserved energy cost | 10,000 A$/MWh | An emergency price, far above any generator's marginal cost, so the solver sheds only when nothing else will serve the load |
| Boundary threshold | 0.1% of demand | A cell shedding more than this is reported as a boundary, never treated as a menu member, and dropped before marginals are differenced |
| Cost treatment | Excluded everywhere | Unserved-energy generators carry no capital cost and are excluded from dispatch, marginal cost and capital columns, so the penalty never enters a reported cost |

The threshold is chosen to sit far above the rounding noise of a converged solve and far below any shedding that would change the reported
mix. The 2060 stress chain under the deepest cap shed 157,934,633 MWh, or 26.83% of its demand -- roughly 270 times the threshold -- so that
cell marks where the pressure setting stops being feasible on this fleet rather than contributing an answer.

**confidence: high** on the rule and its consequences, all read from `deliverables.py`; **confidence: medium** on the 10,000 A$/MWh price,
which is a conventional emergency value but carries no citation in this fork.

## Plot

[`plot_carbon_caps.py`](plot_carbon_caps.py) draws the ladder as the absolute annual tonnages the solver is given, one line per rung and one
panel per trajectory on a shared log axis, with the source-basis rung ringed. It builds the tonnages with this module's own
`build_caps_table`, so the plot and the manifest cannot drift apart. It writes `carbon_caps.html` and `carbon_caps.png` beside itself.
