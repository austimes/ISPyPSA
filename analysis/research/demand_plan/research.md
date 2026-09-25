# Demand plan

## Current plan: one Step Change base, 2026 to 2060

The campaign runs one base trajectory, `iasr_step_change`, at eight milestones, and varies demand through the
increment grid's demand levels. The sections after this one describe the earlier five-trajectory plan and stay as its
derivation record; the boundary factors they discuss (0.91, 1.3, 0.97) still apply.

Source NEM load, TWh per financial year:

| Milestone | Knot | Derivation | Cites | confidence |
| --------: | ---: | ---------- | ------ | ---------- |
| 2026 | 190.1 | Draft CDP4 Step Change FY2026 generation excluding rooftop, 191 TWh, x 0.995 | A011 | medium |
| 2030 | 202.73 | Draft CDP4, 209 TWh, x 0.97 | A010 | medium |
| 2035 | 246.38 | Draft CDP4, 254 TWh, x 0.97 | A010 | medium |
| 2040 | 282.27 | Draft CDP4, 291 TWh, x 0.97 | A010 | medium |
| 2045 | 307.49 | Draft CDP4, 317 TWh, x 0.97 | A010 | medium |
| 2050 | 322.04 | Draft CDP4, 332 TWh, x 0.97 | A010 | medium |
| 2055 | 341.9 | 2050 knot plus half the 2040-2050 rise of 39.77 TWh | A012 | low |
| 2060 | 361.8 | 2050 knot plus the whole 2040-2050 rise | A012 | low |

**2026.** FY2026 is the only milestone before AEMO's final 2026 ISP series starts (FY2027), so it uses the draft CDP4
generation, 111 coal, 8 gas, 15 hydro, 37 wind and 20 utility solar, 191 TWh in all. The factor is the FY2027
generation-net-of-storage-losses ratio of 0.995 (see
[Generation to operational demand, measured](#generation-to-operational-demand-measured)), because storage charging is
still small in FY2026. With the 0.97 used at 2030 to 2050 the knot would be 185.3 TWh, 2.5% lower. The plan's check that
the 2026 base reproduces AEMO's 2026 generation needs the higher knot: the model's own generation is its load plus storage
losses, so a 185.3 TWh load cannot generate 191 TWh.

**2055 and 2060.** No AEMO series reaches past FY2050. The earlier plan's 2060 knots were authored at 17% to 20% above
2050 with no recorded rule. The rule here is ShARP's own (S010): post-2050 quantities continue each future's 2040-2050
absolute trend. On the campaign's knots that is +39.77 TWh per decade, giving 341.9 and 361.8 TWh. As a cross-check,
ShARP's current-policy future adds 20 TWh of national delivered electricity per five years after 2050 (359.7 and 379.7
TWh against 339.7 in 2050), which on the campaign's basis (x 0.97 / (1.3 x 0.7915) = 0.9427) is +18.85 TWh per five
years: 340.9 and 359.7 TWh, within 0.6% of the knots. Holding the earlier plan's +19.5% per decade instead would give 352.0
and 384.8 TWh, a faster rise than AEMO's own 2040-2050 path (+14.1%).

The trace shape behind every post-2050 knot is still an earlier year's: 2055 is native FY2055 in the trace store and 2060
relabels FY2055 ([`../campaign_method/`](../campaign_method/)). Step Change's own trace is flat from FY2050 (251.9 TWh) to
FY2056 (251.2 TWh), so both post-2050 knots are authored levels laid over a flat AEMO shape.

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
| Generation-to-operational factor     |    0.97 | AEMO generation proxy x 0.97 = plan source NEM load  | Authored (A010); measured against AEMO under [Generation to operational demand, measured](#generation-to-operational-demand-measured) |
| `delivery_fraction`                  |    0.91 | Source NEM load x 0.91 = customer-delivered energy   | 9% flat operational-load loss allowance, split 3% transmission and 6% distribution (A001) |
| National scaling                     |     1.3 | NEM source load x 1.3 = national grid-served load    | Stipulated handover factor in the ShARP review; not carried in `demand_plan.json` (A002)  |
| `anchor_2025_customer_delivered_twh` | 193.911 | 2025 customer-delivered reference                    | ShARP planned residual grid quantity (A008)                                               |

All three factors are authored rather than measured. 0.91 and 1.3 are recorded in the ShARP review as placeholders pending electricity-author
ratification; 0.97 was applied with no citation and is measured against AEMO above. The campaign's cap arithmetic multiplies by 0.91 but never by
1.3, so a cap quoted "per MWh delivered" is per MWh delivered on the NEM, not nationally.

The 0.97 and the 0.91 act on different gaps: 0.97 steps from sent-out generation to operational load, and 0.91 then steps from
operational load to customer-delivered energy. They do not overlap, but neither is an AEMO figure.

**confidence: low.** Every factor is a disclosed placeholder, and the 2025 anchor does not reconcile
with the trace store within 5% under either boundary reading: the store has no FY2025 at all, and back-extrapolating Step Change from FY2026 and
FY2027 gives about 176.75 TWh, against 213.09 TWh (anchor / 0.91) or 163.91 TWh (anchor / (0.91 x 1.3)).

## Generation to operational demand, measured

The 0.97 was authored with no source (A010). Measuring it against AEMO's own numbers shows two different ratios, and
0.97 matches neither literally. The inputs are the final 2026 ISP Step Change generation (S008) and the parsed Step
Change trace store summed over its 15 sub-regions per financial year (S001):

| FY | Generation excluding rooftop and storage (TWh) | Operational demand trace (TWh) | Storage losses (TWh) | Electrolyser and green steel load (TWh) | Unexplained (TWh) | Operational / generation | Generation net of storage losses / generation |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2027 | 190.6 | 179.5 | 0.9 | 0.3 | 9.9 | 0.942 | 0.995 |
| 2030 | 210.5 | 189.8 | 7.2 | 1.3 | 12.1 | 0.902 | 0.966 |
| 2035 | 259.0 | 219.3 | 13.1 | 8.8 | 17.9 | 0.847 | 0.950 |
| 2040 | 294.2 | 240.1 | 16.2 | 16.4 | 21.5 | 0.816 | 0.945 |
| 2045 | 317.0 | 247.2 | 17.8 | 24.6 | 27.4 | 0.780 | 0.944 |
| 2050 | 332.1 | 251.9 | 19.2 | 30.3 | 30.6 | 0.759 | 0.942 |

Storage losses are the negative of AEMO's "Storage and DSP net generation" series. Electrolyser load is the IASR's Step
Change domestic and green-commodity hydrogen (Mt) times its PEM electrolyser consumption rate, plus its green-steel arc
furnace load (S009); the export hydrogen rows are zero in Step Change. The unexplained remainder, 5% of generation in
FY2027 rising to 9% by FY2050, is not decomposed here: interconnector losses (which `OPSO_MODELLING` removes), electrolyser
balance of plant and any difference between the 2018 reference-year trace and AEMO's multi-year average are candidates.
The trace's FY2026 total is 178.1 TWh; FY2051 to FY2056 hold between 251.2 and 252.1 TWh.

**Operational demand is not 0.97 of generation.** It falls from 0.94 to 0.76 because AEMO's generation also serves
electrolysers, storage losses and network losses that operational demand excludes. **The campaign's load is not
operational demand either.** Each knot scales the operational-demand trace up to 0.97 x generation. So from 2030 on it
carries the electrolyser load, network losses and the unexplained remainder spread over the operational demand shape.
The campaign models none of them separately, and its transmission is lossless.

What the model does add on top of its load is storage round-trip loss. So the ratio that makes the model's generation
match AEMO's is generation net of storage losses over generation, the last column. **The recommended factor is that
ratio, per year** (A010): 0.995 in FY2027, 0.966 in FY2030, then 0.942 to 0.950 from FY2035 to FY2050. Per year, FY2027
to FY2050: 0.9951, 0.9903, 0.9773, 0.9656, 0.9626, 0.9602, 0.9579, 0.9552, 0.9496, 0.9509, 0.9494, 0.9539, 0.9474,
0.9448, 0.9437, 0.9436, 0.9509, 0.9455, 0.9437, 0.9415, 0.9447, 0.9433, 0.9455, 0.9421. FY2026 holds the FY2027 value
and years after FY2050 hold the FY2050 value.

Moving from 0.97 to this ratio shifts every common-basis conversion by the factor over 0.97:

| FY | Factor | Quantities (knots, AEMO and ShARP demand on the common basis) | Costs per MWh on the common basis |
| ---: | ---: | ---: | ---: |
| 2026, 2027 | 0.995 | +2.6% | -2.5% |
| 2030 | 0.966 | -0.4% | +0.5% |
| 2035 | 0.950 | -2.1% | +2.1% |
| 2040 | 0.945 | -2.6% | +2.7% |
| 2045 | 0.944 | -2.7% | +2.8% |
| 2050 on | 0.942 | -2.9% | +3.0% |

The 2030 to 2050 knots use 0.97 on the draft ISP: the shift is under 3%, inside the
factor's own uncertainty, and keeping them keeps the base comparable with run `2026-09-22T22.46_sc5`. The 2026 knot uses the measured
0.995, because there the difference decides whether the base can reproduce AEMO's 2026 generation.

**confidence: high** on the ratios, which are sums of AEMO-published series and the trace store. **confidence: medium**
on using the net-of-storage ratio as the factor: it assumes the model's storage losses match AEMO's, and it leaves the
unexplained 5% to 9% inside the load, as the knots already do.

## Checks that fail or cannot be made

| Check                                                                  | Result                                                                                                                   |
|------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| `central` tracks the campaign's own Step Change trace                  | No. -3.6% at 2030, +11.6% at 2040, +44.9% at 2050. Step Change is near-flat past FY2045; every trajectory keeps climbing |
| `low` and `high` bracketed by other scenarios in the campaign's inputs | Cannot check. The parsed store holds one scenario, POE and demand type only (Step Change, POE50, `OPSO_MODELLING`)       |
| `low` and `high` bracketed by the draft ISP range                      | `high` yes at 2030, 2040 and 2050. `low` sits 3% below the Slower Growth floor by construction, because of the 0.97      |
| `stress` at least 20% above `high`                                     | **Fails at 2030: 214.4 / 185 = +15.9%.** Clears the rule at 2040 (+29.0%), 2050 (+21.2%) and 2060 (+23.6%)               |
| A real FY2060 demand level exists                                      | No. The trace store ends FY2056 and the 2060 shape is FY2050 relabelled (A009); the 2060 TWh level is authored           |

## Plot

[`plot_demand_trajectories.py`](plot_demand_trajectories.py) draws the plan's Step Change knots, read from
`demand_plan.json`, against the draft CDP4 generation they were scaled from, the final 2026 ISP generation as published
and net of storage losses, and the operational-demand trace store. A second panel draws the two measured ratios to
generation with the authored 0.97 as a reference line. It writes `demand_trajectories.html` and `demand_trajectories.png`
beside itself.
