"""Fork-specific model input patches, applied between ISPyPSA's templater and translator.

Each patch takes ``(ispypsa_tables: dict[str, DataFrame], config)`` and returns a (possibly
mutated) ``ispypsa_tables`` dict. Patches typically edit ``new_entrant_generators``, append rows
to ``custom_constraints_lhs`` / ``custom_constraints_rhs``, or tweak ``expected_closure_years``.

Design choice: patches act at the ISPyPSA-input layer (CSVs between templater and translator)
rather than the PyPSA-friendly layer. This keeps mutations expressed in ISP-domain units
(technology names, REZ ids, financial-year shares) rather than PyPSA bus/generator names.

:func:`apply_model_patches` applies seven patches, in order, to every run:

  1. Pumped-storage fix -- re-route Wivenhoe / Shoalhaven / Borumba / Snowy 2.0 from
     ecaa_generators to ecaa_batteries so they are modelled as PyPSA StorageUnits, not
     unconstrained Water-carrier generators. See ``pumped_storage_fix.py`` for the data sources.

  2. PHES menu repair -- appends the IASR's new-entrant pumped-hydro candidates (10/24/48 h +
     BOTN - Cethana 20 h) at workbook costs, build limits and lead times, two authored
     long-duration classes (168 h and 336 h) whose capex is extrapolated from the published
     duration-cost line, a per-sub-region shared-site cap on total new-entrant PHES power, and
     the two committed/policy PHES units (Kidston, Phoenix) the templater's battery-only filter
     drops. See ``phes_menu.py`` for per-value workbook citations.

  3. Ageing-fleet maintenance overlay -- adds a per-row ageing premium to fom_$/kw/annum on ECAA
     thermal generators in their final years of operation, anchored against published
     refurbishment cost references. See ``maintenance_overlay.py`` for sources and methodology.

  4. End-of-life renewable repowering -- extends ECAA wind / solar closure_year by 20 years and
     adds an annualised repowering capex premium to fom_$/kw/annum. See ``repowering.py`` for
     sources, methodology, and limitations.

  5. Biomass availability cap -- adds a per-milestone-year NEM-wide biomass capacity ceiling as a
     PyPSA custom_constraint, anchored on the ARENA Bioenergy Roadmap 2021 and the AEMO ISP 2024
     baseline. See ``biomass_cap.py``.

  6. REZ limit relaxation -- a sensitivity switch, off unless a run passes a factor: multiplies every
     renewable energy zone (REZ) transmission, expansion and resource limit by that factor, leaving
     interconnector flow paths alone. See ``rez_limits.py``.

  7. Transmission corridor limit relaxation -- the matching sensitivity switch for the
     corridors, off unless a run passes a factor: multiplies the expansion headroom of every
     sub-region flow path and every REZ-to-sub-region connection by that factor, leaving AEMO's
     REZ group constraints alone. See ``flow_path_limits.py``.

Biomass feedstock beyond the residue tier is priced by the configured biomass supply curve
(``config.biomass_supply_curve.curve_csv``), which every campaign run sets, so the patches leave
the IASR residue-tier price in place as that curve's baseline.
"""

from .biomass_cap import apply as _apply_biomass_cap
from .flow_path_limits import apply as _apply_flow_path_limits
from .maintenance_overlay import apply as _apply_maintenance_overlay
from .phes_menu import apply as _apply_phes_menu
from .pumped_storage_fix import apply as _apply_pumped_storage_fix
from .repowering import apply as _apply_repowering
from .rez_limits import apply as _apply_rez_limits


def apply_model_patches(
    ispypsa_tables,
    config,
    rez_limit_factor: float | None = None,
    flow_path_limit_factor: float | None = None,
):
    """Apply the seven fork-specific model patches, in order, to templated ISPyPSA tables.

    :param ispypsa_tables: Templated ISPyPSA input tables, keyed by table name.
    :param config: The run's ISPyPSA configuration.
    :param rez_limit_factor: Factor the REZ limit relaxation sensitivity multiplies every REZ limit by;
        ``None`` leaves the IASR limits in place.
    :param flow_path_limit_factor: Factor the corridor limit relaxation sensitivity multiplies every
        flow-path and REZ-connection expansion limit by; ``None`` leaves the IASR limits in place.
    :return: The patched tables.
    """
    ispypsa_tables = _apply_pumped_storage_fix(ispypsa_tables, config)
    ispypsa_tables = _apply_phes_menu(ispypsa_tables, config)
    ispypsa_tables = _apply_maintenance_overlay(ispypsa_tables, config)
    ispypsa_tables = _apply_repowering(ispypsa_tables, config)
    ispypsa_tables = _apply_biomass_cap(ispypsa_tables, config)
    ispypsa_tables = _apply_rez_limits(ispypsa_tables, config, rez_limit_factor)
    ispypsa_tables = _apply_flow_path_limits(
        ispypsa_tables, config, flow_path_limit_factor
    )
    return ispypsa_tables
