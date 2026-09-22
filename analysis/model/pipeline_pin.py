"""Near-term new-entrant allowance: a ceiling on new-entrant build in the pipeline years.

Until the last pipeline year the fleet is what the Integrated System Plan (ISP) already has under
way - existing, committed and anticipated projects - plus a small allowance for anything else. Left
unconstrained, the optimiser builds the whole near term at once, which is neither buildable nor what
the ISP's own development path shows.

The allowance is applied as a NEM-wide capacity ceiling on every ``New Entrant`` row of the
generator and battery menus, one constraint per component class because the custom-constraints
framework sums one component type per constraint, so generation and storage carry their own
ceiling. Both values are campaign inputs (``msm solve --new-entrant-cap-mw`` and
``--new-entrant-storage-cap-mw``), not numbers this module chooses.
"""

from __future__ import annotations

import pandas as pd

from .capacity_cap import add_capacity_cap

# A residual of exactly zero is dropped as an unbounded constraint, so a zero allowance is
# applied as the tightest ceiling the solver can still see.
_MINIMUM_CAP_MW = 1e-6

_MENUS = (
    ("new_entrant_generators", "generator", "generator_capacity"),
    ("new_entrant_batteries", "storage_name", "storage_capacity"),
)


def apply(
    ispypsa_tables: dict[str, pd.DataFrame],
    config,
    cap_mw: float | None = None,
    storage_cap_mw: float | None = None,
) -> dict[str, pd.DataFrame]:
    """Cap new-entrant generation at ``cap_mw`` MW and new-entrant storage at ``storage_cap_mw`` MW across the NEM.

    :param ispypsa_tables: Templated ISPyPSA input tables, keyed by table name.
    :param config: The run's ISPyPSA configuration; the cap binds on its investment periods.
    :param cap_mw: NEM-wide new-entrant generation allowance in MW; ``None`` leaves the menu uncapped.
    :param storage_cap_mw: NEM-wide new-entrant storage allowance in MW; ``None`` leaves the menu uncapped.
    :return: The patched tables.
    """
    for (table, id_col, term_type), cap in zip(_MENUS, (cap_mw, storage_cap_mw)):
        if cap is None:
            continue
        ispypsa_tables = add_capacity_cap(
            ispypsa_tables,
            config,
            constraint_prefix=f"pipeline_{table}",
            caps_by_year=_caps_by_year(config, cap),
            new_entrant_table=table,
            new_entrant_id_col=id_col,
            new_entrant_predicate=lambda row: row.get("status") == "New Entrant",
            existing_table=None,
            existing_predicate=None,
            term_type=term_type,
        )
    return ispypsa_tables


def _caps_by_year(config, cap_mw: float) -> dict[int, float]:
    """One menu's allowance repeated across every investment period of the solve."""
    return {
        year: max(cap_mw, _MINIMUM_CAP_MW)
        for year in config.temporal.capacity_expansion.investment_periods
    }
