# Pumped hydro menu

## Purpose and scope

ISPyPSA's templater keeps only battery rows from the IASR storage summaries, so every pumped hydro energy storage (PHES) row AEMO
enumerates and costs is silently dropped. [`analysis/model/phes_menu.py`](../../model/phes_menu.py) restores them, adds two longer-duration
classes the published menu does not reach, and caps how much PHES any sub-region may build. The upstream templater filter is left unchanged.

## The candidate menu

Six new-entrant classes, all routed through the same translation path as battery candidates so they inherit the build-cost merge, locational
cost factors, connection costs, per-technology weighted average cost of capital and fixed operating cost handling.

| Class | Duration (h) | Source | Round-trip efficiency | Fixed operating cost (A$/kW/y) | Total lead time (y) |
|---|---:|---|---:|---:|---:|
| Pumped Hydro (10hrs storage) | 10 | IASR workbook | 76% | 96.7385 | 8 |
| Pumped Hydro (24hrs storage) | 24 | IASR workbook | 76% | 74.84505 | 10 |
| Pumped Hydro (48hrs storage) | 48 | IASR workbook | 76% | 85.5372 | 10 |
| BOTN - Cethana | 20 | IASR workbook | 80% | 74.84505 | 10 |
| Pumped Hydro (168hrs storage) | 168 | Authored | 76%, inherited | 85.5372, inherited | 10, inherited |
| Pumped Hydro (336hrs storage) | 336 | Authored | 76%, inherited | 85.5372, inherited | 10, inherited |

Economic life is 40 years for every class and the Step Change weighted average cost of capital is 8.5%. A class is only offered in
investment periods at or after 2025 plus its total lead time, so the 10-hour class is first buildable in 2033 and the rest in 2035.

Two committed or policy projects are added as fixed units: Kidston (250 MW, 900 MWh, commissioning 2027, North Queensland) and Phoenix
(810 MW, 9,720 MWh, commissioning 2032, Central New South Wales).

**confidence: high** for the four published classes, every parameter of which is read from a named sheet of the cached IASR workbook.

## The two authored classes

The published menu stops at 48 hours, leaving the modelled fleet no low-carbon firming beyond a couple of days. The 168-hour and 336-hour
classes extend it to one and two weeks.

| Parameter | Treatment |
|---|---|
| Capital cost | Extrapolated: per financial-year cost column, a least-squares line `capex_per_kw = power_cost + reservoir_cost_per_hour x duration_hours` is fitted to the published 10, 24 and 48-hour points and evaluated at 168 and 336 |
| Everything else | Inherited unchanged from the 48-hour class |

The fit is physically meaningful rather than curve-tracing: the intercept is power-related cost (turbines, penstock, connection) and the
slope is reservoir cost per hour of storage. Fitting per year means the new classes follow the published cost trajectory's shape. The
published points sit close to a line, with an R-squared of about 0.977 in every Step Change year, and a year whose fit falls below 0.95 is
logged rather than used silently.

Fixed operating cost is inherited rather than scaled because the published values are not monotonic in duration (10 h 96.7385, 24 h
74.84505, 48 h 85.5372), so any duration scaling would be invention.

**confidence: medium.** The capital-cost extrapolation is disciplined and its fit quality is checked, but 168 and 336 hours are three and
seven times beyond the furthest published point, and a real two-week reservoir is unlikely to be the same engineering as a two-day one at
the same efficiency and operating cost.

## Site limits

AEMO's `build_limits_phes` table gives a megawatt limit per sub-region per duration class, on a GHD 2025 site assessment basis. Those limits
bound power at PHES-suitable sites, so a 168-hour reservoir is a deeper reservoir at an assessed site, not an extra site. Each authored
class therefore takes its sub-region's 48-hour limit as its own build limit, and one `<=` constraint per sub-region caps the sum of all
new-entrant PHES power in that sub-region at that same figure, so the duration classes compete for one site budget instead of stacking. A
sub-region with no published 48-hour limit is offered neither authored class.

Committed PHES is not netted off: the workbook's notes state the limits exclude Snowy 2.0 and Borumba, so they are additive with the
committed fleet.

Enforced right-hand sides, as recorded in the limits inventory for the two reference solves.

| ISP sub-region id | 2060 stress run (MW) | 2050 central run (MW) | Binding |
|---|---:|---:|---|
| `cnsw` | 2,724.1 | 3,900.0 | no |
| `nnsw` | 18,840.7 | 19,341.5 | no |
| `snsw` | 2,300.0 | 2,300.0 | no |
| `cq` | 1,893.5 | 5,774.6 | no |
| `nq` | 10,010.0 | 10,200.0 | no |
| `sq` | 1,582.5 | 1,600.0 | yes, in the 2050 central run |
| `nsa` | 0.0 | 800.0 | no |
| `tas` | 1,319.4 | 3,468.9 | no |
| `wnv` | 6,710.6 | 9,206.3 | no |

**confidence: low on the enforced values.** The constraint as written passes the published 48-hour limit straight through with nothing
subtracted, so the right-hand side should be identical in both runs. It is not: `cq` differs by a factor of three and `nsa` is zero in one
run and 800 MW in the other. Nothing in this fork's code path explains the difference, so the site
limits are the one part of this menu that should be re-derived before being relied on. The design intent -- one site budget shared across
duration classes, additive with committed projects -- is **confidence: high** and is stated in the module itself.

## Plot

[`plot_phes_menu.py`](plot_phes_menu.py) draws capital cost against storage duration for each milestone year, distinguishing the published
10, 24 and 48-hour points from the authored 168 and 336-hour points it produces by calling the model's own fit, with the shared site ceilings
beside them. It writes `phes_menu.html` and `phes_menu.png` beside itself.
