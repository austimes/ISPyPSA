# Pumped hydro menu -- source evidence

Verbatim evidence behind [`research.md`](research.md). Source ids match [`source_ledger.csv`](source_ledger.csv).

## S001 -- AEMO 2026 IASR workbook, PHES sheets

**Source:** IASR 2026 version 7.8 final workbook, parsed to the local workbook cache. The sheets and their cached CSV names are listed
verbatim in [`analysis/model/phes_menu.py`](../../model/phes_menu.py):

> "Sources (IASR 2026 v7.8 Final workbook, parsed to the workbook cache):
>   - Candidate set, durations, pumping (round-trip) efficiencies: sheet "Storage properties" -> cache
>     `pumped_hydro_new_entrant_properties.csv` (76% for 10/24/48h per note 4 "based on information provided by Hydro Tasmania"; 80% for
>     BOTN - Cethana - 20h).
>   - Build limits (MW per sub-region per duration class): sheet "Build limits - PHES" -> cache `build_limits_phes.csv` (GHD 2025 Pumped
>     Hydro Energy Storage Parameter Review basis; notes 1-2: limits exclude Snowy 2.0 and Borumba, which are modelled as specific projects --
>     so these caps are additive with the committed fleet).
>   - Locational cost factors: sheet "Technology specific LCFs" -> cache `technology_specific_lcfs.csv` ...
>   - Connection costs ($/kW by NEM region): cache `connection_costs_other.csv`.
>   - WACC (% by scenario): cache `wacc.csv` (Step Change: 8.5 for all four).
>   - Economic life / total lead time (years): cache `lead_time_and_project_life.csv` (40 y life; lead 8 y for 10h, 10 y for
>     24h/48h/BOTN - Cethana).
>   - FOM ($/kW/yr): cache `fixed_opex_new_entrants.csv` (10h 96.7385, 24h 74.84505, 48h 85.5372, BOTN - Cethana 74.84505)."

No verbatim quote from the workbook itself is available: neither the workbook nor its cache is in this repository, so every published figure
above reaches `research.md` through this code citation.

On the committed projects, verbatim:

> "Kidston / Phoenix unit parameters: cache
> `maximum_capacity_existing_committed_anticipated_additional_generators.csv` (Kidston 250 MW / 900 MWh, commissioning 2027-01-01, Committed,
> NQ; Phoenix 810 MW / 9,720 MWh, commissioning 2032-07-01, Additional policy-supported project, CNSW)"

And on an internal inconsistency in the workbook, verbatim:

> "NOTE the workbook is internally inconsistent on Kidston's duration (max-capacity table 900 MWh -> 3.6 h; Storage properties sheet 6 h;
> technology class label 10 h); the max-capacity table is used, matching how ECAA battery durations are derived."

## S002 -- GHD 2025 Pumped Hydro Energy Storage Parameter Review

**Source:** the basis AEMO cites for its `build_limits_phes` table.

No verbatim quote is available: no local copy of this review exists in or beside this repository, and the code cites it only as the basis of
the workbook sheet it reads.

## S003 -- The menu repair as implemented

**Source:** [`analysis/model/phes_menu.py`](../../model/phes_menu.py).

On the defect it repairs, verbatim:

> "ISPyPSA's templater keeps only battery rows from the IASR storage summaries (src/ispypsa/templater/storage.py:56-62), so every pumped-hydro
> row -- the new-entrant candidates AEMO enumerates and costs, and two committed/policy projects -- is silently dropped."

On why the authored classes exist, verbatim:

> "The published IASR menu stops at 48 hours, which leaves the modelled fleet with no low-carbon firming beyond a couple of days."

On the capital-cost extrapolation, verbatim:

> "Capex is the ONLY authored parameter, and it is extrapolated rather than assumed: per financial-year column of `new_entrant_build_costs`,
> a least-squares line `capex_per_kw = power_cost + reservoir_cost_per_hour * duration_hours` is fitted across the published 10 h, 24 h and
> 48 h points and evaluated at 168 h and 336 h. The intercept is the power-related cost (turbines, penstock, connection) and the slope the
> reservoir cost per hour of storage, so the fit carries physical meaning rather than tracing a curve through arbitrary points."

On the fit quality, verbatim:

> "The published points sit close to a line (R-squared ~0.977 in every Step Change year); a year whose fit falls below _FIT_R_SQUARED_FLOOR
> is logged rather than silently used."

On what is inherited and why, verbatim:

> "EVERYTHING else is inherited unchanged from the 48-hour class: pumping (round-trip) efficiency, FOM, total lead time, economic life,
> locational cost factors and connection costs. FOM in particular is inherited rather than scaled, because the published FOM is not monotonic
> in duration (10 h 96.7385, 24 h 74.84505, 48 h 85.5372) so any duration scaling would be invention."

On the shared site budget, verbatim:

> "Those limits bound POWER at PHES-suitable sites, so a 168-hour reservoir is a deeper reservoir at an assessed site, not an additional site.
> Each authored class therefore takes its sub-region's 48-hour limit as its `build_limit_mw`, and a per-sub-region `<=` custom constraint caps
> the SUM of all new-entrant PHES power in that sub-region at that same 48-hour limit, so the duration classes compete for one site budget
> instead of stacking to several times the assessed potential."

And verbatim from `_add_shared_site_constraints`, on committed projects:

> "Committed PHES is not netted off: the workbook's notes 1-2 state the limits exclude Snowy 2.0 and Borumba, so they are additive with the
> committed fleet."

## S004 -- Enforced site limits in the reference solves

**Source:** the limits inventory described in [`../rez_transmission_limits/source_data.md`](../rez_transmission_limits/source_data.md),
which read each run's own `custom_constraints_rhs.csv`.

Verbatim:

> "one `<=` constraint per sub-region (`phes_site_limit_<subregion>_<year>`) capping total new-entrant PHES power at the GHD 2025 48-hour
> site assessment limit for that sub-region. Values below are the enforced RHS read from each run's `custom_constraints_rhs.csv`; `sq`
> (Southern Queensland) was binding in the 2050-central run."

The two runs report different right-hand sides for the same sub-regions. The constraint builder passes the published limit through with
`existing_table=None`, so nothing in the code path read here subtracts anything from it, and the difference is unexplained rather than
attributed.
