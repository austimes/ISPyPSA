"""Reshape cached IASR 7.x workbook tables into the canonical (v7.4-named) form the templater reads.

Each function rewrites CSVs in the cache folder in place and is a no-op when its table is absent.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_V74_TO_CANONICAL_COLUMN_RENAMES: dict[str, dict[str, str]] = {
    "lead_time_and_project_life": {
        # v7.4 appended a "4," footnote text to this column header.
        "Total lead time (years)4,": "Total lead time (years)",
    },
    "variable_opex_existing_committed_anticipated_additional_generators": {
        # The 7.5 and 7.8 workbooks append a "1," footnote text to this column header.
        "Variable OPEX ($/MWh sent out)1,": "Variable OPEX ($/MWh sent out)",
    },
    # v7.4 connection_costs_other uses inconsistent casing for battery tech
    # column headers ("Battery storage" lowercase for 1-4hrs, "Battery Storage"
    # capital S for 8hrs). new_entrants_summary uses capital S consistently in
    # `Connection cost_Technology` values. Standardise the column headers to
    # capital S so post-melt key alignment is clean.
    "connection_costs_other": {
        "Battery storage (1hr storage)": "Battery Storage (1hr storage)",
        "Battery storage (2hrs storage)": "Battery Storage (2hrs storage)",
        "Battery storage (4hrs storage)": "Battery Storage (4hrs storage)",
    },
    # v7.4 splits gas_prices into per-status tables with different first
    # column headers (`Generator` for existing, `New generating stations`
    # for new entrants). Templater concats them and expects a single
    # identifier column.
    "gas_prices_new_entrants": {
        "New generating stations": "Generator",
    },
}


_V74_MAX_CAPACITY_CONSOLIDATED = (
    "maximum_capacity_existing_committed_anticipated_additional_generators"
)


def split_v74_maximum_capacity_commissioning_dates(cache_path: Path) -> None:
    """Split v7.4's single `Commissioning date` column into the two-column
    layout the templater downstream expects.

    The workbook publishes one `Commissioning date` column and uses `Status`
    to tell confirmed dates from indicative ones. The templater reads separate
    `Commissioning date` (confirmed, committed rows) and `Indicative
    commissioning date` (anticipated/additional rows) columns, so for rows
    with `Status in {Anticipated, Additional}` the date moves into
    `Indicative commissioning date`. No-op if the table is absent.
    """
    csv_path = cache_path / f"{_V74_MAX_CAPACITY_CONSOLIDATED}.csv"
    if not csv_path.exists():
        return
    df = pd.read_csv(csv_path)
    df["Indicative commissioning date"] = pd.NA
    indicative_mask = df["Status"].isin(["Anticipated", "Additional"])
    df.loc[indicative_mask, "Indicative commissioning date"] = df.loc[
        indicative_mask, "Commissioning date"
    ]
    df.loc[indicative_mask, "Commissioning date"] = pd.NA
    df.to_csv(csv_path, index=False)


_V74_OTHER_OUTAGES_SINGLE_YEAR_COLUMN = "2025-26"


def pivot_v74_other_outages_to_wide(cache_path: Path) -> None:
    """Generate the templater-expected forms from v7.4's long-form
    `other_outages_existing_generators` (rows keyed by Fuel type + Property,
    year columns 2025-26 through 2034-35).

    Produces:
    - `other_outages_existing_generators.csv`: pivoted wide form, one row
      per Fuel type with per-Property columns (single year value, 2025-26).
      Used by static generator-property merges (Partial Outage Derating
      Factor, MTTR full/partial).
    - `full_outages_forecast_existing_generators.csv`: time-series of
      "Full outage (% of time)" per Fuel type × year. Used by dynamic
      generator-property templater.
    - `partial_outages_forecast_existing_generators.csv`: time-series of
      "Partial outage (% of time)" per Fuel type × year.

    The dynamic templater uses the outage time series; the static templater
    uses the single representative year (2025-26) because the PyPSA inputs
    take one outage value per generator.

    No-op if the long-form file is missing.
    """
    path = cache_path / "other_outages_existing_generators.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    year_cols = [c for c in df.columns if c not in ("Fuel type", "Property")]
    # Time-series forecasts per Property.
    for property_value, target_name in [
        ("Full outage (% of time)", "full_outages_forecast_existing_generators"),
        ("Partial outage (% of time)", "partial_outages_forecast_existing_generators"),
    ]:
        subset = df[df["Property"] == property_value].drop(columns="Property")
        subset.to_csv(cache_path / f"{target_name}.csv", index=False)
    # Wide static form (single representative year per Property).
    wide = df.pivot_table(
        index="Fuel type",
        columns="Property",
        values=_V74_OTHER_OUTAGES_SINGLE_YEAR_COLUMN,
        aggfunc="first",
    ).reset_index()
    wide.columns.name = None
    wide.to_csv(path, index=False)


def aggregate_v74_liquid_fuel_prices_to_v60_form(cache_path: Path) -> None:
    """v7.4 split `liquid_fuel_prices` into per-generator rows (Generator,
    Gas price scenario, year cols), differentiating prices by location.
    The templater consumes a single representative price per scenario, so
    average across the Generator dimension (mean per scenario+year) and rename
    the columns to the names the templater reads. Liquid-fuel capacity in the
    NEM is small, so a fleet-average price is a reasonable proxy for
    per-generator prices.

    No-op if the file is absent.
    """
    path = cache_path / "liquid_fuel_prices.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    year_cols = [c for c in df.columns if c not in ("Generator", "Gas price scenario")]
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
    aggregated = df.groupby("Gas price scenario", as_index=False)[year_cols].mean()
    aggregated.insert(0, "Liquid fuel price", "Liquid fuel")
    aggregated = aggregated.rename(
        columns={"Gas price scenario": "Liquid fuel price scenario"}
    )
    aggregated.to_csv(path, index=False)


def aggregate_v74_biomethane_prices_to_v60_form(cache_path: Path) -> None:
    """v7.4 publishes biomethane prices per-source (Landfill gas, Waste, Crop
    residue) × scenario. The templater expects one row per scenario, so
    average across sources per scenario+year. As for liquid fuel, the
    source-average price stands in for per-source biomethane prices.

    No-op if the table is absent.
    """
    path = cache_path / "biomethane_prices.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    year_cols = [
        c
        for c in df.columns
        if c not in ("Biomethane price", "Biomethane price scenario")
    ]
    df[year_cols] = df[year_cols].apply(pd.to_numeric, errors="coerce")
    aggregated = df.groupby("Biomethane price scenario", as_index=False)[
        year_cols
    ].mean()
    aggregated.insert(0, "Biomethane price", "Biomethane (mean across sources)")
    aggregated.to_csv(path, index=False)


def drop_v78_not_applicable_build_cost_year(cache_path: Path) -> None:
    """Drop fully-"Not Applicable" financial-year columns from `build_costs`.

    The 2026 ISP FINAL (v7.8) workbook prepended a `2024-25` build-cost column
    to the "Build costs" sheet whose every cell reads the string
    "Not Applicable" (AEMO's first published GenCost year is 2025-26). The
    templater's `_template_new_entrant_build_costs` multiplies the whole
    year-column block by 1000 (`build_costs *= 1000.0`) to convert $/kW to
    $/MW, which raises `TypeError: can't multiply sequence by non-int` on the
    string column.

    The column carries no data the model uses — every investment period is
    2025-26 or later — so dropping the all-"Not Applicable" FY column at cache
    load is lossless.
    """
    import re

    fy_pattern = re.compile(r"^\d{4}-\d{2}$")
    csv_path = cache_path / "build_costs.csv"
    if not csv_path.exists():
        return
    df = pd.read_csv(csv_path)
    fy_cols = [c for c in df.columns if fy_pattern.match(str(c))]
    all_not_applicable = [
        c for c in fy_cols if (df[c].astype(str) == "Not Applicable").all()
    ]
    df = df.drop(columns=all_not_applicable)
    df.to_csv(csv_path, index=False)


def strip_v74_rez_prefix_from_aug_cost_options(cache_path: Path) -> None:
    """v7.4 publishes `rez_augmentation_costs_*` tables with Option values
    prefixed by the REZ ID (e.g. `"DN1 Option 1"`); the corresponding
    `rez_augmentation_options_*` tables use the bare suffix (`"Option 1"`).
    The templater merges aug options + costs on `(id, option)` and the
    mismatch silently drops nearly all rows — leaving `rez_transmission_expansion_costs`
    empty, which means PyPSA links from REZs to sub-regions become
    non-extendable. VRE build is then capped at the existing REZ
    transmission limits and the LP fills load-bus capacity gaps with
    biomass instead.

    Strip the leading `"{REZ ID} "` from Option values in v7.4 cost tables
    so the merge with the options table succeeds. The aug_options tables
    are left untouched.

    No-op if cost files are absent or already in stripped form.
    """
    for csv_path in cache_path.glob("rez_augmentation_costs_*.csv"):
        df = pd.read_csv(csv_path)
        rez_col = "REZ / Constraint ID" if "REZ / Constraint ID" in df.columns else None
        if rez_col is None or "Option" not in df.columns:
            continue
        has_prefix = df.apply(
            lambda r: (
                isinstance(r["Option"], str)
                and isinstance(r[rez_col], str)
                and r["Option"].startswith(r[rez_col] + " ")
            ),
            axis=1,
        )
        if not has_prefix.any():
            continue
        df.loc[has_prefix, "Option"] = df.loc[has_prefix].apply(
            lambda r: r["Option"][len(r[rez_col]) + 1 :],
            axis=1,
        )
        df.to_csv(csv_path, index=False)


def merge_v74_connection_capacity_into_forecast(cache_path: Path) -> None:
    """v7.4 publishes per-REZ `Connection capacity (MVA)` only in
    `connection_costs_for_wind_and_solar.csv`; the forecast table itself
    carries just year-column values in $. The templater needs MVA inline
    on the forecast table to compute $/MW. Merge it here so the templater
    sees the same shape regardless of source version.

    No-op if either source file is absent.
    """
    forecast_path = cache_path / "connection_cost_forecast_wind_and_solar.csv"
    initial_path = cache_path / "connection_costs_for_wind_and_solar.csv"
    if not forecast_path.exists() or not initial_path.exists():
        return
    forecast = pd.read_csv(forecast_path)
    initial = pd.read_csv(initial_path)
    capacity = initial[["REZ names", "Connection capacity (MVA)"]].drop_duplicates(
        subset=["REZ names"]
    )
    merged = forecast.merge(capacity, on="REZ names", how="left")
    leading = ["REZ names", "Scenario", "Connection capacity (MVA)"]
    other = [c for c in merged.columns if c not in leading]
    merged = merged[[c for c in leading if c in merged.columns] + other]
    merged.to_csv(forecast_path, index=False)


# v7.4 ECAA tables that publish one row per generating unit (IASR ID), which
# downstream templater code expects to see at per-power-station granularity
# (one row per Power Station). Aggregation strategy:
#   summary table:          first values per Power Station (unit properties
#                           are identical across all units of the same plant)
#   maximum_capacity table: sum `Installed capacity (MW)` across units, first
#                           values for other columns
#   property tables (heat_rates, fixed_opex, variable_opex, auxiliary_load,
#                    marginal_loss_factors, seasonal_ratings): first values
_V74_ECAA_PER_UNIT_TABLES_FIRST_AGG = [
    "existing_committed_anticipated_additional_generator_summary",
    "heat_rates_existing_committed_anticipated_additional_generators",
    "fixed_opex_existing_committed_anticipated_additional_generators",
    "variable_opex_existing_committed_anticipated_additional_generators",
    "auxiliary_load_existing_committed_anticipated_additional_generators",
    "marginal_loss_factors_existing_generators",
    "seasonal_ratings_existing_committed_anticipated_additional_generators",
]


def aggregate_v74_ecaa_units_to_power_stations(cache_path: Path) -> None:
    """Collapse v7.4 per-unit ECAA rows to per-Power-Station.

    The workbook publishes one row per generating unit (IASR ID = e.g. BW01,
    BW02, BW03, BW04 for Bayswater units 1–4), with property values typically identical
    across all units of the same plant. The templater downstream is built
    around the per-plant convention — duplicate "generator" identifiers
    (snake_cased Power Station) propagate through to PyPSA and break the
    network build.

    This function collapses the tables to per-plant granularity: groupby
    Power Station and take first values for properties, summing
    only `Installed capacity (MW)` in the max_capacity table where total
    plant capacity is the meaningful figure. Each unit's capacity is first
    copied into `expected_closure_years`, which stays per unit.

    No-op if the table is missing or already per-plant.
    """
    for table_name in _V74_ECAA_PER_UNIT_TABLES_FIRST_AGG:
        csv_path = cache_path / f"{table_name}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        if "Power Station" not in df.columns:
            continue
        if df["Power Station"].duplicated().sum() == 0:
            continue
        df = _aggregate_first_by_power_station(df)
        df.to_csv(csv_path, index=False)

    cap_path = (
        cache_path
        / "maximum_capacity_existing_committed_anticipated_additional_generators.csv"
    )
    if cap_path.exists():
        df = pd.read_csv(cap_path)
        if "Power Station" in df.columns and df["Power Station"].duplicated().sum() > 0:
            _add_unit_capacity_to_closure_years(cache_path, df)
            df = _aggregate_capacity_by_power_station(df)
            df.to_csv(cap_path, index=False)


def _add_unit_capacity_to_closure_years(cache_path: Path, units: pd.DataFrame) -> None:
    """Add each unit's `Installed capacity (MW)` to `expected_closure_years`, so the
    templater can retire a station's capacity unit by unit.
    """
    closure_path = cache_path / "expected_closure_years.csv"
    closures = pd.read_csv(closure_path)
    capacity = units.set_index("IASR ID")["Installed capacity (MW)"]
    closures["Installed capacity (MW)"] = closures["IASR ID"].map(capacity)
    closures.to_csv(closure_path, index=False)


def _aggregate_first_by_power_station(df: pd.DataFrame) -> pd.DataFrame:
    other_cols = [c for c in df.columns if c != "Power Station"]
    aggregated = df.groupby("Power Station", as_index=False, sort=False)[
        other_cols
    ].first()
    return aggregated[list(df.columns)]


def _aggregate_capacity_by_power_station(df: pd.DataFrame) -> pd.DataFrame:
    sum_cols = [c for c in ("Installed capacity (MW)",) if c in df.columns]
    first_cols = [c for c in df.columns if c not in sum_cols + ["Power Station"]]
    agg_spec = {c: "first" for c in first_cols}
    agg_spec.update({c: "sum" for c in sum_cols})
    aggregated = df.groupby("Power Station", as_index=False, sort=False).agg(agg_spec)
    return aggregated[list(df.columns)]
