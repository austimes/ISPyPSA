import logging
from pathlib import Path
from typing import Literal

import pandas as pd
from isp_trace_parser import get_data

from ispypsa.translator.mappings import (
    _FOSSIL_CARRIERS,
    _NSW_ROADMAP_CARRIERS,
    _THERMAL_CARRIERS,
    _TRET_RENEWABLE_CARRIERS,
    _VRET_RENEWABLE_CARRIERS,
)
from ispypsa.translator.technology_capacity_targets import (
    _add_first_binding_year,
    _filter_to_units_active_in_period,
    _select_target_in_force_per_period,
)

_LHS_COLUMNS = [
    "constraint_name",
    "variable_name",
    "coefficient",
    "component",
    "attribute",
]
_RHS_COLUMNS = ["constraint_name", "rhs", "constraint_type", "investment_period"]
_ENFORCED_POLICIES = ["nsw_iio_gen", "vret", "tret", "sa_net_renewable"]
# AEMO's demand traces net distributed PV (rooftop PV and PV non-scheduled
# generation) off demand; the trace before that netting minus the one after it
# is the distributed PV output.
_DEMAND_BEFORE_DISTRIBUTED_PV = "OPSO_MODELLING_PVLITE"
_DEMAND_AFTER_DISTRIBUTED_PV = "OPSO_MODELLING"
# Annual energy uses the hours in a year the model's snapshot weightings sum to.
_HOURS_PER_YEAR = 8760


def _translate_state_generation_targets(
    targets: pd.DataFrame,
    generators: pd.DataFrame,
    links: pd.DataFrame,
    bus_regions: dict[str, str],
    investment_periods: list[int],
    distributed_pv: pd.DataFrame,
    pre_roadmap_generators: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Translates the state renewable generation targets into custom constraints.

    Each target binds from the investment period ending the financial year it is due
    in, and the latest target in force sets the constraint (see
    `_select_target_in_force_per_period`). Energy terms sum annual dispatch over the
    period's snapshots at build time.

    Args:
        targets: columns FY, region_id, policy_id and target (MWh for NSW and
            Tasmania, a fraction of generation for VRET, unused for SA).
        generators: PyPSA friendly generators table.
        links: PyPSA friendly links table.
        bus_regions: NEM region id of each bus, indexed by bus name.
        investment_periods: model investment periods.
        distributed_pv: columns region_id, investment_period and
            distributed_pv_mwh (see `_read_distributed_pv_energy`).
        pre_roadmap_generators: names of generators excluded from the NSW Roadmap
            target because they predate it.

    Returns:
        Tuple of custom constraint (lhs, rhs) tables in PyPSA friendly format.
    """
    logging.info("Creating custom constraints for state generation targets")
    targets = _filter_to_enforced_policies(targets)
    binding = _select_target_in_force_per_period(
        _add_first_binding_year(targets), investment_periods
    )
    binding = binding.merge(
        distributed_pv, on=["region_id", "investment_period"], how="left"
    )
    generators = generators.assign(region_id=generators["bus"].map(bus_regions))
    constraints = [
        _create_nsw_roadmap_constraints(
            binding[binding["policy_id"] == "nsw_iio_gen"],
            generators,
            pre_roadmap_generators,
        ),
        _create_vret_constraints(binding[binding["policy_id"] == "vret"], generators),
        _create_tret_constraints(binding[binding["policy_id"] == "tret"], generators),
        _create_sa_net_renewable_constraints(
            binding[binding["policy_id"] == "sa_net_renewable"],
            generators,
            links,
            bus_regions,
        ),
    ]
    lhs = pd.concat([lhs for lhs, _ in constraints], ignore_index=True)
    rhs = pd.concat([rhs for _, rhs in constraints], ignore_index=True)
    return lhs, rhs[_RHS_COLUMNS]


def _combine_state_generation_targets(
    renewable_generation_targets: pd.DataFrame, renewable_share_targets: pd.DataFrame
) -> pd.DataFrame:
    """Stacks the templated generation (MWh) and share (%) targets into one target column,
    with shares as fractions."""
    generation = renewable_generation_targets.rename(columns={"capacity_mwh": "target"})
    shares = renewable_share_targets.assign(target=renewable_share_targets["pct"] / 100)
    return pd.concat([generation, shares.drop(columns="pct")], ignore_index=True)


def _list_pre_roadmap_generators(ecaa_generators: pd.DataFrame) -> list[str]:
    """Names the generators excluded from the NSW Roadmap target as predating it.

    AEMO excludes capacity existing or committed in its November 2019 Generation
    Information, which the IASR does not record, so every generator the IASR lists
    as existing is excluded. This also excludes existing units committed after
    November 2019, so the constraint asks for more new build than AEMO's.
    """
    return ecaa_generators.loc[
        ecaa_generators["status"] == "Existing", "generator"
    ].to_list()


def _filter_to_enforced_policies(targets: pd.DataFrame) -> pd.DataFrame:
    """Keeps targets with a constraint formulation, logging the others."""
    enforced = targets["policy_id"].isin(_ENFORCED_POLICIES)
    if not enforced.all():
        logging.info(
            "State generation targets not enforced, no constraint formulation: "
            f"{sorted(targets.loc[~enforced, 'policy_id'].unique())}"
        )
    return targets[enforced]


def _create_nsw_roadmap_constraints(
    binding: pd.DataFrame, generators: pd.DataFrame, pre_roadmap_generators: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """NSW Roadmap: sum of eligible capacity x its available energy per MW >= target (MWh).

    AEMO writes the target on installed capacity weighted by each generator's average
    capacity factor, so the terms are capacities, not dispatch.
    """
    eligible = generators[~generators["name"].isin(pre_roadmap_generators)]
    terms = _list_generator_terms(
        binding, eligible, _NSW_ROADMAP_CARRIERS, "available_energy"
    )
    return _to_lhs(terms, 1.0), binding.assign(rhs=binding["target"])


def _create_vret_constraints(
    binding: pd.DataFrame, generators: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """VRET: (renewables + distributed PV) / (renewables + distributed PV + thermal) >= share.

    Rearranged to be linear in the share s:
    (1 - s) x renewables - s x thermal >= -(1 - s) x distributed PV.
    """
    renewable = _list_generator_terms(
        binding, generators, _VRET_RENEWABLE_CARRIERS, "energy"
    )
    thermal = _list_generator_terms(binding, generators, _THERMAL_CARRIERS, "energy")
    lhs = pd.concat(
        [
            _to_lhs(renewable, 1 - renewable["target"]),
            _to_lhs(thermal, -thermal["target"]),
        ]
    )
    rhs = -(1 - binding["target"]) * binding["distributed_pv_mwh"]
    return lhs, binding.assign(rhs=rhs)


def _create_tret_constraints(
    binding: pd.DataFrame, generators: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """TRET: large-scale renewables + distributed PV >= target (MWh)."""
    renewable = _list_generator_terms(
        binding, generators, _TRET_RENEWABLE_CARRIERS, "energy"
    )
    rhs = binding["target"] - binding["distributed_pv_mwh"]
    return _to_lhs(renewable, 1.0), binding.assign(rhs=rhs)


def _create_sa_net_renewable_constraints(
    binding: pd.DataFrame,
    generators: pd.DataFrame,
    links: pd.DataFrame,
    bus_regions: dict[str, str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """SA net 100% renewable: net exports - fossil-fuel generation >= 0 (MWh)."""
    fossil = _list_generator_terms(binding, generators, _FOSSIL_CARRIERS, "energy")
    exports = _list_net_export_terms(binding, links, bus_regions)
    return pd.concat([_to_lhs(fossil, -1.0), exports]), binding.assign(rhs=0.0)


def _list_generator_terms(
    binding: pd.DataFrame, generators: pd.DataFrame, carriers: list[str], attribute: str
) -> pd.DataFrame:
    """Pairs each binding target with its region's generators of the given carriers
    that are active in the target's period."""
    selected = generators[generators["carrier"].isin(carriers)]
    terms = _filter_to_units_active_in_period(binding.merge(selected, on="region_id"))
    return terms.assign(
        variable_name=terms["name"], component="Generator", attribute=attribute
    )


def _list_net_export_terms(
    binding: pd.DataFrame, links: pd.DataFrame, bus_regions: dict[str, str]
) -> pd.DataFrame:
    """Energy terms for links crossing the region's border: +1 flowing out, -1 flowing in.

    A link's flow is positive from bus0 to bus1.
    """
    links = links.assign(
        region0=links["bus0"].map(bus_regions), region1=links["bus1"].map(bus_regions)
    )
    crossing = links[links["region0"] != links["region1"]]
    outward = binding.merge(crossing, left_on="region_id", right_on="region0")
    inward = binding.merge(crossing, left_on="region_id", right_on="region1")
    terms = pd.concat(
        [outward.assign(coefficient=1.0), inward.assign(coefficient=-1.0)]
    )
    return terms.assign(
        variable_name=terms["name"], component="Link", attribute="energy"
    )[_LHS_COLUMNS]


def _to_lhs(terms: pd.DataFrame, coefficient: float | pd.Series) -> pd.DataFrame:
    """Selects the custom constraint LHS columns, setting each term's coefficient."""
    return terms.assign(coefficient=coefficient)[_LHS_COLUMNS]


def _read_distributed_pv_energy(
    sub_regions: pd.DataFrame,
    parsed_traces_directory: Path,
    scenario: str,
    reference_year_mapping: dict[int, int],
    investment_periods: list[int],
    year_type: Literal["fy", "calendar"],
) -> pd.DataFrame:
    """Reads each NEM region's annual distributed PV energy (MWh) per investment period
    from the demand traces.

    Returns:
        `pd.DataFrame` with columns region_id, investment_period and distributed_pv_mwh.
    """
    traces = [
        get_data.get_demand_multiple_reference_years(
            reference_year_mapping={period: reference_year_mapping[period]},
            scenario=scenario,
            subregion=list(sub_regions["isp_sub_region_id"]),
            demand_type=[_DEMAND_BEFORE_DISTRIBUTED_PV, _DEMAND_AFTER_DISTRIBUTED_PV],
            poe="POE50",
            directory=parsed_traces_directory / "demand",
            year_type=year_type,
            select_columns=["datetime", "subregion", "demand_type", "value"],
        ).assign(investment_period=period)
        for period in investment_periods
    ]
    return _calculate_distributed_pv_energy(pd.concat(traces), sub_regions)


def _calculate_distributed_pv_energy(
    demand_traces: pd.DataFrame, sub_regions: pd.DataFrame
) -> pd.DataFrame:
    """Sums each NEM region's distributed PV energy (MWh) per investment period.

    Args:
        demand_traces: columns subregion, demand_type, value (MW) and investment_period.
        sub_regions: columns isp_sub_region_id and nem_region_id.
    """
    missing = {_DEMAND_BEFORE_DISTRIBUTED_PV, _DEMAND_AFTER_DISTRIBUTED_PV} - set(
        demand_traces["demand_type"]
    )
    if missing:
        raise ValueError(
            f"Parsed demand traces have no data for demand types {sorted(missing)}"
        )
    mean_mw = demand_traces.pivot_table(
        index=["subregion", "investment_period"],
        columns="demand_type",
        values="value",
        aggfunc="mean",
    ).reset_index()
    pv_mw = (
        mean_mw[_DEMAND_BEFORE_DISTRIBUTED_PV] - mean_mw[_DEMAND_AFTER_DISTRIBUTED_PV]
    )
    region_id = mean_mw["subregion"].map(
        sub_regions.set_index("isp_sub_region_id")["nem_region_id"]
    )
    energy = mean_mw.assign(
        region_id=region_id, distributed_pv_mwh=pv_mw * _HOURS_PER_YEAR
    )
    return energy.groupby(["region_id", "investment_period"], as_index=False)[
        "distributed_pv_mwh"
    ].sum()
