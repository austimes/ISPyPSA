# Conventional hydro energy budget

## Purpose and scope

ISPyPSA loads no hydro availability traces. Left alone, the solver dispatches every `Water`-carrier generator at whatever its capacity
allows, because hydro's marginal cost is near zero. This fork adds two constraints in
[`src/ispypsa/pypsa_build/generators.py`](../../../src/ispypsa/pypsa_build/generators.py): a monthly capacity-factor ceiling on
instantaneous output, and an annual energy budget on total output. Pumped hydro is not covered here; it is modelled separately as storage
units, and its menu is documented in [`../pumped_hydro_menu/`](../pumped_hydro_menu/).

Real hydro is water-limited, not just capacity-limited. The monthly ceiling alone does not express that: paired with a near-zero marginal
cost the solver simply sits at the ceiling in nearly every hour. The annual budget is what forces the solver to spend a limited amount of
water on its highest-value hours.

## The monthly capacity-factor ceiling

`_HYDRO_MONTHLY_CF`, applied as a static `p_max_pu` series to every `Water`-carrier generator.

| Months | Capacity factor | Season |
|---|---:|---|
| January, February | 0.25 | Peak summer, low inflows |
| March, April, May | 0.35 | Autumn |
| June, July, August | 0.40 | Winter, peak inflows |
| September, October, November | 0.45 | Spring, snowmelt |
| December | 0.30 | Early summer |

The annual mean is about 0.37, inside the 30 to 45% band for Australian conventional hydro. The profile is derived from AEMO Generation
Information long-run monthly hydro generation, dominated by the New South Wales and Tasmanian fleets, and is applied uniformly: no
generator gets its own profile.

**confidence: medium.** The seasonal shape is defensible and the annual mean lands in the expected band, but the derivation is described
rather than reproduced from a cited table, and one profile for Tumut, Murray, Eildon and Bendeela alike is a simplification. Per-facility
differentiation needs AEMO Generation Information per-facility data.

## The annual energy budget

`_HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY`, applied as a PyPSA `GlobalConstraint` of type `operational_limit`, one per investment period.

| Financial year | Budget (TWh) | Financial year | Budget (TWh) |
|---|---:|---|---:|
| 2027 | 16.670 | 2039 | 13.636 |
| 2028 | 15.496 | 2040 | 12.770 |
| 2029 | 15.518 | 2041 | 10.776 |
| 2030 | 12.989 | 2042 | 9.831 |
| 2031 | 13.099 | 2043 | 10.737 |
| 2032 | 12.686 | 2044 | 10.726 |
| 2033 | 12.164 | 2045 | 11.002 |
| 2034 | 12.472 | 2046 | 9.188 |
| 2035 | 14.363 | 2047 | 9.972 |
| 2036 | 13.484 | 2048 | 11.813 |
| 2037 | 13.301 | 2049 | 11.381 |
| 2038 | 14.847 | 2050 | 9.834 |

The series is AEMO's own modelled conventional-hydro generation under Step Change, so it carries AEMO's view of both water availability and
how hard the fleet is worked. It declines from about 16.7 TWh in 2027 to about 9.8 TWh in 2050. Years outside 2027 to 2050 are clamped to
the nearest published year, so a 2025 or 2026 period uses the 2027 figure and the campaign's 2060 milestone uses the 2050 figure.

**confidence: high** on the numbers, which are transcribed from a named AEMO workbook, sheet, column and sensitivity;
**confidence: low** on the 2060 milestone, which reuses the 2050 budget because nothing is published beyond FY2050 and the campaign holds
2050 conditions forward.

## The region-filter skip

The budget is a NEM-wide annual total. The pypsa-friendly tables reaching the constraint are already region-filtered, so the NEM-wide
capacity the budget belongs to cannot be recovered and the budget cannot be scaled to the modelled share of the fleet.

| Run type | Behaviour |
|---|---|
| Whole-of-NEM (`filtered_to_regions` is `None`) | Budget applied per investment period |
| Filtered to a subset of regions or sub-regions | Budget skipped, with a warning |
| Network has no `Water` generators | Nothing added |

Applying a NEM-wide total to, say, a New South Wales-only run would leave that fleet effectively uncapped, so skipping is the honest
choice. It does mean any region-filtered run in this fork dispatches hydro against the monthly ceiling alone, at roughly four times a
realistic annual energy. Every campaign chain is whole-of-NEM, so the campaign results are not affected; smaller diagnostic runs are.

**confidence: high.** The condition and its consequence are both stated in the function's own docstring and implemented as described.

## Plot

[`plot_hydro_budget.py`](plot_hydro_budget.py) draws the published FY2027 to FY2050 budget in terawatt-hours, the clamped extension that
serves every later year, and the budget each campaign milestone is solved against. It writes `hydro_budget.html` and `hydro_budget.png`
beside itself.
