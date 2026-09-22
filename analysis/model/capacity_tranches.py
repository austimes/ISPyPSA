"""Priced capacity tranches: the transmission social-licence curve and the build-rate curve.

Two campaign cost curves share one linopy mechanism, added to the model the same way the fuel supply curves are.
A group of components (one expandable link, or one carrier's new build) gets a set of tranche variables whose
widths are the megawatts available at each price step. A coupling constraint requires the group's installed
capacity to be covered by its tranche variables, and each tranche's adder enters the objective, so the group's
capacity pays a rising marginal price as it fills the cheap steps first.

**Transmission, above AEMO's published headroom.** Per expandable renewable energy zone (REZ) and corridor link,
the first tranche is the published expansion headroom at no premium, the second the same width again at the first
social-licence premium, and the last is unbounded at the second premium. The link's own
``<isp_name>_expansion_limit`` custom constraint remains the hard ceiling, so the last tranche needs no width of
its own. Each premium is a fraction of the link's own annuitised capital cost, from
``analysis/research/social_licence_premium/research.md``.

**Build rate, above the baseline additions of a period.** Per carrier, over the generators and storage units that
are this period's genuine new build, with widths from the cumulative capacity steps of
``build_rate_premiums_central.csv`` and absolute A$/MW/yr adders from the same file.

**Landholder payments.** A flat per-megawatt adder on every expansion link's capital cost, converted from the New
South Wales and Victorian per-kilometre host payment schemes at AEMO's own easement lengths. Applied before the
network is built, because a capital cost changed after the model exists never reaches the objective.

After the solve each group's premium is spread across its members as a uniform ``capital_premium`` column, which is
what makes the premiums visible to the component-based cost extractors downstream.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from analysis.model.recursive_dynamic import _P_NOM_OPT_THRESHOLD_MW, _strip_vintage
from ispypsa.pypsa_build.custom_constraints import _get_variables
from ispypsa.translator.helpers import _annuitised_investment_costs

log = logging.getLogger(__name__)

#: Columns of the tranche frame, in order.
_TRANCHE_COLUMNS = ["kind", "group", "period", "tranche", "width_mw", "adder"]

#: Columns the build-rate curve file must carry.
_CURVE_COLUMNS = ["group", "tranche", "financial_year", "cap_mw", "adder_$/mw/yr"]

#: PyPSA component name to the network attribute holding its table.
_COMPONENTS = {
    "Generator": "generators",
    "StorageUnit": "storage_units",
    "Link": "links",
}

#: Link classes the transmission curve prices, and the classes the build-rate curve meters.
_EXPANDABLE_LINK_TYPES = ("rez", "flow_path")

#: New South Wales Strategic Benefit Payments, A$200,000/km, stated as an undiscounted total and
#: treated here as a 25-year total annuitised at the 3% transmission weighted average cost of
#: capital, so it is comparable with the annuitised capital costs it sits beside. Victoria's
#: landholder payment is already published as A$8,000/km/year over 25 years.
_TRANSMISSION_WACC = 0.03
_PAYMENT_YEARS = 25
_NSW_AUD_PER_KM_YR = _annuitised_investment_costs(
    200_000.0, _TRANSMISSION_WACC, _PAYMENT_YEARS
)
_VIC_AUD_PER_KM_YR = 8_000.0

#: Sub-region hosting the payment scheme, mapped to its annual per-kilometre rate.
_LANDHOLDER_AUD_PER_KM_YR = {
    "CNSW": _NSW_AUD_PER_KM_YR,
    "NNSW": _NSW_AUD_PER_KM_YR,
    "SNW": _NSW_AUD_PER_KM_YR,
    "SNSW": _NSW_AUD_PER_KM_YR,
    "VIC": _VIC_AUD_PER_KM_YR,
    "WNV": _VIC_AUD_PER_KM_YR,
    "CVIC": _VIC_AUD_PER_KM_YR,
}

#: Capacity-weighted easement length per megawatt of each class of augmentation option.
_KM_PER_MW = {"rez": 0.149, "flow_path": 0.112}


def parse_premiums(text: str | None) -> tuple[float, ...] | None:
    """Parse ``0.15,0.60`` into the social-licence premium fraction of each tranche."""
    return tuple(float(part) for part in text.split(",")) if text else None


def load_build_rate_curve(path: str | Path, periods: list[int]) -> pd.DataFrame:
    """Read and validate the build-rate premium curve.

    :param path: CSV with columns ``group, tranche, financial_year, cap_mw, adder_$/mw/yr``.
    :param periods: Periods the curve must carry a row for.
    :return: The validated curve.
    """
    curve = pd.read_csv(path)
    _check_curve_columns(curve)
    _check_curve_periods(curve, periods)
    _check_curve_backstop(curve)
    _check_curve_adders(curve)
    return curve


def add_landholder_adders(pypsa_friendly: dict[str, pd.DataFrame]) -> None:
    """Add the host-landholder payment to every expansion link's capital cost, in place."""
    links = pypsa_friendly["links"]
    rate = (
        links["bus0"]
        .map(_LANDHOLDER_AUD_PER_KM_YR)
        .fillna(links["bus1"].map(_LANDHOLDER_AUD_PER_KM_YR))
        .fillna(0.0)
    )
    adder = rate * links["isp_type"].map(_KM_PER_MW).fillna(0.0)
    links["capital_cost"] = links["capital_cost"] + adder.where(
        links["p_nom_extendable"], 0.0
    )
    log.warning(
        f"capacity_tranches: landholder payments added to "
        f"{int((adder.where(links['p_nom_extendable'], 0.0) > 0).sum())} expansion links"
    )


def campaign_tranches(
    network: pypsa.Network,
    ispypsa_tables: dict[str, pd.DataFrame],
    period: int,
    social_licence_premiums: tuple[float, ...] | None,
    build_rate_curve: pd.DataFrame | None,
    rez_factor: float,
    flow_path_factor: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every priced capacity tranche of one solve and the components each group meters.

    :param network: The built network, whose linopy model the tranches are added to.
    :param ispypsa_tables: Templated tables, for the published headroom and the existing rosters.
    :param period: The investment year being solved.
    :param social_licence_premiums: Premium fraction per transmission tranche, or ``None``.
    :param build_rate_curve: Validated build-rate curve, or ``None``.
    :param rez_factor: Factor the run relaxed the REZ limits by.
    :param flow_path_factor: Factor the run relaxed the corridor limits by.
    :return: The tranche frame and the member frame.
    """
    tranches, members = [], []
    if social_licence_premiums is not None:
        headroom = _link_headroom_mw(
            network.links, ispypsa_tables, period, rez_factor, flow_path_factor
        )
        tranches.append(
            _transmission_tranches(network, headroom, period, social_licence_premiums)
        )
        members.append(_transmission_members(headroom))
    if build_rate_curve is not None:
        tranches.append(_build_rate_tranches(build_rate_curve, period))
        members.append(_build_rate_members(network, ispypsa_tables, period))
    tranches = pd.concat(tranches, ignore_index=True)
    members = pd.concat(members, ignore_index=True)
    priced = tranches[tranches["group"].isin(members["group"])]
    return priced.reset_index(drop=True), members


def add_priced_tranches(
    network: pypsa.Network, tranches: pd.DataFrame, members: pd.DataFrame
) -> None:
    """Add each group's tranche variables, coupling constraint and objective terms to the model."""
    weight = float(network.investment_period_weightings["objective"].iloc[0])
    for group, rows in tranches.groupby("group", sort=False):
        purchases = _add_tranche_variables(network.model, rows, group)
        _couple_capacity_to_tranches(
            network, members[members["group"] == group], purchases, group
        )
        network.model.objective = (
            network.model.objective
            + (_tranche_adders(rows, group, weight) * purchases).sum()
        )
    log.info(
        f"capacity_tranches: priced {len(tranches)} tranches over "
        f"{tranches['group'].nunique()} groups"
    )


def tranche_usage(network: pypsa.Network, tranches: pd.DataFrame) -> pd.DataFrame:
    """Solved megawatts and premium paid per tranche."""
    solved = {
        group: network.model.variables[_variable_name(group)].solution.to_pandas()
        for group in tranches["group"].unique()
    }
    mw_used = [
        float(solved[group].loc[tranche])
        for group, tranche in zip(tranches["group"], tranches["tranche"])
    ]
    return tranches.assign(
        mw_used=mw_used, premium_aud_per_yr=np.array(mw_used) * tranches["adder"]
    )


def allocate_premiums(
    network: pypsa.Network, usage: pd.DataFrame, members: pd.DataFrame
) -> None:
    """Spread each group's premium across its members as a uniform ``capital_premium`` column."""
    rates = members["group"].map(_group_premium_rates(network, usage, members))
    for attribute in _COMPONENTS.values():
        getattr(network, attribute)["capital_premium"] = 0.0
    for component, rows in members.assign(rate=rates).groupby("component"):
        frame = getattr(network, _COMPONENTS[component])
        frame.loc[rows["name"], "capital_premium"] = rows["rate"].to_numpy()


def _variable_name(group: str) -> str:
    """Name of one group's tranche variable set in the linopy model."""
    return f"capacity_tranche_{group}"


def _check_curve_columns(curve: pd.DataFrame) -> None:
    """Raise unless the curve carries every column the tranche builder reads."""
    missing = set(_CURVE_COLUMNS) - set(curve.columns)
    if missing:
        raise ValueError(f"Build-rate curve is missing columns: {sorted(missing)}")


def _check_curve_periods(curve: pd.DataFrame, periods: list[int]) -> None:
    """Raise unless every period of the chain has a row in the curve."""
    missing = sorted(set(periods) - set(curve["financial_year"]))
    if missing:
        raise ValueError(f"Build-rate curve has no rows for periods: {missing}")


def _check_curve_backstop(curve: pd.DataFrame) -> None:
    """Raise unless every group and year ends in one uncapped backstop tranche."""
    uncapped = curve[curve["cap_mw"].isna()].groupby(["group", "financial_year"]).size()
    expected = curve.groupby(["group", "financial_year"]).size()
    if not uncapped.reindex(expected.index).eq(1).all():
        raise ValueError(
            "Build-rate curve needs exactly one uncapped backstop tranche per group and year"
        )


def _check_curve_adders(curve: pd.DataFrame) -> None:
    """Raise where a group's adders fall as its cumulative capacity steps rise."""
    ordered = curve.sort_values(["group", "financial_year", "cap_mw"])
    steps = ordered.groupby(["group", "financial_year"])["adder_$/mw/yr"].diff()
    if (steps.fillna(0) < 0).any():
        raise ValueError("Build-rate curve adders must not decrease across tranches")


def _headroom_by_id(expansion_costs: pd.DataFrame, id_column: str) -> pd.Series:
    """Published expansion headroom per component, summed over that component's options."""
    return expansion_costs.groupby(id_column)["additional_network_capacity_mw"].sum(
        min_count=1
    )


def _link_headroom_mw(
    links: pd.DataFrame,
    ispypsa_tables: dict[str, pd.DataFrame],
    period: int,
    rez_factor: float,
    flow_path_factor: float,
) -> pd.Series:
    """Published expansion headroom of this period's expandable links, undoing the run's relaxation."""
    expandable = links[
        links["p_nom_extendable"]
        & links["isp_type"].isin(_EXPANDABLE_LINK_TYPES)
        & links["build_year"].eq(period)
    ]
    rez = _headroom_by_id(
        ispypsa_tables["rez_transmission_expansion_costs"], "rez_constraint_id"
    )
    flow_path = _headroom_by_id(
        ispypsa_tables["flow_path_expansion_costs"], "flow_path"
    )
    headroom = np.where(
        expandable["isp_type"].eq("rez"),
        expandable["bus0"].map(rez) / rez_factor,
        expandable["isp_name"].map(flow_path) / flow_path_factor,
    )
    return pd.Series(headroom, index=expandable.index).dropna()


def _transmission_tranches(
    network: pypsa.Network,
    headroom: pd.Series,
    period: int,
    premiums: tuple[float, ...],
) -> pd.DataFrame:
    """Published headroom free, then one tranche per premium, the last unbounded under the hard ceiling."""
    cost = network.links.loc[headroom.index, "capital_cost"]
    widths = [headroom, headroom, pd.Series(np.inf, index=headroom.index)]
    adders = [cost * 0.0, cost * premiums[0], cost * premiums[1]]
    return pd.concat(
        [
            _tranche_rows("transmission", headroom.index, period, step, width, adder)
            for step, (width, adder) in enumerate(zip(widths, adders), start=1)
        ],
        ignore_index=True,
    )


def _tranche_rows(
    kind: str,
    groups: pd.Index,
    period: int,
    tranche: int,
    width_mw: pd.Series,
    adder: pd.Series,
) -> pd.DataFrame:
    """One tranche row per group, in the tranche frame's own column order."""
    return pd.DataFrame(
        {
            "kind": kind,
            "group": list(groups),
            "period": period,
            "tranche": tranche,
            "width_mw": width_mw.to_numpy(),
            "adder": adder.to_numpy(),
        }
    )


def _transmission_members(headroom: pd.Series) -> pd.DataFrame:
    """Each priced link is a group of its own, metering its own capacity."""
    return pd.DataFrame(
        {
            "kind": "transmission",
            "group": list(headroom.index),
            "component": "Link",
            "name": list(headroom.index),
        }
    )


def _build_rate_tranches(curve: pd.DataFrame, period: int) -> pd.DataFrame:
    """One period's build-rate steps per carrier, with widths from the cumulative capacity caps."""
    rows = curve[curve["financial_year"] == period].sort_values(["group", "cap_mw"])
    caps = rows["cap_mw"].fillna(np.inf)
    widths = caps.groupby(rows["group"]).diff().fillna(caps)
    return rows.assign(
        kind="build_rate",
        period=period,
        width_mw=widths,
        adder=rows["adder_$/mw/yr"],
    )[_TRANCHE_COLUMNS].reset_index(drop=True)


def _build_rate_members(
    network: pypsa.Network, ispypsa_tables: dict[str, pd.DataFrame], period: int
) -> pd.DataFrame:
    """This period's genuine new-build generators and storage units, grouped by carrier."""
    generators = _new_build_rows(
        network.generators,
        set(ispypsa_tables["ecaa_generators"]["generator"]),
        period,
        "Generator",
    )
    storage = _new_build_rows(
        network.storage_units,
        set(ispypsa_tables["ecaa_batteries"]["storage_name"]),
        period,
        "StorageUnit",
    )
    return pd.concat([generators, storage], ignore_index=True)


def _new_build_rows(
    component: pd.DataFrame, roster: set[str], period: int, component_name: str
) -> pd.DataFrame:
    """Rows of one component table that this period builds new, keyed by carrier."""
    names = component.index.astype(str)
    is_existing = names.isin(roster) | pd.Index(
        [_strip_vintage(name) for name in names]
    ).isin(roster)
    built = (
        component["p_nom_extendable"]
        & component["build_year"].eq(period)
        & ~is_existing
        & component["bus"].ne("bus_for_custom_constraint_gens")
    )
    return pd.DataFrame(
        {
            "kind": "build_rate",
            "group": component.loc[built, "carrier"].to_numpy(),
            "component": component_name,
            "name": list(component.index[built]),
        }
    )


def _add_tranche_variables(model, rows: pd.DataFrame, group: str):
    """One capacity variable per tranche of a group, bounded by that tranche's width."""
    coords = pd.Index(rows["tranche"], name=f"{group}_tranche")
    return model.add_variables(
        lower=xr.DataArray(np.zeros(len(rows)), coords=[coords]),
        upper=xr.DataArray(rows["width_mw"].to_numpy(), coords=[coords]),
        name=_variable_name(group),
    )


def _couple_capacity_to_tranches(
    network: pypsa.Network, members: pd.DataFrame, purchases, group: str
) -> None:
    """Require the group's installed capacity to be covered by its tranche variables."""
    terms = tuple(
        (1.0, _get_variables(network.model, name, component, "p_nom"))
        for component, name in zip(members["component"], members["name"])
    )
    capacity = network.model.linexpr(*terms)
    network.model.add_constraints(
        capacity - purchases.sum() <= 0, name=_variable_name(group)
    )


def _tranche_adders(rows: pd.DataFrame, group: str, weight: float) -> xr.DataArray:
    """Tranche adders in A$/MW/year, weighted like every other annualised cost in the objective."""
    return xr.DataArray(
        rows["adder"].to_numpy() * weight,
        coords=[pd.Index(rows["tranche"], name=f"{group}_tranche")],
    )


def _group_premium_rates(
    network: pypsa.Network, usage: pd.DataFrame, members: pd.DataFrame
) -> pd.Series:
    """Premium per installed megawatt of each group, zero where the group built nothing."""
    built = (
        members.assign(p_nom_opt=_member_capacity(network, members))
        .groupby("group")["p_nom_opt"]
        .sum()
    )
    premium = usage.groupby("group")["premium_aud_per_yr"].sum()
    return (premium / built.where(built > _P_NOM_OPT_THRESHOLD_MW)).fillna(0.0)


def _member_capacity(network: pypsa.Network, members: pd.DataFrame) -> list[float]:
    """Solved capacity of every member, read from its own component table."""
    solved = {
        component: getattr(network, attribute)["p_nom_opt"]
        for component, attribute in _COMPONENTS.items()
    }
    return [
        float(solved[component].get(name, 0.0))
        for component, name in zip(members["component"], members["name"])
    ]
