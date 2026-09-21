"""Transmission corridor limit relaxation, the sensitivity switch beside the REZ one.

Once renewable energy zone (REZ) headroom is relaxed, the binding ceiling on a deep-cap chain moves to
the corridors that carry that energy between sub-regions. Relaxing every flow-path expansion limit by one
factor gives a run set that shows how much of the deep-cap cost sits in the transmission backbone rather
than in the REZ or generation limits.

The factor multiplies ``additional_network_capacity_mw`` in ``flow_path_expansion_costs``, the headroom an
expansion option may add on top of the templated capacity of every flow path between sub-regions, whether
it crosses a NEM region boundary or stays inside one. ISPyPSA's translator turns that column into the
``<flow path>_expansion_limit`` custom constraints that cap each corridor link's ``p_nom``, so scaling the
column is what moves those ceilings. The per-MW expansion costs are untouched, so relaxed capacity is still
paid for at AEMO's published price. REZ-to-sub-region connections belong to ``rez_limits``, so the two
factors are independent levers.

A factor of 1.0, or no factor at all, leaves the table exactly as the templater produced it, so the base
campaign and a relaxed campaign differ in this one number.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# The expansion headroom column both corridor tables carry. Per-MW costs are excluded: relaxing a limit must
# not also change what the capacity costs.
_CAPACITY_COLUMN = "additional_network_capacity_mw"

_SCALED_TABLES = ["flow_path_expansion_costs"]


def apply(
    ispypsa_tables: dict[str, pd.DataFrame],
    config,
    flow_path_limit_factor: float | None = None,
) -> dict[str, pd.DataFrame]:
    """Multiply every flow-path expansion limit by ``flow_path_limit_factor``.

    :param ispypsa_tables: Templated ISPyPSA input tables, keyed by table name.
    :param config: The run's ISPyPSA configuration; unused, kept so every patch reads the same.
    :param flow_path_limit_factor: Factor to relax the corridor limits by; ``None`` or ``1.0`` changes
        nothing.
    :return: The patched tables.
    """
    if flow_path_limit_factor is None or flow_path_limit_factor == 1.0:
        return ispypsa_tables
    ispypsa_tables["flow_path_expansion_costs"] = _scale_flow_paths(
        ispypsa_tables["flow_path_expansion_costs"], flow_path_limit_factor
    )
    log.warning(
        f"flow_path_limits: scaled {_SCALED_TABLES} corridor expansion limits "
        f"by {flow_path_limit_factor}"
    )
    return ispypsa_tables


def _scale_flow_paths(expansion_costs: pd.DataFrame, factor: float) -> pd.DataFrame:
    """Multiply every sub-region flow path's expansion headroom by ``factor``."""
    scaled = expansion_costs.copy()
    scaled[_CAPACITY_COLUMN] = scaled[_CAPACITY_COLUMN] * factor
    return scaled
