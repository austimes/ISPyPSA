# Biomass

## Purpose and scope

Three separate authored limits bound biomass in this fork, and they are easy to confuse:

| Limit | Quantity bounded | Where |
|---|---|---|
| Supply-curve tranches | Fuel energy per year, in petajoules (PJ), priced in steps | [`analysis/model/data/biomass_supply_curve_central_held_to_2060.csv`](../../model/data/biomass_supply_curve_central_held_to_2060.csv) |
| Capacity cap | New-entrant biomass generating capacity, in megawatts | [`analysis/model/biomass_cap.py`](../../model/biomass_cap.py) |
| Carbon cap | Biomass residual methane and nitrous oxide, in tonnes of carbon dioxide equivalent | [`analysis/hpc/manifest.py`](../../hpc/manifest.py), documented in [`../carbon_caps/`](../carbon_caps/) |

The problem all three respond to is that the IASR defaults make biomass structurally the cheapest firm capacity whenever coal retires
without a storage mandate: a fuel cost of A$0.66/GJ with no availability constraint drove early runs to tens of times current Australian
biomass consumption, and spreading new-entrant biomass across every sub-region did not fix it.

## Supply-curve tranches

Annual fuel availability by tranche, with a price adder on top of the base fuel cost. The curve is flat from 2055 and the file's last row
is 2060, which is what "held to 2060" in its name means.

| Tranche | 2025 (PJ) | 2030 (PJ) | 2040 (PJ) | 2050 and 2060 (PJ) | Adder (A$/GJ) |
|---|---:|---:|---:|---:|---:|
| `existing_industry_byproduct` | 30.0 | 30.0 | 30.0 | 30.0 | 0.0 |
| `collected_residues` | 5.0 | 25.0 | 60.0 | 90.0 | 5.5 |
| `energy_crops` | 0.0 | 0.0 | 30.0 | 120.0 | 10.0 |
| `imported_pellet_backstop` | unbounded | unbounded | unbounded | unbounded | 15.0 |

Bounded availability at 2050 therefore totals 240 PJ per year, with an unbounded backstop above it at A$15/GJ.

**confidence: low.** The three bounded tranche trajectories, their step sizes and their price adders carry no citation anywhere in this
fork. Their shape -- a fixed byproduct base, residues ramping to a plateau, energy crops starting late -- is plausible, but the numbers
themselves cannot be traced to a source.

## Capacity cap

NEM-wide new-entrant biomass capacity, applied as a custom constraint summing the 12 sub-region biomass new entrants per milestone year.
There is no existing biomass capacity in the IASR cache, so the cap applies to new entrants only.

| Year | Cap (MW) | Stated basis |
|---|---:|---|
| 2025 | 1,000 | Approximately current Australian biomass-for-electricity capacity |
| 2030 | 1,500 | Early-deployment growth |
| 2035 | 2,000 | Interpolation |
| 2040 | 3,000 | Interpolation |
| 2045 | 4,000 | Interpolation |
| 2050 | 5,000 | Upper bound of the ARENA bioenergy roadmap range across all bioenergy categories |

At about 90% capacity factor the 2050 cap corresponds to roughly 39 TWh of generation, which the module itself calls optimistic against the
5 to 15 TWh range AEMO and industry projections suggest. It is also inconsistent in magnitude with the supply curve: 39 TWh of electricity
is about 140 PJ, needing around 350 PJ of fuel at a plausible conversion efficiency, well past the 240 PJ of bounded tranches, so the
unbounded import backstop would have to carry the difference.

**confidence: low.** Three sources are named (an ARENA bioenergy roadmap, AEMO ISP Step Change technology projections, a Clean Energy
Council investment report) but none is cited to an edition, page or table, and the module describes the values as defensible upper bounds
rather than sourced figures. The intermediate years are interpolation, not evidence.

The cap constrains power, not fuel. A generation-energy constraint would be the rigorous form, but the custom-constraints framework does not
expose time-weighted generation sums as left-hand-side terms.

## Biomass is not free under the carbon cap

The cap constraint sums `isp_residual_co2_t_per_mwh` over every generator with a positive residual. Biomass has one: its cross-walk to the
National Greenhouse Accounts Factors 2024 gives biogenic carbon dioxide of zero but methane and nitrous oxide combustion residuals of
0.8 and 1.0 kg CO2e/GJ, for 1.8 kg CO2e/GJ in total. That is small per gigajoule and decisive at the deepest cap rungs.

| Step | Arithmetic | Result |
|---|---|---:|
| Biomass fuel drawn under the 0.0005 ladder in the probed run | 30 PJ byproduct at its cap, plus 2.5 PJ of residues | 32.5 PJ |
| Residual emissions from that fuel | 32.5e6 GJ x 1.8 kg CO2e/GJ | 58,500 t CO2e |
| The cap that run was held to at 2060 | 0.0001 t/MWh on the source basis x 568.4 TWh | 56,840 t CO2e |

The implied residual is about 3% above the whole annual budget. At the deepest rung, then, what limits biomass is the carbon cap, not the
supply curve (which still has over 200 PJ untouched) and not the capacity cap. The same arithmetic at the shallower 2050 rungs is less
dramatic: the 0.0005 delivered-basis cap on the central trajectory is 166,075 t CO2e, so 32.5 PJ of biomass would consume about 35% of it.

**confidence: medium** on the emission factor, the cap arithmetic and the cap constraint's coefficient, which are all read from code;
**confidence: low** on the 32.5 PJ, which comes from a probe transcript that is not committed and so cannot be re-derived against the cap
quoted above. Read it as the scale of the draw rather than an exact figure. The 30 PJ within it is confirmed only as "at its cap" in the
limits inventory.

## Plot

[`plot_biomass_limits.py`](plot_biomass_limits.py) draws the supply curve as a priced step of cumulative availability for each milestone
year, marks the 32.5 PJ actually drawn under the deepest cap, and puts the capacity ceiling beside it. It writes `biomass_limits.html` and
`biomass_limits.png` beside itself.
