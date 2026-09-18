"""PHES menu repair — pre-pass applied to ALL archetypes (runs after
_pumped_storage_fix).

ISPyPSA's templater keeps only battery rows from the IASR storage summaries
(src/ispypsa/templater/storage.py:56-62), so every pumped-hydro row — the
new-entrant candidates AEMO enumerates and costs, and two committed/policy
projects — is silently dropped. `_pumped_storage_fix` re-injects four named
facilities only. This pre-pass restores the rest of the workbook's PHES menu:

  1. New-entrant PHES candidates per sub-region — Pumped Hydro (10hrs/24hrs/
     48hrs storage) plus the BOTN - Cethana - 20h project option — appended to
     `new_entrant_batteries` so they flow through the SAME translation path as
     battery candidates (build-cost merge by technology_type, LCF, connection
     cost, per-technology WACC annuitisation, FOM).
  2. Two authored long-duration classes, Pumped Hydro (168hrs storage) and
     Pumped Hydro (336hrs storage), on the same code path (see below).
  3. Workbook build limits applied per candidate via a new `build_limit_mw`
     column, which the translator maps to PyPSA `p_nom_max`.
  4. IASR total lead times gate availability: a candidate is only offered in
     investment periods >= _AVAILABILITY_ANCHOR_FY + total lead time.
  5. A per-sub-region shared-site cap on total new-entrant PHES power (see
     below).
  6. Kidston and Phoenix Pumped Hydro appended to `ecaa_batteries` as fixed
     committed/policy units (same pathway as the four `_pumped_storage_fix`
     facilities, which are deliberately left untouched).

Authored long-duration classes (168 h and 336 h)
------------------------------------------------
The published IASR menu stops at 48 hours, which leaves the modelled fleet
with no low-carbon firming beyond a couple of days. The two authored classes
extend the menu to one and two weeks of storage, and are offered to every
archetype so the cost ladder stays comparable across runs.

Capex is the ONLY authored parameter, and it is extrapolated rather than
assumed: per financial-year column of `new_entrant_build_costs`, a
least-squares line `capex_per_kw = power_cost + reservoir_cost_per_hour *
duration_hours` is fitted across the published 10 h, 24 h and 48 h points and
evaluated at 168 h and 336 h. The intercept is the power-related cost
(turbines, penstock, connection) and the slope the reservoir cost per hour of
storage, so the fit carries physical meaning rather than tracing a curve
through arbitrary points. Fitting per year means the new classes inherit the
published cost trajectory's shape. The published points sit close to a line
(R-squared ~0.977 in every Step Change year); a year whose fit falls below
_FIT_R_SQUARED_FLOOR is logged rather than silently used.

EVERYTHING else is inherited unchanged from the 48-hour class: pumping
(round-trip) efficiency, FOM, total lead time, economic life, locational cost
factors and connection costs. FOM in particular is inherited rather than
scaled, because the published FOM is not monotonic in duration (10 h 96.7385,
24 h 74.84505, 48 h 85.5372) so any duration scaling would be invention.

Shared site limits
------------------
`build_limits_phes` gives a megawatt limit per sub-region per duration class
from the GHD 2025 site assessment. Those limits bound POWER at PHES-suitable
sites, so a 168-hour reservoir is a deeper reservoir at an assessed site, not
an additional site. Each authored class therefore takes its sub-region's
48-hour limit as its `build_limit_mw`, and a per-sub-region `<=` custom
constraint caps the SUM of all new-entrant PHES power in that sub-region at
that same 48-hour limit, so the duration classes compete for one site budget
instead of stacking to several times the assessed potential. A sub-region with
no published 48-hour limit is offered neither authored class.

Sources (IASR 2026 v7.8 Final workbook, parsed to the workbook cache):
  - Candidate set, durations, pumping (round-trip) efficiencies: sheet
    "Storage properties" -> cache `pumped_hydro_new_entrant_properties.csv`
    (76% for 10/24/48h per note 4 "based on information provided by Hydro
    Tasmania"; 80% for BOTN - Cethana - 20h).
  - Build limits (MW per sub-region per duration class): sheet "Build limits -
    PHES" -> cache `build_limits_phes.csv` (GHD 2025 Pumped Hydro Energy
    Storage Parameter Review basis; notes 1-2: limits exclude Snowy 2.0 and
    Borumba, which are modelled as specific projects — so these caps are
    additive with the committed fleet).
  - Locational cost factors: sheet "Technology specific LCFs" -> cache
    `technology_specific_lcfs.csv` (published FINAL multipliers per sub-region
    for the three PHES classes; BOTN - Cethana is published as 100 (%) for TAS
    and Not Applicable elsewhere).
  - Connection costs ($/kW by NEM region): cache `connection_costs_other.csv`.
  - WACC (% by scenario): cache `wacc.csv` (Step Change: 8.5 for all four).
  - Economic life / total lead time (years): cache
    `lead_time_and_project_life.csv` (40 y life; lead 8 y for 10h, 10 y for
    24h/48h/BOTN - Cethana).
  - FOM ($/kW/yr): cache `fixed_opex_new_entrants.csv` (10h 96.7385,
    24h 74.84505, 48h 85.5372, BOTN - Cethana 74.84505).
  - Kidston / Phoenix unit parameters: cache
    `maximum_capacity_existing_committed_anticipated_additional_generators.csv`
    (Kidston 250 MW / 900 MWh, commissioning 2027-01-01, Committed, NQ;
    Phoenix 810 MW / 9,720 MWh, commissioning 2032-07-01, Additional
    policy-supported project, CNSW), `expected_closure_years.csv` (2065 /
    2122), and pumping efficiencies from
    `pumped_hydro_existing_committed_anticipated_additional_properties.csv`
    (Kidston 80%, Phoenix 76%). NOTE the workbook is internally inconsistent
    on Kidston's duration (max-capacity table 900 MWh -> 3.6 h; Storage
    properties sheet 6 h; technology class label 10 h); the max-capacity
    table is used, matching how ECAA battery durations are derived.

The templater's battery-only filter itself is left unchanged. Use the
archetype runner to apply this repair; calling the package builder alone
does not restore these candidates.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from analysis.archetypes._capacity_floor import add_capacity_cap
from analysis.archetypes._pumped_storage_fix import (
    _existing_sub_regions,
    _make_battery_row,
)

log = logging.getLogger(__name__)

# IASR publication year: total lead times are counted from here, so a class
# with a 10-year total lead time is first buildable in FY2035.
_AVAILABILITY_ANCHOR_FY = 2025

# Column labels inside the cached workbook tables.
_NE_PROPS_NAME_COL = "Power Station / Technology"
_LIMIT_COL_PREFIX = "Pumped Hydro Energy Storage (PHES) limits (MW)_"

# The deepest published class, which the two authored classes inherit from.
_PHES_48H_TECH = "Pumped Hydro (48hrs storage)"

# The six new-entrant PHES classes. `props_name` keys the Storage-properties
# table and the build-limit columns; `technology_type` keys build_costs / wacc
# / lead-time / fixed-opex / LCF tables (and is the exact string the
# translator's build-cost merge needs). The two authored classes appear in no
# workbook table, so `inherits_from` redirects every workbook lookup to the
# 48-hour class and `duration_hours` supplies the storage depth directly.
_NE_PHES_CLASSES = [
    {
        "technology_type": "Pumped Hydro (10hrs storage)",
        "props_name": "Pumped Hydro (10hrs storage)",
        "short": "phes_10h",
        "inherits_from": None,
        "duration_hours": None,
    },
    {
        "technology_type": "Pumped Hydro (24hrs storage)",
        "props_name": "Pumped Hydro (24hrs storage)",
        "short": "phes_24h",
        "inherits_from": None,
        "duration_hours": None,
    },
    {
        "technology_type": _PHES_48H_TECH,
        "props_name": _PHES_48H_TECH,
        "short": "phes_48h",
        "inherits_from": None,
        "duration_hours": None,
    },
    {
        "technology_type": "BOTN - Cethana",
        "props_name": "BOTN - Cethana - 20h",
        "short": "botn_cethana_20h",
        "inherits_from": None,
        "duration_hours": None,
    },
    {
        "technology_type": "Pumped Hydro (168hrs storage)",
        "props_name": _PHES_48H_TECH,
        "short": "phes_168h",
        "inherits_from": _PHES_48H_TECH,
        "duration_hours": 168.0,
    },
    {
        "technology_type": "Pumped Hydro (336hrs storage)",
        "props_name": _PHES_48H_TECH,
        "short": "phes_336h",
        "inherits_from": _PHES_48H_TECH,
        "duration_hours": 336.0,
    },
]

_EXTRAPOLATED_CLASSES = [c for c in _NE_PHES_CLASSES if c["inherits_from"]]

# FOM $/kW/yr from fixed_opex_new_entrants.csv (base value column). The
# authored classes read the 48-hour entry via `_workbook_tech`.
_NE_PHES_FOM = {
    "Pumped Hydro (10hrs storage)": 96.7385,
    "Pumped Hydro (24hrs storage)": 74.84505,
    _PHES_48H_TECH: 85.5372,
    "BOTN - Cethana": 74.84505,
}

# Published (duration, capex) anchors for the capex-versus-duration fit.
_PUBLISHED_FIT_DURATIONS = {
    "Pumped Hydro (10hrs storage)": 10.0,
    "Pumped Hydro (24hrs storage)": 24.0,
    _PHES_48H_TECH: 48.0,
}

# The fitted coefficients for this financial year (FY2050) are logged so the
# authored capex is auditable without re-running the fit.
_FIT_AUDIT_COLUMN = "2049_50_$/mw"

# Below this the published points are too far from a line for the fit to be
# trustworthy, and the run says so rather than extrapolating silently.
_FIT_R_SQUARED_FLOOR = 0.95

# Fixed committed / policy PHES units dropped by the templater and not in
# _pumped_storage_fix's four-facility list. Parameter sources in module
# docstring. round_trip_efficiency_% is the workbook's "Pumping efficiency".
_ECAA_PHES_SPECS = [
    {
        "storage_name": "Kidston",
        "sub_region_id": "NQ",
        "region_id": "QLD",
        "rez_id": np.nan,
        "maximum_capacity_mw": 250.0,
        "storage_duration_hours": 3.6,  # 900 MWh / 250 MW (max-capacity table)
        "round_trip_efficiency_%": 80.0,
        "status": "Committed",
        "commissioning_date": "2027-01-01",
        "closure_year": 2065,
    },
    {
        "storage_name": "Phoenix Pumped Hydro Project",
        "sub_region_id": "CNSW",
        "region_id": "NSW",
        "rez_id": np.nan,
        "maximum_capacity_mw": 810.0,
        "storage_duration_hours": 12.0,  # 9,720 MWh / 810 MW
        "round_trip_efficiency_%": 76.0,
        "status": "Additional policy-supported project",
        "commissioning_date": "2032-07-01",
        "closure_year": 2122,
    },
]


def apply(ispypsa_tables: dict, config=None) -> dict:
    """Append workbook PHES new-entrant candidates and the two dropped
    committed units. Needs a config carrying the workbook cache path, the
    scenario and a single (myopic) investment period; otherwise the menu is
    NOT offered and a warning says so — the production myopic chain always
    satisfies all three."""
    cache_path = getattr(getattr(config, "paths", None), "parsed_workbook_cache", None)
    if cache_path is None:
        log.warning(
            "phes_menu: config carries no parsed_workbook_cache — PHES menu "
            "NOT offered (battery-only new-entrant storage, pre-repair "
            "behaviour)."
        )
        return ispypsa_tables
    periods = list(config.temporal.capacity_expansion.investment_periods)
    if len(periods) != 1:
        log.warning(
            f"phes_menu: multi-period run (investment_periods={periods}) — "
            "PHES lead-time gating is only implemented for single-period "
            "(myopic) runs, so the PHES menu is NOT offered here."
        )
        return ispypsa_tables
    source = _read_phes_source_tables(Path(cache_path))
    candidates = _build_new_entrant_phes_candidates(source, config.scenario, periods[0])
    available_sub_regions = _existing_sub_regions(ispypsa_tables)
    if not candidates.empty:
        candidates = candidates[
            candidates["sub_region_id"].isin(available_sub_regions)
        ].reset_index(drop=True)
    offered = (
        sorted(candidates["storage_name"].tolist()) if not candidates.empty else []
    )
    log.info(
        f"phes_menu: new-entrant PHES candidates offered at {periods[0]}: {offered}"
    )
    ispypsa_tables["new_entrant_batteries"] = _append_candidates(
        ispypsa_tables.get("new_entrant_batteries"), candidates
    )
    ispypsa_tables["new_entrant_build_costs"] = _append_extrapolated_build_costs(
        ispypsa_tables["new_entrant_build_costs"]
    )
    ispypsa_tables["ecaa_batteries"] = _append_ecaa_phes(
        ispypsa_tables.get("ecaa_batteries"), available_sub_regions
    )
    return _add_shared_site_constraints(
        ispypsa_tables, source, config, available_sub_regions
    )


def _read_phes_source_tables(cache: Path) -> dict[str, pd.DataFrame]:
    """Load the cached workbook tables the PHES menu is built from.

    Fails loud when a table is missing — a silent skip would quietly restore
    the truncated menu this pre-pass exists to repair."""
    names = [
        "pumped_hydro_new_entrant_properties",
        "build_limits_phes",
        "technology_specific_lcfs",
        "connection_costs_other",
        "wacc",
        "lead_time_and_project_life",
    ]
    tables = {}
    for name in names:
        path = cache / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"PHES menu source table missing from workbook cache: {path}. "
                "Re-build the cache with the PHES tables in REQUIRED_TABLES "
                "(ispypsa.iasr_table_caching.local_cache)."
            )
        tables[name] = pd.read_csv(path)
    return tables


def _build_new_entrant_phes_candidates(
    source: dict[str, pd.DataFrame], scenario: str, period: int
) -> pd.DataFrame:
    """One candidate row per (available class x sub-region with a non-zero
    workbook build limit), in new_entrant_batteries column shape plus
    `build_limit_mw`."""
    rows = []
    for phes_class in _NE_PHES_CLASSES:
        tech = phes_class["technology_type"]
        lead_time = _lead_time_years(source, _workbook_tech(phes_class))
        earliest_fy = _AVAILABILITY_ANCHOR_FY + lead_time
        if period < earliest_fy:
            log.info(
                f"phes_menu: {tech} unavailable at {period} "
                f"(earliest build FY {earliest_fy:.0f} from IASR total lead time)"
            )
            continue
        duration, rte = _class_properties(source, phes_class)
        limit_column = _limit_column(source, phes_class["props_name"])
        for _, limit_row in source["build_limits_phes"].iterrows():
            limit_mw = float(limit_row[limit_column])
            if limit_mw <= 0:
                continue
            rows.append(
                _make_candidate_row(
                    source, phes_class, limit_row, limit_mw, duration, rte, scenario
                )
            )
    return pd.DataFrame(rows)


def _workbook_tech(phes_class: dict) -> str:
    """Technology key this class reads the workbook tables under.

    The authored long-duration classes appear in no published table, so every
    lookup but capex is redirected to the class they inherit from."""
    return phes_class["inherits_from"] or phes_class["technology_type"]


def _limit_column(source: dict[str, pd.DataFrame], props_name: str) -> str:
    """Resolve the build-limit column for a class (limit columns are keyed by
    the Storage-properties name, e.g. '..._BOTN - Cethana - 20h')."""
    for col in source["build_limits_phes"].columns:
        if col.startswith(_LIMIT_COL_PREFIX) and props_name in col:
            return col
    raise KeyError(f"No build-limit column for {props_name} in build_limits_phes")


def _class_properties(
    source: dict[str, pd.DataFrame], phes_class: dict
) -> tuple[float, float]:
    """(storage hours, round-trip efficiency %) for a class.

    The authored classes carry their own storage depth and take the pumping
    efficiency of the class they inherit from."""
    props = source["pumped_hydro_new_entrant_properties"].set_index(_NE_PROPS_NAME_COL)
    row = props.loc[phes_class["props_name"]]
    published_hours = float(row["Storage capacity (hours)"])
    duration = phes_class["duration_hours"] or published_hours
    return duration, float(row["Pumping efficiency (%)"])


def _lead_time_years(source: dict[str, pd.DataFrame], tech: str) -> float:
    table = source["lead_time_and_project_life"].set_index("Technology")
    return float(table.loc[tech, "Total lead time (years)"])


def _economic_life_years(source: dict[str, pd.DataFrame], tech: str) -> float:
    table = source["lead_time_and_project_life"].set_index("Technology")
    life = float(table.loc[tech, "Economic life (years)"])
    if not np.isfinite(life):
        raise ValueError(f"No economic life for {tech} in lead_time_and_project_life")
    return life


def _wacc_fraction(source: dict[str, pd.DataFrame], tech: str, scenario: str) -> float:
    table = source["wacc"].set_index("Technology type")
    return float(table.loc[tech, scenario]) / 100.0


def _lcf_percent(source: dict[str, pd.DataFrame], tech: str, sub_region: str) -> float:
    """Published final LCF for (tech, sub-region), as a percentage.

    The workbook publishes the three PHES classes as multipliers (~1.0) and
    BOTN - Cethana as 100 (%) for TAS only."""
    if tech == "BOTN - Cethana":
        return 100.0
    lcfs = source["technology_specific_lcfs"].set_index("Cost zone / REZ ID")
    return float(lcfs.loc[sub_region, tech]) * 100.0


def _connection_cost_per_mw(
    source: dict[str, pd.DataFrame], tech: str, region: str
) -> float:
    """Region-level connection cost, $/kW in the workbook -> $/MW.

    BOTN - Cethana has no connection-cost column; AEMO publishes it as a
    project with no separate connection cost entry -> the 48hr PHES value for
    its region is NOT substituted; 0.0 is used and disclosed here (the
    project-level build cost is taken as all-in)."""
    table = source["connection_costs_other"].set_index("Region")
    col = tech if tech in table.columns else None
    if col is None:
        if tech == "BOTN - Cethana":
            return 0.0
        raise KeyError(f"No connection-cost column for {tech}")
    return float(table.loc[region, col]) * 1000.0


def _make_candidate_row(
    source: dict[str, pd.DataFrame],
    phes_class: dict,
    limit_row: pd.Series,
    limit_mw: float,
    duration: float,
    rte: float,
    scenario: str,
) -> dict:
    workbook_tech = _workbook_tech(phes_class)
    sub_region = limit_row["ISP Sub-region"]
    region = limit_row["Region"]
    per_direction_eff = 100.0 * (rte / 100.0) ** 0.5
    return {
        "storage_name": f"{phes_class['short']}_{sub_region.lower()}",
        "isp_resource_type": f"Pumped Hydro {duration:.0f}h",
        "technology_type": phes_class["technology_type"],
        "status": "New Entrant",
        "region_id": region,
        "sub_region_id": sub_region,
        "rez_id": np.nan,
        "fuel_type": "Water",
        "fom_$/kw/annum": _NE_PHES_FOM[workbook_tech],
        "connection_cost_$/mw": _connection_cost_per_mw(source, workbook_tech, region),
        "technology_specific_lcf_%": _lcf_percent(source, workbook_tech, sub_region),
        "maximum_capacity_mw": np.nan,
        "storage_duration_hours": duration,
        "lifetime": _economic_life_years(source, workbook_tech),
        "round_trip_efficiency_%": rte,
        "charging_efficiency_%": per_direction_eff,
        "discharging_efficiency_%": per_direction_eff,
        "wacc": _wacc_fraction(source, workbook_tech, scenario),
        "build_limit_mw": limit_mw,
    }


def _append_candidates(
    new_entrant_batteries: pd.DataFrame | None, candidates: pd.DataFrame
) -> pd.DataFrame:
    """Append PHES candidates; existing battery rows are untouched (they gain
    a `build_limit_mw` column holding NaN, which the translator maps to an
    infinite p_nom_max)."""
    if candidates.empty:
        return (
            new_entrant_batteries
            if new_entrant_batteries is not None
            else pd.DataFrame()
        )
    if new_entrant_batteries is None or new_entrant_batteries.empty:
        return candidates
    return pd.concat(
        [new_entrant_batteries, candidates], axis=0, ignore_index=True, sort=False
    )


def _append_extrapolated_build_costs(build_costs: pd.DataFrame) -> pd.DataFrame:
    """Append one `new_entrant_build_costs` row per authored long-duration
    class, fitted across the published 10/24/48-hour capex in each
    financial-year column."""
    year_columns = [col for col in build_costs.columns if col != "technology"]
    published = build_costs.set_index("technology").loc[list(_PUBLISHED_FIT_DURATIONS)]
    fits = {col: _fit_capex_against_duration(published[col]) for col in year_columns}
    _log_capex_extrapolation(fits)
    rows = [
        _extrapolated_cost_row(phes_class, fits, year_columns)
        for phes_class in _EXTRAPOLATED_CLASSES
    ]
    return pd.concat([build_costs, pd.DataFrame(rows)], ignore_index=True)


def _fit_capex_against_duration(capex: pd.Series) -> tuple[float, float, float]:
    """Least-squares fit of capex against storage duration for one financial
    year: (power cost, reservoir cost per storage hour, R-squared).

    The intercept is the power-related cost (turbines, penstock, connection)
    and the slope the reservoir cost per hour of storage."""
    durations = np.array([_PUBLISHED_FIT_DURATIONS[tech] for tech in capex.index])
    values = capex.to_numpy(dtype=float)
    reservoir_cost, power_cost = np.polyfit(durations, values, 1)
    residual = ((values - (power_cost + reservoir_cost * durations)) ** 2).sum()
    total = ((values - values.mean()) ** 2).sum()
    return float(power_cost), float(reservoir_cost), float(1.0 - residual / total)


def _extrapolated_cost_row(
    phes_class: dict,
    fits: dict[str, tuple[float, float, float]],
    year_columns: list[str],
) -> dict:
    """One build-cost row: the fitted line evaluated at this class's duration
    in every financial-year column."""
    hours = phes_class["duration_hours"]
    row = {"technology": phes_class["technology_type"]}
    row.update({col: fits[col][0] + fits[col][1] * hours for col in year_columns})
    return row


def _log_capex_extrapolation(fits: dict[str, tuple[float, float, float]]) -> None:
    """Disclose the authored capex and its fitted coefficients, plus any
    financial year whose published points are too far from a line."""
    # The fit runs on the templated $/MW table; the log reports $/kW so the
    # coefficients can be read against the workbook's published capex.
    power_cost, reservoir_cost, _ = fits[_FIT_AUDIT_COLUMN]
    classes = sorted(c["technology_type"] for c in _EXTRAPOLATED_CLASSES)
    log.warning(
        f"phes_menu: capex for {classes} is extrapolated beyond the published "
        f"10-48 h duration range by a per-financial-year least-squares fit of "
        f"capex against duration; FY2050 power cost {power_cost / 1000.0:.1f} "
        f"$/kW, reservoir cost {reservoir_cost / 1000.0:.2f} $/kW per storage hour"
    )
    poor = sorted(col for col, fit in fits.items() if fit[2] < _FIT_R_SQUARED_FLOOR)
    if poor:
        log.warning(
            f"phes_menu: published 10/24/48 h capex is not linear in duration "
            f"(R-squared below {_FIT_R_SQUARED_FLOOR}) in financial years "
            f"{poor}; the extrapolated 168/336 h capex is less reliable there"
        )


def _add_shared_site_constraints(
    ispypsa_tables: dict,
    source: dict[str, pd.DataFrame],
    config,
    available_sub_regions: set[str],
) -> dict:
    """Cap total new-entrant PHES power per sub-region at its 48-hour limit.

    The GHD limits bound power at PHES-suitable sites, so the duration classes
    are competing reservoir depths at one site budget rather than separate
    sites. Committed PHES is not netted off: the workbook's notes 1-2 state the
    limits exclude Snowy 2.0 and Borumba, so they are additive with the
    committed fleet."""
    period = list(config.temporal.capacity_expansion.investment_periods)[0]
    limit_column = _limit_column(source, _PHES_48H_TECH)
    for _, limit_row in source["build_limits_phes"].iterrows():
        sub_region = limit_row["ISP Sub-region"]
        limit_mw = float(limit_row[limit_column])
        if limit_mw <= 0 or sub_region not in available_sub_regions:
            continue
        ispypsa_tables = _add_one_site_constraint(
            ispypsa_tables, config, sub_region, limit_mw, period
        )
    return ispypsa_tables


def _add_one_site_constraint(
    ispypsa_tables: dict, config, sub_region: str, limit_mw: float, period: int
) -> dict:
    """One '<=' constraint summing every new-entrant PHES p_nom in one
    sub-region."""
    return add_capacity_cap(
        ispypsa_tables,
        config,
        constraint_prefix=f"phes_site_limit_{sub_region.lower()}",
        caps_by_year={period: limit_mw},
        new_entrant_table="new_entrant_batteries",
        new_entrant_id_col="storage_name",
        new_entrant_predicate=lambda row: (
            row.get("fuel_type") == "Water" and row.get("sub_region_id") == sub_region
        ),
        existing_table=None,
        existing_predicate=None,
        term_type="storage_capacity",
    )


def _append_ecaa_phes(
    ecaa_batteries: pd.DataFrame | None, available_sub_regions: set[str]
) -> pd.DataFrame:
    """Append Kidston and Phoenix as fixed units via the same row builder as
    the four `_pumped_storage_fix` facilities."""
    specs_in_scope = [
        spec
        for spec in _ECAA_PHES_SPECS
        if spec["sub_region_id"] in available_sub_regions
    ]
    added = sorted(spec["storage_name"] for spec in specs_in_scope)
    log.info(f"phes_menu: added to ecaa_batteries: {added}")
    if not specs_in_scope:
        return ecaa_batteries if ecaa_batteries is not None else pd.DataFrame()
    new_rows = pd.DataFrame([_make_battery_row(spec) for spec in specs_in_scope])
    if ecaa_batteries is None or ecaa_batteries.empty:
        return new_rows
    return pd.concat([ecaa_batteries, new_rows], axis=0, ignore_index=True, sort=False)
