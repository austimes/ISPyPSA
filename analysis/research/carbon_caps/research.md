# Carbon caps

## Superseded: the 0.12 anchor and the pressure ladder

This topic was written for a ladder of 41 chains spanning six 2050 target intensities, every one of them held at an
authored 0.12 t CO2e/MWh in 2030. That anchor is retired. The campaign's base chain now takes the Step Change scenario's
own emissions intensity at each milestone, 0.19673 t CO2e/MWh in 2030 falling to 0.01385 by 2050, derived in
[`../aemo_scenario_intensity/`](../aemo_scenario_intensity/) and applied as described in
[`../near_term_pipeline/`](../near_term_pipeline/). Carbon pressure is now varied by the increment grid rather than by a
ladder of cap chains.

Everything below describes how a cap becomes a tonnage, what the constraint covers and when a capped result counts as an
answer, all of which is unchanged.

## Purpose and scope

The campaign applies carbon pressure two ways: a price in Australian dollars per tonne, and an absolute annual cap in tonnes. The ladder of
settings, the cap arithmetic and the run naming all live in [`analysis/hpc/manifest.py`](../../hpc/manifest.py); the constraint itself is
added in [`analysis/hpc/instrumented_runner.py`](../../hpc/instrumented_runner.py); the rule for deciding when a capped result is a usable
answer rather than a boundary lives in [`analysis/sharp/deliverables.py`](../../sharp/deliverables.py).

## The pressure ladder

The earlier design ran 41 chains: five zero-price chains, six carbon-price chains and 30 chains on a ladder of six cap
schedules, each named by a 2050 target intensity and every one anchored at 0.12 t CO2e/MWh in 2030. None of it survives.
The campaign now runs one base chain on the Step Change intensity path and varies carbon pressure through the increment
grid's intensity levels, so no ladder, no price chain and no authored anchor remains in the plan or the manifest.

## From intensity to tonnes

`cap_t = delivery_fraction x intensity x source_twh x 1e6`, where `source_twh` is that chain's source NEM load for that
year. The delivery fraction is 1.0 for an intensity quoted on the source basis, which is what the scenario intensities
are, and the plan's 0.91 for one quoted on the customer-delivered basis. Every manifest row records its basis, so no cap
is ever quoted without one.

Worked example on the base chain `ext_step_change_sc`, whose source load is 202.73, 282.27 and 322.04 TWh at these years.

| Year | Intensity | Basis | Arithmetic | Cap (t CO2e/y) |
|---|---:|---|---|---:|
| 2030 | 0.19673 | source | 1.00 x 0.19673 x 202.73e6 | 39,883,073 |
| 2040 | 0.04136 | source | 1.00 x 0.04136 x 282.27e6 | 11,674,687 |
| 2050 | 0.01385 | source | 1.00 x 0.01385 x 322.04e6 | 4,460,254 |

The base chain's eight milestones, with the 2026 and post-2050 intensities (A009):

| Year | Intensity (t CO2e/MWh) | Source basis | Source load (TWh) | Cap (t CO2e/y) |
|---|---:|---|---:|---:|
| 2026 | 0.55646 | Draft ISP Step Change FY2026: 106.284 Mt over 191 TWh generated | 190.1 | 105,783,046 |
| 2030 | 0.19673 | Draft ISP Step Change FY2030 | 202.73 | 39,883,073 |
| 2035 | 0.06450 | Draft ISP Step Change FY2035 | 246.38 | 15,891,510 |
| 2040 | 0.04136 | Draft ISP Step Change FY2040 | 282.27 | 11,674,687 |
| 2045 | 0.02714 | Draft ISP Step Change FY2045 | 307.49 | 8,345,279 |
| 2050 | 0.01385 | Draft ISP Step Change FY2050 | 322.04 | 4,460,254 |
| 2055 | 0.01385 | Held at 2050 | 341.9 | 4,735,315 |
| 2060 | 0.01385 | Held at 2050 | 361.8 | 5,010,930 |

The 2026 cap is 0.5% below AEMO's own FY2026 emissions, because the source load (190.1 TWh) sits just under AEMO's
generation. It should not bind hard: 2026 is a calibration year. After 2050 AEMO publishes nothing, so the intensity is
held at 2050, as the earlier plan held its 2060 rung. The absolute cap therefore rises with demand after 2050. ShARP's own
post-2050 futures instead keep tightening, halving the gap to 99% renewables each decade, so holding is the looser of the
two readings.

**confidence: high** on 2026, read from the committed intensity series. **confidence: low** on 2055 and 2060, an
authored hold with no source.

Because the tonnage scales with demand, an increment cell's cap is its intensity level on the base intensity at its
demand level on the base load: the 2030 cell at demand level 1.10 and intensity level 1.0 is capped at 43,871,380 t
against the base cell's 39,883,073 t.

**confidence: high** on the arithmetic; the delivered basis and its unratified 0.91 are no longer on the path any
campaign cap takes, and are documented in [`../demand_plan/`](../demand_plan/).

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

[`plot_carbon_caps.py`](plot_carbon_caps.py) draws the base chain's cap intensity per milestone and the absolute annual tonnage it becomes,
with the increment grid's cells as faint points around it. It builds the caps with the manifest's own `build_caps_table` against the shipped
demand plan, so the plot and the manifest cannot drift apart. It writes `carbon_caps.html` and `carbon_caps.png` beside itself.
