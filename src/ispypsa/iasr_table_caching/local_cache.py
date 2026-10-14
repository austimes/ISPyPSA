from pathlib import Path

import pandas as pd
from isp_workbook_parser import Parser

from ..feature_flags import FEATURE_FLAGS
from ..templater.mappings import (
    _FLOW_PATH_AGUMENTATION_TABLES,
    _FLOW_PATH_AUGMENTATION_COST_TABLES,
    _REZ_AUGMENTATION_COST_TABLES,
    _REZ_CONNECTION_AGUMENTATION_TABLES,
)


def _build_required_tables() -> list[str]:
    """Return the list of IASR 7.8 table names to extract from the workbook.

    The `use_new_table_format` feature flag still gates the minimal-template path
    (network geography + transmission only) used by ongoing upstream refactors.
    """
    if FEATURE_FLAGS["use_new_table_format"]:
        _NETWORK_REQUIRED_TABLES = [
            "sub_regional_reference_nodes",
            "renewable_energy_zones",
            "flow_path_transfer_capability",
            "initial_transmission_limits",
        ]
        return _NETWORK_REQUIRED_TABLES
    else:
        # Per-property generator and storage tables. The four ECAA statuses share one
        # `existing_committed_anticipated_additional_generators` table per property;
        # some properties still split existing from new entrants.
        _GENERATOR_PROPERTY_TABLES = [
            "maximum_capacity_existing_committed_anticipated_additional_generators",
            "maximum_capacity_new_entrants",
            "seasonal_ratings_existing_committed_anticipated_additional_generators",
            "seasonal_ratings_new_entrants",
            "maintenance_existing_generators",
            "maintenance_new_entrants",
            "fixed_opex_existing_committed_anticipated_additional_generators",
            "fixed_opex_new_entrants",
            "variable_opex_existing_committed_anticipated_additional_generators",
            "variable_opex_new_entrants",
            "marginal_loss_factors_existing_generators",
            "marginal_loss_factors_new_entrants",
            "marginal_loss_factors_new_entrant_electrolysers",
            "auxiliary_load_existing_committed_anticipated_additional_generators",
            "auxiliary_load_new_entrants",
            "heat_rates_existing_committed_anticipated_additional_generators",
            "heat_rates_new_entrants",
            "gpg_min_stable_level_existing_generators",
            "gpg_min_stable_level_new_entrants",
            "affine_heat_rates_existing_generators",
            "affine_heat_rates_new_entrants",
            "long_duration_outages_existing_generators",
            "other_outages_existing_generators",
            "outages_new_entrants",
        ]
        _FUEL_PRICE_TABLES = [
            "coal_fuel_price",
            "biomass_fuel_price",
            "gas_prices_existing_generators",
            "gas_prices_new_entrants",
            "liquid_fuel_prices",
            "biomethane_prices",
            "hydrogen_prices",
            "industrial_fuel_costs",
            "residential_fuel_costs",
            "gpg_secondary_fuel_prices",
        ]
        _NEW_ENTRANTS_COST_TABLES = [
            "build_costs",
            # Per-technology, per-scenario weighted average cost of capital
            # (values in %). Consumed by the templater to annuitise each
            # new-entrant at AEMO's technology-specific rate instead of a
            # single scalar.
            "wacc",
            "connection_costs_for_wind_and_solar",
            "connection_costs_other",
            "connection_cost_forecast_wind_and_solar",
            "connection_cost_forecast_other",
        ]
        _NETWORK_REQUIRED_TABLES = (
            [
                "sub_regional_reference_nodes",
                "regional_topology_representation",
                "regional_reference_nodes",
                "renewable_energy_zones",
                "flow_path_transfer_capability",
                "interconnector_transfer_capability",
                "initial_resource_limits",
                "initial_transmission_limits",
            ]
            + _FLOW_PATH_AGUMENTATION_TABLES
            + [
                t
                for tables in _FLOW_PATH_AUGMENTATION_COST_TABLES.values()
                for t in tables
            ]
            + _REZ_CONNECTION_AGUMENTATION_TABLES
            + [t for tables in _REZ_AUGMENTATION_COST_TABLES.values() for t in tables]
        )
        _GENERATORS_STORAGE_REQUIRED_SUMMARY_TABLES = [
            "existing_committed_anticipated_additional_generator_summary",
            "consumer_energy_resources_summary",
            "new_entrants_summary",
            "new_entrant_electrolysers_summary",
        ]
        _GENERATORS_REQUIRED_PROPERTY_TABLES = [
            "expected_closure_years",
            "coal_minimum_stable_level",
            *_FUEL_PRICE_TABLES,
            "hydrogen_limit_for_gpg",
            "gpg_emissions_reduction_biomethane",
            "locational_cost_factors",
            "technology_cost_breakdown_ratios",
            "lead_time_and_project_life",
            "technology_specific_lcfs",
        ] + _GENERATOR_PROPERTY_TABLES
        # The pumped-hydro property tables share the "Storage properties" sheet with the
        # battery table; `build_limits_phes` holds the sub-regional pumped-hydro build
        # limits. Caching them does not by itself put pumped hydro in the model: the
        # templater's storage filter keeps batteries only.
        _BATTERY_REQUIRED_PROPERTY_TABLES = [
            "battery_properties",
            "pumped_hydro_existing_committed_anticipated_additional_properties",
            "pumped_hydro_new_entrant_properties",
            "build_limits_phes",
        ]
        _POLICY_REQUIRED_TABLES = [
            "vic_renewable_target",
            "vic_storage_target",
            "vic_offshore_wind_target",
            "nsw_roadmap_storage_energy_capacity_trajectory",
            "nsw_roadmap_storage_power_capacity_trajectory",
            "nsw_roadmap_min_vre_generation_target",
            "tas_renewable_target_trajectory",
            "tas_renewable_energy_target",
            "lret_target",
            "regional_carbon_budget_trajectory",
            "sa_renewable_generation_target",
        ]
        return (
            _NETWORK_REQUIRED_TABLES
            + _GENERATORS_STORAGE_REQUIRED_SUMMARY_TABLES
            + _GENERATORS_REQUIRED_PROPERTY_TABLES
            + _BATTERY_REQUIRED_PROPERTY_TABLES
            + _NEW_ENTRANTS_COST_TABLES
            + _POLICY_REQUIRED_TABLES
        )


REQUIRED_TABLES = _build_required_tables()


def build_local_cache(
    cache_path: Path | str, workbook_path: Path | str, iasr_workbook_version: str
) -> None:
    """Uses `isp-workbook-parser` to build a local cache of parsed workbook CSVs

    Examples:
        Perform required imports.
        >>> from pathlib import Path
        >>> from ispypsa.iasr_table_caching import build_local_cache

        Build the local cache of parsed workbook CSVs.
        >>> build_local_cache(
        ...     cache_path=Path("parsed_workbook_cache"),
        ...     workbook_path=Path("path/to/ISP_Workbook.xlsm"),
        ...     iasr_workbook_version="7.8"
        ... )

    Args:
        cache_path: Path that should be created for the local cache
        workbook_path: Path to an ISP Assumptions Workbook that is supported by
            `isp-workbook-parser`
        iasr_workbook_version: str specifying the version of the work being used.

    Returns:
        None
    """
    workbook = Parser(Path(workbook_path))
    if workbook.workbook_version != iasr_workbook_version:
        raise ValueError(
            "The IASR workbook provided does not match the version "
            "specified in the config."
        )
    tables_to_get = REQUIRED_TABLES
    workbook.save_tables(cache_path, tables=tables_to_get)
    _normalise_cached_csvs_to_v74(Path(cache_path), tables_to_get)
    return None


def _normalise_cached_csvs_to_v74(cache_path: Path, table_names: list[str]) -> None:
    """Rewrite the cached 7.x CSVs into the canonical column names and table shapes the templater reads."""
    from .schema_normalisation import (
        _V74_TO_CANONICAL_COLUMN_RENAMES,
        aggregate_v74_biomethane_prices_to_v60_form,
        aggregate_v74_ecaa_units_to_power_stations,
        aggregate_v74_liquid_fuel_prices_to_v60_form,
        drop_v78_not_applicable_build_cost_year,
        merge_v74_connection_capacity_into_forecast,
        pivot_v74_other_outages_to_wide,
        split_v74_maximum_capacity_commissioning_dates,
        strip_v74_rez_prefix_from_aug_cost_options,
    )

    _strip_leading_underscore_columns(cache_path, table_names)
    # Column renames are no-ops when the source column name isn't present.
    for table_name, renames in _V74_TO_CANONICAL_COLUMN_RENAMES.items():
        csv_path = cache_path / f"{table_name}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        df = df.rename(columns=renames)
        df.to_csv(csv_path, index=False)

    # v7.8 FINAL prepends an all-"Not Applicable" 2024-25 build-cost column;
    # drop it so the templater's $/kW->$/MW multiply doesn't hit a string.
    drop_v78_not_applicable_build_cost_year(cache_path)
    # The consolidated max_capacity table carries a single `Commissioning date`
    # column; the templater expects separate confirmed and indicative columns.
    split_v74_maximum_capacity_commissioning_dates(cache_path)
    # `other_outages_existing_generators` is long-form (Fuel type × Property ×
    # year columns) but the static templater reads one value per property, so
    # pivot to wide form at the 2025-26 year.
    pivot_v74_other_outages_to_wide(cache_path)
    # v7.4 liquid_fuel_prices is per-generator; templater downstream
    # consumes a single representative price. Aggregate across the
    # Generator dimension.
    aggregate_v74_liquid_fuel_prices_to_v60_form(cache_path)
    # v7.4 biomethane_prices is per-source (Landfill/Waste/Crop) × scenario;
    # templater consumes a single representative price per scenario.
    aggregate_v74_biomethane_prices_to_v60_form(cache_path)
    # v7.4 connection_cost_forecast_wind_and_solar has no MVA col;
    # the templater needs it inline for the per-MW division. Merge it
    # in from connection_costs_for_wind_and_solar.
    merge_v74_connection_capacity_into_forecast(cache_path)
    # v7.4 publishes one row per generating unit; templater expects
    # per-power-station rows. Aggregate (first values for properties,
    # sum for installed capacity).
    aggregate_v74_ecaa_units_to_power_stations(cache_path)
    # v7.4 rez_augmentation_costs tables prefix Option values with REZ
    # IDs (e.g. "DN1 Option 1"); the merge with options tables (which
    # use bare suffixes) needs them stripped.
    strip_v74_rez_prefix_from_aug_cost_options(cache_path)


def _strip_leading_underscore_columns(cache_path: Path, table_names: list[str]) -> None:
    """Strip leading underscores from cached CSV column headers.

    `isp_workbook_parser` joins multi-row headers with `_`. When the top row
    of a header pair is blank for some columns (e.g. identifier columns under
    a seasonal-label-only top row in v7.4 seasonal_ratings), the joined name
    ends up with a leading underscore. This is a parser artifact, not real
    schema, so we strip it once at cache-load time.
    """
    for table_name in table_names:
        csv_path = cache_path / f"{table_name}.csv"
        if not csv_path.exists():
            continue
        df = pd.read_csv(csv_path)
        renames = {
            col: col.lstrip("_")
            for col in df.columns
            if isinstance(col, str) and col.startswith("_")
        }
        if renames:
            df = df.rename(columns=renames)
            df.to_csv(csv_path, index=False)


def list_cache_files(cache_path):
    files = REQUIRED_TABLES
    files = [cache_path / Path(file + ".csv") for file in files]
    return files
