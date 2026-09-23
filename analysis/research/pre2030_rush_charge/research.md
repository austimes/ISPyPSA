# Pre-2030 rush charge

## Purpose and scope

The 2030 period covers the four build years FY2027 to FY2030. The near-term pipeline pin gives new entrants a free
allowance in that period ([`../near_term_pipeline/`](../near_term_pipeline/)). Build above the allowance is not
forbidden: it pays a rush charge, up to a hard ceiling. This topic converts ShARP's price for supply added at short lead
time, which is quoted per megawatt hour (MWh), into the per-megawatt annual adder the model's capacity tranches need.

ShARP, the whole-of-economy model the campaign feeds, charges A$37.447769/MWh on growth in grid supply beyond its plan
that is installed in FY2030 (A045 in ShARP's grid electricity role, S001). The campaign reuses that number so the two
models price a 2030 rush the same way.

## What the campaign does

| Tranche in the 2030 period | Width | Adder (A$/MW/yr, real June 2025 dollars) |
| -------------------------- | ----- | ---------------------------------------: |
| Generation within the allowance | the generation allowance | 0 |
| Generation above the allowance | up to the hard ceiling | **71,400** |
| Storage within the allowance | the storage allowance | 0 |
| Storage above the allowance | up to the hard ceiling | **24,900** |

The charge applies in the 2030 period only. ShARP's adjustment "expires after that year" (S001), so the adder must not be
carried into later periods as capital cost.

## Derivation

```text
rush_aud_2025_per_mwh_delivered  = 37.447769 x 1.0218                    = 38.26
rush_aud_2025_per_mwh_generated  = 38.26 x 0.7915                         = 30.29
generation_adder_aud_per_mw_yr   = 30.29 x 8,760 h x 0.2693               = 71,444
storage_adder_aud_per_mw_yr      = 30.29 x 823.6 discharge hours per MW   = 24,943
```

| Step | Value | Basis |
| ---- | ----: | ----- |
| ShARP short-lead-time charge, A$2024 per MWh delivered | 37.447769 | S001, S002 |
| A$2024 to real June 2025 dollars | 1.0218 | A001: ABS CPI, as in [`../sharp_grid_reference/`](../sharp_grid_reference/) |
| MWh delivered per MWh generated | 0.7915 | A002: ShARP's own delivery factor, its A052 |
| Capacity factor of the Step Change FY2027 to FY2030 new build mix | 0.2693 | A003: CDP4 energy and capacity additions |
| Battery discharge per MW of battery, hours per year | 823.6 | A004: base chain of run `2026-09-22T22.46_sc5`, 2030 period |

### Capacity factor of the new build mix

The capacity factor is the Step Change path's added energy over its added capacity between FY2026 and FY2030, from the
draft 2026 ISP candidate development path 4 (CDP4) files (S004):

| Carrier | Capacity 2026 (GW) | Capacity 2030 (GW) | Added (GW) | Energy 2026 (TWh) | Energy 2030 (TWh) | Added (TWh) | Marginal capacity factor |
| ------- | -----------------: | -----------------: | ---------: | ----------------: | ----------------: | ----------: | -----------------------: |
| Wind | 11 | 26 | 15 | 37 | 81 | 44 | 0.335 |
| Solar, utility | 9 | 32 | 23 | 20 | 68 | 48 | 0.238 |
| Gas | 11 | 12 | 1 | 8 | 3 | not used | - |
| **Mix** | | | **39** | | | **92** | **0.269** |

Gas output falls while its capacity rises, because the new gas is peaking plant and coal-to-renewables displacement
drives the energy change. So gas contributes capacity but no energy to the mix, which treats new peaking gas as running
close to zero hours. Leaving gas out altogether would give 0.276 and a generation adder of 73,300.

### Battery discharge hours

Neither CDP4 file carries storage, so the storage figure comes from the campaign's own base chain
(`outputs/2026-09-22T22.46_sc5`, cell `ext_step_change_sc`, 2030 period): 12.016 TWh discharged from 14.59 GW of
batteries, or 823.6 hours per MW per year (a 9.4% capacity factor). That fleet is existing and committed plant with no
new build, so the figure describes how the model works batteries in 2030, not a published assumption.

## The numbers

| Quantity | Value | Unit |
| -------- | ----: | ---- |
| `pipeline_rush_charge_aud_per_mw_yr.generation` | 71,400 | A$/MW/yr, real June 2025 dollars |
| `pipeline_rush_charge_aud_per_mw_yr.storage` | 24,900 | A$/MW/yr, real June 2025 dollars |
| Generation, without the 0.7915 delivery factor | 90,300 | A$/MW/yr |
| Storage, without the 0.7915 delivery factor | 31,500 | A$/MW/yr |

For scale, against the 2030 annuitised capital costs in [`../build_rate_premium/`](../build_rate_premium/): the
generation charge is 29% of an onshore wind megawatt's annuity (246,256) and 90% of a utility solar megawatt's (79,700).
It is 1.7 times the build-rate premium's first adder on wind and 5.1 times it on solar. The storage charge is 20% of a
four-hour battery's annuity (123,037).

**confidence: medium** on the generation adder. The charge, dollar year and delivery factor are read directly, and the
capacity factor is arithmetic on AEMO's own path. The weak link is ShARP's figure itself, which ShARP tags exploratory.

**confidence: low** on the storage adder. ShARP prices energy, and a battery adds no net energy. Charging it per
discharged MWh is a convention, and the discharge hours come from one campaign run rather than a published source.

## Caveats

| Caveat | Effect |
| ------ | ------ |
| One charge per MW for every technology | At 71,400 A$/MW/yr, solar pays about A$34/MWh generated and wind about A$24/MWh; only the mix averages A$30.29/MWh. A rush of solar is therefore charged more per MWh than ShARP charges |
| ShARP's persistent overflow-growth band is left out | ShARP adds A$2.155449/MWh on the first 12 TWh/year of growth, for a combined A$39.603218/MWh rush price (S001). Including it would raise both adders by 5.8% |
| Storage allowance of zero | With the 2030 storage allowance at 0 MW ([`../near_term_pipeline/`](../near_term_pipeline/), A009 there), a ceiling set at twice the allowance forbids all 2030 storage new build. A storage ceiling needs its own value for the storage rush tranche to exist |
| Draft CDP4 capacity factor | Final 2026 ISP capacity by fuel was not available; the draft path's new build mix may differ |

## Plot

[`plot_pre2030_rush_charge.py`](plot_pre2030_rush_charge.py) draws both rush adders beside the 2030 annuitised capital
cost and the build-rate premium's first adder for wind, solar and batteries, so the size of the charge can be read
against what a megawatt already costs. It writes `pre2030_rush_charge.html` and `pre2030_rush_charge.png` beside itself.
Run it with:

```bash
uv run --with kaleido python analysis/research/pre2030_rush_charge/plot_pre2030_rush_charge.py
```
