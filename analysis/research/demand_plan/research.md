# Demand plan

## Purpose and scope

The campaign grid is five demand trajectories crossed with ten carbon pressure settings. The trajectories live in
[`analysis/hpc/demand_plan.json`](../../hpc/demand_plan.json), plan version `20260921-isp-range-v2`, as annual National Electricity Market (NEM)
energy in terawatt-hours (TWh) at the milestones 2030, 2040, 2050 and 2060. Two other numbers travel with them: a delivery fraction of 0.91 and a
2025 customer-delivered anchor of 193.911 TWh.

The plan quantity is **source NEM load**: the sum of AEMO's `OPSO_MODELLING` half-hourly demand traces over the 15 ISP sub-regions.
`OPSO_MODELLING` is operational demand with estimated interconnector losses removed and coordinated electric-vehicle charging added; it already
excludes rooftop and other embedded photovoltaic (PV) generation, and excludes hydrogen-production load. Rooftop PV is therefore not in the plan
quantity and must not be subtracted again downstream.

## How the trajectories are used

| Consumer      | Use                                                                                                                                            | File                                                          |
|---------------|------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|
| Trace scaling | Each trajectory's milestone TWh divided by the source-store financial-year energy gives a per-milestone scalar applied to every demand parquet | [`analysis/hpc/tracedirs.py`](../../hpc/tracedirs.py)         |
| Carbon caps   | `cap_t = delivery_fraction x intensity x source_twh x 1e6`, so the demand level sets the cap tonnage                                           | [`analysis/hpc/manifest.py`](../../hpc/manifest.py)           |
| Campaign grid | One chain per trajectory per pressure setting                                                                                                  | [`analysis/hpc/campaign_grid.py`](../../hpc/campaign_grid.py) |

## The numbers

Source NEM load, TWh per financial year, as written in `demand_plan.json`.

| Trajectory         |  2030 |  2040 |  2050 |  2060 | Derivation                                                                                      |
|--------------------|------:|------:|------:|------:|---------------------------------------------------------------------------------------------------|
| `iasr_low_bracket` | 155.3 | 196.3 | 239.2 | 286.5 | `iasr_low` x 0.92 at all four knots (A005)                                                      |
| `iasr_low`         | 168.8 | 213.4 | 260.0 | 311.4 | Draft ISP Slower Growth generation proxy (S002) x 0.97 at 2030-2050; the 2060 knot is authored (A003) |
| `iasr_central`     |   183 |   268 |   365 |   431 | Provenance not established (A006)                                                               |
| `iasr_high`        |   185 |   282 |   393 |   460 | Provenance not established (A006)                                                               |
| `iasr_stress`      | 214.4 | 363.8 | 476.3 | 568.4 | Draft ISP Accelerated Transition proxy (S002) x 0.97 at 2030-2050; 2027, 2029 and 2060 authored (A004) |

The 0.97 converts a generation-basis AEMO series to the plan's operational-load basis. It is an authored placeholder for the share of sent-out
generation absorbed by storage charging and auxiliary load (A010), not a figure AEMO publishes; operational demand is
measured as sent out, so network losses are already inside both series and are not what the factor removes. No rooftop correction sits on top of it: both sides of the comparison already exclude rooftop
photovoltaics, because `OPSO_MODELLING` is net of embedded generation and the generation proxy has `Solar (Rooftop)` subtracted before the
factor is applied.

`iasr_stress` also carries 199.8 TWh at 2027 and 209.5 TWh at 2029, which no milestone reads; they shape the interpolation only.

Reference series the trajectories are judged against.

| Series                                                         |    2030 |    2040 |    2050 | Boundary                                | Source |
|----------------------------------------------------------------|--------:|--------:|--------:|-----------------------------------------|--------|
| Parsed trace store, Step Change                                | 189.818 | 240.051 | 251.925 | Source NEM load (`OPSO_MODELLING`)      | S001   |
| Draft ISP Slower Growth, generation excluding rooftop          |   174.0 |   220.0 |   268.0 | NEM generation, a proxy for grid supply | S002   |
| Draft ISP Step Change, generation excluding rooftop            |   209.0 |   291.0 |   332.0 | NEM generation, a proxy for grid supply | S002   |
| Draft ISP Accelerated Transition, generation excluding rooftop |   221.0 |   375.0 |   491.0 | NEM generation, a proxy for grid supply | S002   |

The two AEMO series are different vintages and different quantities. The trace store is the 2026 final Inputs, Assumptions and Scenarios Report (IASR)
demand the campaign actually reads; the CDP4 files are 2026 draft ISP candidate-development-path generation, which includes transmission and storage
round-trip losses and so sits above delivered demand by a few per cent. For the same named scenario, Step Change, the gap between them widens from
+10.1% at 2030 to +31.8% at 2050.

**confidence: medium** for `low` and `stress` -- each is a named AEMO draft-ISP series at 2030, 2040 and 2050 scaled by one authored factor, so the
shape is AEMO's and only the level is authored; **confidence: low** for `central` and `high`, whose knots match no file in this repository or in the
ShARP review set.

## Boundary conversion

| Quantity                             |   Value | Meaning                                              | Basis                                                                                     |
|--------------------------------------|--------:|------------------------------------------------------|-------------------------------------------------------------------------------------------|
| Generation-to-operational factor     |    0.97 | AEMO generation proxy x 0.97 = plan source NEM load  | Authored placeholder for storage charging and auxiliary load between sent-out generation and operational demand |
| `delivery_fraction`                  |    0.91 | Source NEM load x 0.91 = customer-delivered energy   | 9% flat operational-load loss allowance, split 3% transmission and 6% distribution (A001) |
| National scaling                     |     1.3 | NEM source load x 1.3 = national grid-served load    | Stipulated handover factor in the ShARP review; not carried in `demand_plan.json` (A002)  |
| `anchor_2025_customer_delivered_twh` | 193.911 | 2025 customer-delivered reference                    | ShARP planned residual grid quantity (A008)                                               |

All three factors are authored rather than measured. 0.91 and 1.3 are recorded in the ShARP review as placeholders pending electricity-author
ratification; 0.97 is applied when the plan is built and carries no citation at all. The campaign's cap arithmetic multiplies by 0.91 but never by
1.3, so a cap quoted "per MWh delivered" is per MWh delivered on the NEM, not nationally.

The 0.97 and the 0.91 act on different gaps: 0.97 steps from sent-out generation to operational load, and 0.91 then steps from
operational load to customer-delivered energy. They do not overlap, but neither is an AEMO figure.

**confidence: low.** Every factor is a disclosed placeholder, and the 2025 anchor does not reconcile
with the trace store within 5% under either boundary reading: the store has no FY2025 at all, and back-extrapolating Step Change from FY2026 and
FY2027 gives about 176.75 TWh, against 213.09 TWh (anchor / 0.91) or 163.91 TWh (anchor / (0.91 x 1.3)).

## Checks that fail or cannot be made

| Check                                                                  | Result                                                                                                                   |
|------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `central` tracks the campaign's own Step Change trace                  | No. -3.6% at 2030, +11.6% at 2040, +44.9% at 2050. Step Change is near-flat past FY2045; every trajectory keeps climbing |
| `low` and `high` bracketed by other scenarios in the campaign's inputs | Cannot check. The parsed store holds one scenario, POE and demand type only (Step Change, POE50, `OPSO_MODELLING`)       |
| `low` and `high` bracketed by the draft ISP range                      | `high` yes at 2030, 2040 and 2050. `low` sits 3% below the Slower Growth floor by construction, because of the 0.97      |
| `stress` at least 20% above `high`                                     | **Fails at 2030: 214.4 / 185 = +15.9%.** Clears the rule at 2040 (+29.0%), 2050 (+21.2%) and 2060 (+23.6%)               |
| A real FY2060 demand level exists                                      | No. The trace store ends FY2056 and the 2060 shape is FY2050 relabelled (A009); the 2060 TWh level is authored           |

## Plot

[`plot_demand_trajectories.py`](plot_demand_trajectories.py) draws the five trajectories against the three draft-ISP scenario proxies and the
final-IASR Step Change trace, and writes `demand_trajectories.html` and `demand_trajectories.png` beside itself.
