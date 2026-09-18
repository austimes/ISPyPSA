# Modelling assumptions

Every way this fork's model differs from upstream ISPyPSA and from the data AEMO publishes for its ISP - the national
electricity capacity-expansion roadmap it produces for the National Electricity Market (NEM) - in the Inputs,
Assumptions and Scenarios Report (IASR). Grouped under four headings, one dot point per item, one line each.

## Upstream fixes in `src/ispypsa`

- **Pumped hydro candidates restored** - upstream's workbook parser reads the wrong header row range for pumped hydro
  storage properties, silently dropping every pumped hydro candidate and committed row before the fork's own
  pumped-storage patches ever see them; this fork reads the correct row range.
- **Hydro annual energy budget from the 2026 ISP** - the cap on total annual conventional-hydro dispatch follows AEMO's
  own year-by-year 2026 ISP Step Change generation trajectory; upstream applies a flat capacity-factor estimate instead.
- **Existing battery build-limit fill** - an existing battery with no workbook build limit gets an unlimited PyPSA
  build ceiling; upstream leaves the limit undefined, which PyPSA cannot solve.
- **Numeric-strip regex for 4+ digit values** - upstream's workbook-cell cleaning rule truncates every plain
  four-or-more-digit number to its first three digits (for example, 1660 reads as 166); this fork's regex matches the
  whole number.
- **Offshore wind excluded from the onshore land-use limit** - upstream's coarse wind-carrier filter on the onshore
  build-limit constraint also captures offshore wind candidates; this fork gives offshore wind its own resource-type
  exclusion from that limit.
- **Existing wind/solar/hydro fixed operating and maintenance (FOM) cost per station** - upstream's FOM lookup for
  renewable and hydro generators joins on a technology-class label the workbook's FOM table never carries, silently
  leaving most of the fleet without a fixed cost; this fork joins by station name instead, the same way thermal plant
  does.
- **Carbon capture and storage (CCS) transport-and-storage supply curve, config-gated and disabled in the campaign** - an
  optional model of CO2 transport pricing and per-sink injection limits; switched off by default (free, unlimited
  disposal, matching AEMO's own ISP treatment) and left off for this campaign in favour of a flat transport-and-storage
  charge.
- **2060 trajectory hold** - an investment period beyond a trajectory table's published horizon (for example, build
  costs or connection costs) carries forward the last published year's values instead of being left unpriced.
- **Thermal heat-rate/VOM median fill** - upstream dispatches an existing thermal generator missing a heat rate or
  variable operating and maintenance (VOM) cost at zero fuel cost and zero emissions; this fork assigns it the median of
  its same-technology-type peers instead.
- **Gas un-blend switch** - a configuration flag can price the Gas carrier from the gas price table alone, leaving out
  AEMO's mandated biomethane blend, so the blend's cost effect can be isolated.
- **Biomass supply curve and gas terajoule fix** - a stepped, config-gated biomass feedstock supply curve, and a fix
  denominating gas supply-curve purchases in terajoules rather than gigajoules.

## Fork input patches in `analysis/model`

- **Pumped-storage fix** - re-routes Wivenhoe, Shoalhaven, Borumba and Snowy 2.0 into PyPSA storage units instead of
  unconstrained generators, from CS Energy, Origin Energy, Queensland Hydro and Snowy Hydro facility documentation plus
  AEMO's Generation Information and IASR committed-generator summary.
- **PHES menu repair** - restores the IASR's new-entrant pumped hydro energy storage (PHES) candidates, workbook build
  limits and lead times, and two committed/policy units, from the IASR's own new-entrant pumped hydro tables.
- **Ageing-fleet maintenance overlay** - adds an ageing cost premium to thermal generators nearing end of life, from
  AEMO/Origin Energy refurbishment cost disclosures and CSIRO GenCost 2024-25.
- **End-of-life renewable repowering** - extends wind and solar closure years with an annualised repowering cost
  premium, from CSIRO GenCost 2024-25 and IRENA's Renewable Power Generation Costs 2023.
- **Biomass availability cap** - a National Electricity Market (NEM)-wide new-entrant biomass capacity ceiling by
  milestone year, from the ARENA Bioenergy Roadmap 2021 and AEMO's ISP 2024 Step Change technology projections.
- **Biomass feedstock cost** - re-prices new-entrant biomass feedstock from the IASR's residue-tier price to a
  scale-appropriate delivered cost, from IRENA's locally-collected feedstock cost tier.

## Authored assumptions with no AEMO source

- The 168-hour and 336-hour pumped hydro storage classes and their extrapolated capital costs.
- The 2060 hold of every trajectory table and trace at its last published year.
- The held-to-2060 gas and biomass supply curves.
- The flat A$89.93 per tonne CCS transport-and-storage charge used in place of the supply curve.
- The ageing-fleet maintenance cost premium.
- The 20-year renewable repowering life extension.
- The biomass capacity cap.

## Campaign method

- Recursive-dynamic chains: each milestone year's new build and retained capacity carries forward into the next.
- Thirteen representative weeks sampled per solve.
- Per-period absolute carbon dioxide equivalent (CO2e) caps, rather than a carbon price, drive the campaign's pressure
  ladder.
- Fossil-only gas pricing (the gas un-blend switch) throughout the campaign.
- Gurobi barrier solver settings, tuned for this campaign's problem size.
