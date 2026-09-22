"""Stepped social-licence premium on renewable energy zone (REZ) generation above AEMO's published limits.

ISPyPSA gives every soft REZ resource limit one unbounded ``<constraint>_relax_<year>`` dummy generator priced at
AEMO's violation penalty (A$0.3M/MW, annuitised at the transmission weighted average cost of capital). That buys
unlimited relaxation at one flat price, which makes a campaign that relaxes REZ ceilings pay nothing extra for the
land it moves onto.

This module replaces each unbounded generator with two bounded tranches, so the relaxation becomes a rising supply
curve: one tranche of width equal to the published limit at the penalty plus the first premium, and a second of twice
that width at the penalty plus the second premium. Each premium is a fraction of the median annuitised capital cost of
the constraint's own new-entrant members, so a premium is proportional to what building in that zone costs rather than
a flat dollar figure across zones of very different cost. Nothing above three times the published limit can be built.

The premiums come from ``--social-licence-premiums``; the derivation of the two fractions is in
``analysis/research/social_licence_premium/research.md``.
"""

from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

#: Width of each tranche, as a multiple of the constraint's published limit.
_TRANCHE_WIDTHS = (1.0, 2.0)


def apply(
    pypsa_friendly: dict[str, pd.DataFrame], premiums: tuple[float, ...]
) -> dict[str, pd.DataFrame]:
    """Explode every REZ relaxation generator into bounded, premium-priced tranches.

    Group transmission expansion generators, and relaxation generators whose limit or member
    cost is unknown, pass through untouched.

    :param pypsa_friendly: Translated PyPSA friendly tables, keyed by table name.
    :param premiums: One premium fraction per tranche, e.g. ``(0.15, 0.60)``.
    :return: The patched tables.
    """
    generators = pypsa_friendly["custom_constraints_generators"]
    limits = pypsa_friendly["custom_constraints_rhs"].set_index("constraint_name")[
        "rhs"
    ]
    medians = _median_member_capital_cost(pypsa_friendly).dropna()
    priceable = (
        generators["name"].str.contains("_relax_")
        & generators["isp_name"].isin(limits.index)
        & generators["isp_name"].isin(medians.index)
    )
    unbounded, others = generators[priceable], generators[~priceable]
    tranches = pd.concat(
        [
            _priced_tranche(unbounded, limits, medians, step, width, premium)
            for step, (width, premium) in enumerate(
                zip(_TRANCHE_WIDTHS, premiums), start=1
            )
        ],
        ignore_index=True,
    )
    pypsa_friendly["custom_constraints_generators"] = pd.concat(
        [others, tranches], ignore_index=True
    )
    pypsa_friendly["custom_constraints_lhs"] = _retarget_lhs(
        pypsa_friendly["custom_constraints_lhs"], unbounded, tranches
    )
    log.warning(
        f"relaxation_tranches: priced {len(unbounded)} REZ relaxation generators as "
        f"{len(premiums)} tranches at premiums {list(premiums)}"
    )
    return pypsa_friendly


def _median_member_capital_cost(
    pypsa_friendly: dict[str, pd.DataFrame],
) -> pd.Series:
    """Median annuitised capital cost of each resource limit's own new-entrant members."""
    lhs = pypsa_friendly["custom_constraints_lhs"]
    members = lhs[lhs["coefficient"] > 0]
    costs = pypsa_friendly["generators"].set_index("name")["capital_cost"]
    return (
        members.assign(capital_cost=members["variable_name"].map(costs))
        .groupby("constraint_name")["capital_cost"]
        .median()
    )


def _priced_tranche(
    unbounded: pd.DataFrame,
    limits: pd.Series,
    medians: pd.Series,
    step: int,
    width: float,
    premium: float,
) -> pd.DataFrame:
    """One bounded tranche per relaxation generator, `width` times its constraint's published limit."""
    rows = unbounded.copy()
    rows["name"] = rows["isp_name"] + f"_relax{step}_" + rows["build_year"].astype(str)
    rows["p_nom_max"] = rows["isp_name"].map(limits) * width
    rows["capital_cost"] = rows["capital_cost"] + premium * rows["isp_name"].map(
        medians
    )
    return rows.dropna(subset=["p_nom_max", "capital_cost"])


def _retarget_lhs(
    lhs: pd.DataFrame, unbounded: pd.DataFrame, tranches: pd.DataFrame
) -> pd.DataFrame:
    """Swap each relaxation generator's left-hand side row for one row per tranche, at the same coefficient."""
    kept = lhs[~lhs["variable_name"].isin(unbounded["name"])]
    rows = tranches.rename(
        columns={"isp_name": "constraint_name", "name": "variable_name"}
    )[["constraint_name", "variable_name"]]
    rows = rows.assign(component="Generator", attribute="p_nom", coefficient=-1.0)
    return pd.concat([kept, rows], ignore_index=True)
