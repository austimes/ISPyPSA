"""Renewable energy zone (REZ) limit relaxation, a sensitivity switch rather than a data correction.

AEMO's REZ limits are the binding ceiling on renewable build in the deep-cap chains: a chain held to a
0.005 t CO2e/MWh 2050 intensity runs out of REZ transmission capacity and REZ wind and solar resource before it
runs out of candidate projects. Relaxing every REZ limit by one factor gives a second campaign run set that
shows how much of the deep-cap cost sits in the REZ ceilings rather than in the generation technologies.

The factor multiplies, in the templated ISPyPSA tables:

  * ``renewable_energy_zones`` -- the REZ-to-sub-region transmission limit that becomes each REZ link's
    ``p_nom``, and the wind, solar and land-use resource and build limits that become the REZ resource and
    build limit custom constraints.
  * ``rez_transmission_expansion_costs`` -- ``additional_network_capacity_mw``, the headroom each REZ
    expansion option may add on top of that transmission limit. The per-MW expansion costs are untouched, so
    relaxed capacity is still paid for at AEMO's published price.
  * ``custom_constraints_rhs`` -- the right-hand side of AEMO's REZ group and transmission-limit constraints,
    which cap groups of REZ connections jointly and would otherwise keep binding at the unrelaxed level.

Interconnector flow paths are deliberately left alone: this sensitivity is about REZ headroom, not about the
transmission backbone between sub-regions.

A factor of 1.0, or no factor at all, leaves every table exactly as the templater produced it, so the base
campaign and a relaxed campaign differ in this one number.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# MW limit columns per templated table. Prices and penalty factors are excluded: relaxing a limit must not
# also change what the capacity costs.
_SCALED_COLUMNS = {
    "renewable_energy_zones": [
        "rez_transmission_network_limit_summer_typical",
        "wind_generation_total_limits_mw_high",
        "wind_generation_total_limits_mw_medium",
        "wind_generation_total_limits_mw_offshore_floating",
        "wind_generation_total_limits_mw_offshore_fixed",
        "solar_pv_plus_solar_thermal_limits_mw_solar",
        "land_use_limits_mw_wind",
        "land_use_limits_mw_solar",
    ],
    "rez_transmission_expansion_costs": ["additional_network_capacity_mw"],
}

_SCALED_TABLES = sorted([*_SCALED_COLUMNS, "custom_constraints_rhs"])


def apply(
    ispypsa_tables: dict[str, pd.DataFrame],
    config,
    rez_limit_factor: float | None = None,
) -> dict[str, pd.DataFrame]:
    """Multiply every REZ transmission, expansion and resource limit by ``rez_limit_factor``.

    :param ispypsa_tables: Templated ISPyPSA input tables, keyed by table name.
    :param config: The run's ISPyPSA configuration; unused, kept so every patch reads the same.
    :param rez_limit_factor: Factor to relax the REZ limits by; ``None`` or ``1.0`` changes nothing.
    :return: The patched tables.
    """
    if rez_limit_factor is None or rez_limit_factor == 1.0:
        return ispypsa_tables
    for table, columns in _SCALED_COLUMNS.items():
        ispypsa_tables[table] = _scale_columns(
            ispypsa_tables[table], columns, rez_limit_factor
        )
    ispypsa_tables["custom_constraints_rhs"] = _scale_group_transmission_limits(
        ispypsa_tables["custom_constraints_lhs"],
        ispypsa_tables["custom_constraints_rhs"],
        rez_limit_factor,
    )
    log.warning(f"rez_limits: scaled {_SCALED_TABLES} REZ limits by {rez_limit_factor}")
    return ispypsa_tables


def _scale_columns(
    table: pd.DataFrame, columns: list[str], factor: float
) -> pd.DataFrame:
    """Multiply the named MW-limit columns of one templated table by ``factor``."""
    scaled = table.copy()
    scaled[columns] = scaled[columns] * factor
    return scaled


def _scale_group_transmission_limits(
    lhs: pd.DataFrame, rhs: pd.DataFrame, factor: float
) -> pd.DataFrame:
    """Multiply the right-hand side of AEMO's REZ group and transmission-limit constraints by ``factor``.

    Those are the constraints that sum link flows. The fork's own capacity caps sum generator and storage
    capacity instead, so they are left at their authored tonnage and megawatt ceilings.
    """
    group_ids = lhs.loc[lhs["term_type"] == "link_flow", "constraint_id"].unique()
    scaled = rhs.copy()
    is_group = scaled["constraint_id"].isin(group_ids)
    scaled.loc[is_group, "rhs"] = scaled.loc[is_group, "rhs"] * factor
    return scaled
