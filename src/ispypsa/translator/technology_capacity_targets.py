import logging

import pandas as pd

from ispypsa.translator.mappings import _TECHNOLOGY_CAPACITY_TARGET_UNITS


def _translate_technology_capacity_targets(
    technology_capacity_targets: pd.DataFrame,
    units: dict[str, pd.DataFrame],
    bus_regions: dict[str, str],
    investment_periods: list[int],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Translates technology capacity targets into minimum capacity custom constraints.

    Each target binds in every investment period that starts on or after the end of
    the financial year the target is due in (see `_add_first_binding_year`), and the
    latest target in force sets the constraint RHS. The LHS sums the capacity of every
    unit of the target's technology in the target's NEM region that is active in that
    period, existing and new build alike.

    Args:
        technology_capacity_targets: templated table with columns FY, region_id,
            policy_id and capacity_mw.
        units: PyPSA friendly `generators` and `batteries` tables, keyed by table name.
        bus_regions: NEM region id of each bus, indexed by bus name.
        investment_periods: model investment periods.

    Returns:
        Tuple of custom constraint (lhs, rhs) tables in PyPSA friendly format.
    """
    logging.info("Creating custom constraints for technology capacity targets")
    targets = _filter_to_policies_with_units(technology_capacity_targets)
    targets = _add_first_binding_year(targets)
    binding = _select_target_in_force_per_period(targets, investment_periods)
    policy_units = _list_policy_target_units(units, bus_regions)
    lhs = _create_capacity_target_lhs(binding, policy_units)
    rhs = binding.assign(rhs=binding["capacity_mw"])
    rhs = rhs[["constraint_name", "rhs", "constraint_type"]]
    return lhs, rhs


def _map_buses_to_nem_regions(
    sub_regions: pd.DataFrame, renewable_energy_zones: pd.DataFrame
) -> dict[str, str]:
    """Maps sub-region, REZ and NEM region bus names to their NEM region id."""
    sub_region_to_region = sub_regions.set_index("isp_sub_region_id")["nem_region_id"]
    rez_to_region = renewable_energy_zones.set_index("rez_id")["isp_sub_region_id"].map(
        sub_region_to_region
    )
    regions = sub_region_to_region.unique()
    return {
        **dict(zip(regions, regions)),
        **rez_to_region.to_dict(),
        **sub_region_to_region.to_dict(),
    }


def _filter_to_policies_with_units(targets: pd.DataFrame) -> pd.DataFrame:
    """Keeps targets whose policy has a unit selection defined, logging the others."""
    known = targets["policy_id"].isin(_TECHNOLOGY_CAPACITY_TARGET_UNITS)
    if not known.all():
        logging.info(
            "Technology capacity targets not enforced, no unit selection defined: "
            f"{sorted(targets.loc[~known, 'policy_id'].unique())}"
        )
    return targets[known]


def _add_first_binding_year(targets: pd.DataFrame) -> pd.DataFrame:
    """Adds the first investment period year a target binds in.

    A target due in financial year "2029_30" must be met by the end of June 2030, so
    it binds in investment periods labelled 2030 and later.
    """
    first_binding_year = targets["FY"].str[:4].astype(int) + 1
    return targets.assign(first_binding_year=first_binding_year)


def _select_target_in_force_per_period(
    targets: pd.DataFrame, investment_periods: list[int]
) -> pd.DataFrame:
    """Pairs each investment period with the latest target of each policy due by then."""
    periods = pd.DataFrame({"investment_period": investment_periods})
    paired = targets.merge(periods, how="cross")
    paired = paired[paired["first_binding_year"] <= paired["investment_period"]]
    paired = paired.sort_values("first_binding_year")
    in_force = paired.groupby(["policy_id", "investment_period"]).tail(1)
    return in_force.assign(
        constraint_name=in_force["policy_id"]
        + "_"
        + in_force["investment_period"].astype(str),
        constraint_type=">=",
    ).reset_index(drop=True)


def _list_policy_target_units(
    units: dict[str, pd.DataFrame], bus_regions: dict[str, str]
) -> pd.DataFrame:
    """Lists the units counted by each policy, with their NEM region and lifetime."""
    policy_units = []
    for policy_id, (
        table,
        component,
        selector,
    ) in _TECHNOLOGY_CAPACITY_TARGET_UNITS.items():
        selected = units[table][selector(units[table])]
        policy_units.append(
            selected[["name", "bus", "build_year", "lifetime"]].assign(
                policy_id=policy_id, component=component
            )
        )
    policy_units = pd.concat(policy_units, ignore_index=True)
    return policy_units.assign(region_id=policy_units["bus"].map(bus_regions))


def _filter_to_units_active_in_period(terms: pd.DataFrame) -> pd.DataFrame:
    """Keeps unit terms whose unit is built and not yet retired in the investment period."""
    active = (terms["build_year"] <= terms["investment_period"]) & (
        terms["investment_period"] < terms["build_year"] + terms["lifetime"]
    )
    return terms[active]


def _create_capacity_target_lhs(
    binding: pd.DataFrame, policy_units: pd.DataFrame
) -> pd.DataFrame:
    """Creates one capacity term per unit active in each binding target's period."""
    terms = binding.merge(policy_units, on=["policy_id", "region_id"])
    terms = _filter_to_units_active_in_period(terms)
    return pd.DataFrame(
        {
            "constraint_name": terms["constraint_name"],
            "variable_name": terms["name"],
            "coefficient": 1.0,
            "component": terms["component"],
            "attribute": "p_nom",
        }
    ).reset_index(drop=True)
