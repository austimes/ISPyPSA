# Modelling assumptions

Every way this fork's model differs from upstream ISPyPSA and from the data AEMO publishes for its ISP - the national
electricity capacity-expansion roadmap it produces for the National Electricity Market (NEM) - in the Inputs,
Assumptions and Scenarios Report (IASR). Grouped under four headings, one dot point per item, one line each.

## Upstream fixes in `src/ispypsa`

- **Pumped hydro candidates restored** - upstream's workbook parser reads the wrong header row range for pumped hydro
  storage properties, silently dropping every pumped hydro candidate and committed row before the fork's own
  pumped-storage patches ever see them; this fork reads the correct row range, so workbook build limits are carried
  through, with unlimited build for candidates that have none.
- **Hydro annual energy budget from the 2026 ISP** - the cap on total annual conventional-hydro dispatch follows AEMO's
  own year-by-year 2026 ISP Step Change generation trajectory; upstream applies a flat capacity-factor estimate instead.
  The budget is a NEM-wide annual figure and is not scaled down for a run filtered to fewer regions.
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
- **Carbon capture and storage (CCS) transport-and-storage supply curve, config-gated** - an optional model of CO2
  transport pricing and per-sink injection limits, defaulting to off in `msm solve` (free, unlimited disposal, matching
  AEMO's own ISP treatment). The shipped tranche file carries zero injectivity caps for every sink and year, so enabling
  it pins CCS output to zero. The campaign's CCS treatment is instead the flat A$89.93 per tonne transport-and-storage
  charge.
- **2060 trajectory hold** - an investment period beyond a trajectory table's published horizon (for example, build
  costs or connection costs) carries forward the last published year's values instead of being left unpriced.
- **Thermal heat-rate/VOM median fill** - upstream dispatches an existing thermal generator missing a heat rate or
  variable operating and maintenance (VOM) cost at zero fuel cost and zero emissions; this fork assigns it the median of
  its same-technology-type peers instead.
- **Gas un-blend switch** - a configuration flag can price the Gas carrier from the gas price table alone, leaving out
  AEMO's mandated biomethane blend, so the blend's cost effect can be isolated.
- **2026 IASR additional batteries kept** - upstream's battery templater keeps only the 2024 IASR status label
  "Additional projects", so every 2026 IASR "Additional policy-supported project" battery is dropped; this fork keeps
  both labels.
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
- **Renewable energy zone (REZ) limit relaxation** - off unless a run passes `--rez-limit-factor`, in which case every
  REZ transmission limit, REZ transmission expansion headroom, offshore wind resource limit and land-use build limit is
  multiplied by that factor. The soft onshore wind and solar resource limits stay at AEMO's published level, because the
  social-licence premium prices capacity above them instead.
- **Social-licence premium on capacity above AEMO's limits** - off unless a run passes `--social-licence-premiums
  <first>,<second>` (the campaign uses `0.15,0.60`). Three things then change: ISPyPSA's one unbounded
  `<constraint>_relax_<year>` generator per soft REZ resource limit becomes two bounded tranches, of one and two times
  the published limit, priced at AEMO's violation penalty plus the two premium fractions of that zone's median
  new-entrant wind or solar annuitised capital cost; every expandable REZ and corridor link gains three priced capacity
  steps, its published expansion headroom free and then the two premium fractions of its own capital cost, with its
  untouched `<isp_name>_expansion_limit` constraint still the hard ceiling; and every expansion link carries a flat
  landholder payment adder, from the New South Wales Strategic Benefit Payments (A$200,000/km, treated as a 25-year
  total annuitised at the 3% transmission weighted average cost of capital) and the Victorian scheme (A$8,000/km/yr),
  converted at AEMO's capacity-weighted easement lengths of 0.149 km/MW for a REZ connection and 0.112 km/MW for a
  corridor. Derived in [`research/social_licence_premium/research.md`](research/social_licence_premium/research.md).
- **Build-rate premium** - off unless a run passes `--build-rate-premiums <csv>`, in which case each carrier's new build
  in a period pays the stepped A$/MW/yr adders of that file above its cumulative capacity steps. The shipped
  [`model/data/build_rate_premiums_central.csv`](model/data/build_rate_premiums_central.csv) carries free steps up to
  the Step Change build rate and two priced steps above it, derived in
  [`research/build_rate_premium/research.md`](research/build_rate_premium/research.md).
- **Transmission corridor limit relaxation** - off unless a run passes `--flow-path-limit-factor`, in which case the
  expansion headroom of every flow path between sub-regions is multiplied by that factor; REZ-to-sub-region
  connections and REZ group constraints belong to the REZ factor, so the two levers are independent.

## Authored assumptions with no AEMO source

- The 168-hour and 336-hour pumped hydro storage classes and their extrapolated capital costs.
- The 2060 hold of every trajectory table at its last published year, and the 2060 demand and weather traces relabelled
  from FY2055.
- The held-to-2060 gas and biomass supply curves.
- Stand-in reference-year-2018 traces for two ECAA projects the final 2026 trace release does not cover: Marulan Solar
  Farm uses the `Distribution_REZ_Marulan` solar trace and Willogoleche Wind Farm 2 uses stage 1's `WGWF1` trace.
  Mulwala Solar Farm (25.1 MW) has no trace and is excluded.
- Ten ECAA solar projects (Aldoga, Broadsound, Bundaberg, Goorambat East, Goulburn River, Kingaroy, Maryvale, Mortlake
  Energy Hub, Punch's Creek and Solar River) and zones N9a and N9b, absent from the final 2026 trace release, keep their
  reference-year-2018 traces from the `isp2026_final_v2` input package, extended to FY2026 by copying FY2027 back one
  year and to FY2052-FY2055 by copying FY2051 forward, with 29 February 2052 copied from the day before.
- The flat A$89.93 per tonne CCS transport-and-storage charge used in place of the supply curve.
- The ageing-fleet maintenance cost premium.
- The 20-year renewable repowering life extension.
- The biomass capacity cap.
- The REZ limit relaxation factor of a sensitivity run set: AEMO publishes no relaxed REZ limits, so the factor is a
  chosen test of how much of a deep-cap chain's cost sits in the REZ ceilings, not a forecast of buildable headroom.
- The two social-licence premium fractions and the tranche widths they apply over: no published source prices capacity
  beyond a REZ or corridor limit, so 15% is transferred from AEMO's own transmission social-licence cost impost and 60%
  from the top of its parcel-density-graduated REZ generation uplift.
- Treating the New South Wales Strategic Benefit Payment as a 25-year total: AEMO states it undiscounted, so the
  annuitisation to A$/MW/yr is the fork's own.
- The build-rate premium adders, which ship as zeros until the research topic lands.

## Campaign method

- Recursive-dynamic chains: each milestone year's new build and retained capacity carries forward into the next.
- Thirteen representative weeks sampled per solve.
- Per-period absolute carbon dioxide equivalent (CO2e) caps, rather than a carbon price, drive the campaign's pressure
  ladder.
- Demand range taken from the draft ISP: the low trajectory follows its Slower Growth generation total excluding rooftop
  solar and the stress trajectory its Accelerated Transition total, each scaled by 0.97 to step from generation to
  source-NEM operational load (the sent-out generation that storage charging and auxiliary loads absorb; an authored
  placeholder, since AEMO's draft ISP tables do not separate them), held past the published 2050 horizon to 2060 by the campaign's 2050-to-2060 growth ratio of about
  1.19, with low_bracket at 0.92 times low. Rooftop solar needs no correction: both the trace store and the draft ISP
  totals already exclude it.
- Fossil-only gas pricing (the gas un-blend switch) throughout the campaign.
- Near-term pipeline pin and pre-2030 rush charge: new-entrant generator and battery build is capped at a per-year
  allowance in 2026; in 2030 build up to each allowance is free and build above it pays a rush charge in A$/MW/yr,
  converted from ShARP's A$37.45/MWh charge on growth installed in FY2030, up to a hard ceiling of its own.
  Derived in [`research/near_term_pipeline/`](research/near_term_pipeline/) and
  [`research/pre2030_rush_charge/`](research/pre2030_rush_charge/).
- Gurobi barrier solver settings, tuned for this campaign's problem size.
