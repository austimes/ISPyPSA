import logging
import re

import pandas as pd

from .dynamic_generator_properties import _ISP_TO_V74_SCENARIO
from .mappings import _TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP


def _template_energy_policy_targets(
    iasr_tables: dict[str, pd.DataFrame], scenario: str
) -> dict[str, pd.DataFrame]:
    """Creates ISPyPSA templates for energy policy targets including NEM-wide and state-level policies.

    Args:
        iasr_tables: Dict of tables from the IASR workbook that have been parsed using
            `isp-workbook-parser`.
        scenario: Scenario obtained from the model configuration

    Returns:
        `dict[pd.DataFrame]`: Templates for renewable share targets, the (empty) Powering Australia Plan,
            renewable generation targets, and technology capacity targets
    """
    logging.info("Creating templates for energy policy targets")

    # Create templates for energy policy targets
    renewable_share_targets = _template_renewable_share_targets(iasr_tables)

    # The 7.8 IASR has no Powering Australia Plan table, so its template is empty.
    power_aus_plan = pd.DataFrame(columns=["FY", "policy_id", "pct"])

    renewable_generation_targets = _template_renewable_generation_targets(
        iasr_tables, scenario
    )

    technology_capacity_targets = _template_technology_capacity_targets(iasr_tables)

    return {
        "renewable_share_targets": renewable_share_targets,
        "powering_australia_plan": power_aus_plan,
        "renewable_generation_targets": renewable_generation_targets,
        "technology_capacity_targets": technology_capacity_targets,
    }


def _template_renewable_share_targets(
    iasr_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Creates ISPyPSA templates for renewable share targets from the yearly target tables.
    Uses TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP to identify files and their
        corresponding regions.

    Args:
        iasr_tables: Dict of tables from the IASR workbook that have been parsed using
            `isp-workbook-parser`.

    Returns:
        `pd.DataFrame`: Template containing renewable share targets with columns for
            financial year, region_id, policy_id, and percentage values in decimal form
    """
    logging.info("Creating template for renewable share targets")
    state_renewable_share_targets = []

    # Get mapping for this function
    target_files = _TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP[
        "template_renewable_share_targets"
    ]

    for target in target_files:
        df = _extract_yearly_share_targets(iasr_tables[target["csv"]])
        df["region_id"] = target["region_id"]
        df["policy_id"] = target["policy_id"]
        df["pct"] = df["pct"].astype(float)

        state_renewable_share_targets.append(
            df[["FY", "region_id", "policy_id", "pct"]]
        )

    merged_state_renewable_share_targets = pd.concat(
        state_renewable_share_targets, ignore_index=True
    )
    merged_state_renewable_share_targets["FY"] = merged_state_renewable_share_targets[
        "FY"
    ].str.replace("-", "_")

    return merged_state_renewable_share_targets


def _extract_yearly_share_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts share targets (%) from a table with one row per calendar or financial year.

    Returns:
        `pd.DataFrame`: columns FY (e.g. "2029_30" or "2026-27") and pct
    """
    if "Calendar year" in df.columns:
        financial_years = _financial_year_ending_in(df["Calendar year"].astype(int))
    else:
        financial_years = df["Financial year"]
    return pd.DataFrame(
        {"FY": financial_years, "pct": df["All scenarios"].astype(float)}
    )


def _financial_year_ending_in(calendar_years: pd.Series) -> pd.Series:
    """Names the financial year ending June of each calendar year, e.g. 2030 -> "2029_30".

    AEMO assumes a target set for a calendar year is met by the end of the financial
    year ending in that year.
    """
    return (
        (calendar_years - 1).astype(str)
        + "_"
        + (calendar_years % 100).map("{:02d}".format)
    )


def _template_technology_capacity_targets(
    iasr_tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Creates ISPyPSA templates for the state storage and offshore wind capacity targets.
    Uses TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP to identify
    files and their corresponding regions.

    Args:
        iasr_tables: Dict of tables from the IASR workbook that have been parsed using
            `isp-workbook-parser`.
    Returns:
        `pd.DataFrame`: Template containing technology capacity trajectories
            with columns for financial year, region_id and capacity in MW
    """
    logging.info("Creating template for technology capacity targets")

    technology_capacity_targets = []
    target_files = _TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP[
        "template_technology_capacity_targets"
    ]

    for target in target_files:
        df = iasr_tables[target["csv"]]
        if df.columns[0] == "Calendar year":
            values_df = _extract_calendar_year_gw_targets(df)
        else:
            values_df = _extract_financial_year_mw_targets(df)

        values_df["capacity_mw"] = values_df["capacity_mw"].astype(float)
        values_df["region_id"] = target["region_id"]
        values_df["policy_id"] = target["policy_id"]

        technology_capacity_targets.append(values_df)

    merged_technology_capacity_targets = pd.concat(
        technology_capacity_targets, ignore_index=True
    )
    merged_technology_capacity_targets["FY"] = merged_technology_capacity_targets[
        "FY"
    ].str.replace("-", "_")

    merged_technology_capacity_targets = merged_technology_capacity_targets.sort_values(
        ["region_id", "policy_id", "FY"]
    ).reset_index(drop=True)

    return merged_technology_capacity_targets


def _extract_financial_year_mw_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts the "target (MW)" row of a table with one column per financial year.

    Returns:
        `pd.DataFrame`: columns FY (e.g. "2029-30") and capacity_mw
    """
    first_column = df.iloc[:, 0]
    target_row_mask = first_column.str.contains(
        "target", case=False
    ) & first_column.str.contains("MW", case=False)
    target_row_idx = df.index[target_row_mask][0]
    return pd.DataFrame(
        {"FY": df.columns[1:], "capacity_mw": df.iloc[target_row_idx, 1:]}
    )


def _extract_calendar_year_gw_targets(df: pd.DataFrame) -> pd.DataFrame:
    """Extracts targets due by the end of a calendar year, given in GW (e.g. "2.6 GW").

    A target for calendar year Y is assigned to the financial year ending June Y, matching
    AEMO's ISP, which reports capacity at 1 July and shows each target installed by then.

    Returns:
        `pd.DataFrame`: columns FY (e.g. "2031_32") and capacity_mw
    """
    gigawatts = df.iloc[:, 1].str.removesuffix(" GW").astype(float)
    return pd.DataFrame(
        {
            "FY": _financial_year_ending_in(df["Calendar year"].astype(int)),
            "capacity_mw": gigawatts * 1000,
        }
    )


def _template_renewable_generation_targets(
    iasr_tables: dict[str, pd.DataFrame], scenario: str
) -> pd.DataFrame:
    """Creates ISPyPSA templates for renewable generation targets.
    Uses TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP to identify files and their corresponding regions.

    Args:
        iasr_tables: Dict of tables from the IASR workbook that have been parsed using
            `isp-workbook-parser`.
        scenario: Scenario obtained from the model configuration, which picks the
            target row of tables with one row per scenario group

    Returns:
        `pd.DataFrame`: Template containing renewable capacity trajectories with columns for
            financial year, region_id and capacity in MW (converted from GWh)

    """
    logging.info("Creating template for renewable generation trajectories")

    renewable_generation_targets = []
    target_files = _TEMPLATE_RENEWABLE_ENERGY_TARGET_MAP[
        "template_renewable_generation_targets"
    ]

    for target in target_files:
        df = iasr_tables[target["csv"]]
        # Check for GWh in row indices
        if not df.iloc[:, 0].str.contains("GWh", case=False).any():
            raise ValueError(f"No GWh values found in {target['csv']}.csv")

        # if exists, remove the "Notes" row
        df = df[~df.iloc[:, 0].str.contains("Notes", case=False)]
        if "row_by_scenario" in target:
            row = target["row_by_scenario"][_ISP_TO_V74_SCENARIO[scenario]]
            df = df[df.iloc[:, 0].str.contains(row)]

        renewable_gen_target = df.melt(
            id_vars=df.columns[0], var_name="FY", value_name="capacity_gwh"
        ).dropna(subset=["capacity_gwh"])

        # Convert GWh to MWh
        renewable_gen_target["capacity_mwh"] = (
            renewable_gen_target["capacity_gwh"].astype(float) * 1000
        )
        renewable_gen_target["region_id"] = target["region_id"]
        renewable_gen_target["policy_id"] = target["policy_id"]
        renewable_generation_targets.append(
            renewable_gen_target[["FY", "region_id", "policy_id", "capacity_mwh"]]
        )

    # Combine all dataframes
    merged_renewable_generation_targets = pd.concat(
        renewable_generation_targets, ignore_index=True
    )
    merged_renewable_generation_targets["FY"] = merged_renewable_generation_targets[
        "FY"
    ].str.replace("-", "_")

    return merged_renewable_generation_targets
