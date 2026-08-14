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
  2. Workbook build limits applied per candidate via a new `build_limit_mw`
     column, which the translator maps to PyPSA `p_nom_max`.
  3. IASR total lead times gate availability: a candidate is only offered in
     investment periods >= _AVAILABILITY_ANCHOR_FY + total lead time.
  4. Kidston and Phoenix Pumped Hydro appended to `ecaa_batteries` as fixed
     committed/policy units (same pathway as the four `_pumped_storage_fix`
     facilities, which are deliberately left untouched).

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

The templater's battery-only filter itself is left unchanged: the upstream
defect (PHES dropped for every ISPyPSA user) stands and is documented in
analysis/calibration/STORAGE_AUDIT_GAS_COMPOSITION.md §0.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

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

# The four new-entrant PHES classes. `props_name` keys the Storage-properties
# table; `technology_type` keys build_costs / wacc / lead-time / fixed-opex /
# LCF tables (and is the exact string the translator's build-cost merge needs).
_NE_PHES_CLASSES = [
    {"technology_type": "Pumped Hydro (10hrs storage)", "props_name": "Pumped Hydro (10hrs storage)", "short": "phes_10h"},
    {"technology_type": "Pumped Hydro (24hrs storage)", "props_name": "Pumped Hydro (24hrs storage)", "short": "phes_24h"},
    {"technology_type": "Pumped Hydro (48hrs storage)", "props_name": "Pumped Hydro (48hrs storage)", "short": "phes_48h"},
    {"technology_type": "BOTN - Cethana", "props_name": "BOTN - Cethana - 20h", "short": "botn_cethana_20h"},
]

# FOM $/kW/yr from fixed_opex_new_entrants.csv (base value column).
_NE_PHES_FOM = {
    "Pumped Hydro (10hrs storage)": 96.7385,
    "Pumped Hydro (24hrs storage)": 74.84505,
    "Pumped Hydro (48hrs storage)": 85.5372,
    "BOTN - Cethana": 74.84505,
}

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
    cache_path = getattr(
        getattr(config, "paths", None), "parsed_workbook_cache", None
    )
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
    candidates = _build_new_entrant_phes_candidates(
        source, config.scenario, periods[0]
    )
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
    ispypsa_tables["ecaa_batteries"] = _append_ecaa_phes(
        ispypsa_tables.get("ecaa_batteries"), available_sub_regions
    )
    return ispypsa_tables


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
        earliest_fy = _AVAILABILITY_ANCHOR_FY + _lead_time_years(source, tech)
        if period < earliest_fy:
            log.info(
                f"phes_menu: {tech} unavailable at {period} "
                f"(earliest build FY {earliest_fy:.0f} from IASR total lead time)"
            )
            continue
        duration, rte = _class_properties(source, phes_class["props_name"])
        limit_column = _limit_column(source, phes_class)
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


def _limit_column(source: dict[str, pd.DataFrame], phes_class: dict) -> str:
    """Resolve the build-limit column for a class (limit columns are keyed by
    the Storage-properties name, e.g. '..._BOTN - Cethana - 20h')."""
    for col in source["build_limits_phes"].columns:
        if col.startswith(_LIMIT_COL_PREFIX) and phes_class["props_name"] in col:
            return col
    raise KeyError(
        f"No build-limit column for {phes_class['props_name']} in build_limits_phes"
    )


def _class_properties(
    source: dict[str, pd.DataFrame], props_name: str
) -> tuple[float, float]:
    """(storage hours, round-trip efficiency %) from the workbook's
    new-entrant PHES properties table."""
    props = source["pumped_hydro_new_entrant_properties"].set_index(
        _NE_PROPS_NAME_COL
    )
    row = props.loc[props_name]
    return float(row["Storage capacity (hours)"]), float(
        row["Pumping efficiency (%)"]
    )


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
    tech = phes_class["technology_type"]
    sub_region = limit_row["ISP Sub-region"]
    region = limit_row["Region"]
    per_direction_eff = 100.0 * (rte / 100.0) ** 0.5
    return {
        "storage_name": f"{phes_class['short']}_{sub_region.lower()}",
        "isp_resource_type": f"Pumped Hydro {duration:.0f}h",
        "technology_type": tech,
        "status": "New Entrant",
        "region_id": region,
        "sub_region_id": sub_region,
        "rez_id": np.nan,
        "fuel_type": "Water",
        "fom_$/kw/annum": _NE_PHES_FOM[tech],
        "connection_cost_$/mw": _connection_cost_per_mw(source, tech, region),
        "technology_specific_lcf_%": _lcf_percent(source, tech, sub_region),
        "maximum_capacity_mw": np.nan,
        "storage_duration_hours": duration,
        "lifetime": _economic_life_years(source, tech),
        "round_trip_efficiency_%": rte,
        "charging_efficiency_%": per_direction_eff,
        "discharging_efficiency_%": per_direction_eff,
        "wacc": _wacc_fraction(source, tech, scenario),
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
    return pd.concat(
        [ecaa_batteries, new_rows], axis=0, ignore_index=True, sort=False
    )
