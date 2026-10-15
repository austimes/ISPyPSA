import logging
import re
from pathlib import Path

import pandas as pd
import pypsa

from ispypsa.translator.helpers import convert_to_numeric_if_possible

# Monthly capacity-factor profile for conventional (non-pumped) hydro, applied
# as a static p_max_pu series for Water-carrier generators. ISPyPSA does not
# load hydro availability traces, so without this constraint the LP dispatches
# Water generators at ~85-100% CF (unbounded by anything except p_nom), inflating
# annual hydro generation by ~4x vs realistic levels.
#
# Values derived from AEMO Generation Information NEM monthly hydro generation
# (long-run averages, NSW + Tas hydro dominate the fleet). Annual mean of ~0.37,
# inside the realistic 30-45% CF band for Australian conventional hydro. This
# applies uniformly to all Water-carrier generators (Tumut, Murray, Eildon,
# Bendeela, etc.); per-generator CF differentiation requires AEMO Gen Info
# per-facility data which is out of scope for this fix.
_HYDRO_MONTHLY_CF = {
    1: 0.25,
    2: 0.25,  # peak summer - low inflows
    3: 0.35,
    4: 0.35,
    5: 0.35,  # autumn
    6: 0.40,
    7: 0.40,
    8: 0.40,  # winter - peak inflows
    9: 0.45,
    10: 0.45,
    11: 0.45,  # spring - snowmelt
    12: 0.30,  # early summer
}


# NEM-wide annual conventional-hydro energy budget (MWh) by financial year,
# used to cap total annual Water-carrier generation via a GlobalConstraint
# (see `_add_hydro_energy_budget_constraint`). `_HYDRO_MONTHLY_CF` above is only a
# ceiling on instantaneous output; paired with hydro's near-zero marginal cost, the
# LP dispatches Water generators at ~that ceiling in almost every hour, which
# overstates annual hydro generation because real hydro is water-limited, not just
# capacity-limited.
#
# Source: AEMO 2026 ISP Step Change modelled conventional-hydro generation
# ("Annual generation and emissions 2026 ISP.xlsx", sheet 'SC Gen', column
# 'Hydro', sensitivity FP20403_260508a; PHES is reported separately in that
# workbook and is modelled separately here as StorageUnits). The trajectory
# declines from ~16.7 TWh (2027) to ~9.8 TWh (2050).
#
# Each figure is a NEM-wide annual total, so it only describes a network that
# covers the whole NEM. A run filtered to a subset of regions models only part
# of the hydro fleet, and applying the NEM-wide total to it would leave that
# fleet effectively uncapped, so the constraint is skipped on such runs.
_HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY = {
    2027: 16_669_580.0,
    2028: 15_495_760.0,
    2029: 15_517_830.0,
    2030: 12_988_940.0,
    2031: 13_099_010.0,
    2032: 12_685_670.0,
    2033: 12_164_150.0,
    2034: 12_471_840.0,
    2035: 14_362_580.0,
    2036: 13_483_620.0,
    2037: 13_301_300.0,
    2038: 14_846_830.0,
    2039: 13_635_800.0,
    2040: 12_769_520.0,
    2041: 10_776_160.0,
    2042: 9_830_530.0,
    2043: 10_737_040.0,
    2044: 10_726_160.0,
    2045: 11_001_850.0,
    2046: 9_187_630.0,
    2047: 9_972_260.0,
    2048: 11_812_520.0,
    2049: 11_380_730.0,
    2050: 9_833_820.0,
}


def _hydro_annual_budget_mwh(period: int) -> float:
    """AEMO SC hydro budget for a financial year, clamped to the published
    2027-2050 range (a 2025/2026 chain period uses the 2027 value)."""
    years = sorted(_HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY)
    clamped = min(max(int(period), years[0]), years[-1])
    return _HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY[clamped]


def _build_seasonal_hydro_trace(snapshots: pd.MultiIndex) -> pd.DataFrame:
    """Build a wind/solar-shaped trace DataFrame for Water-carrier generators.

    PyPSA's network.snapshots MultiIndex levels are unnamed by default while
    ISPyPSA's trace DataFrames use named columns ("investment_periods",
    "snapshots") that get_set_index'd downstream. Construct by position to
    work either way."""
    investment_period_level = snapshots.get_level_values(0)
    timestep_level = snapshots.get_level_values(1)
    return pd.DataFrame(
        {
            "investment_periods": investment_period_level,
            "snapshots": timestep_level,
            "p_max_pu": [_HYDRO_MONTHLY_CF[m] for m in timestep_level.month],
        }
    )


def _get_trace_data(generator_name: str, path_to_traces: Path):
    """Fetches trace data for a generator from directories containing traces.

    Args:
        generator_name: String defining the generator's name
        path_to_traces: `pathlib.Path` for directory containing traces

    Returns:
        DataFrame with resource trace data.
    """
    generator_name_without_build_year = re.sub(r"_[0-9]{4}$", "", generator_name)
    filename = Path(f"{generator_name_without_build_year}.parquet")
    trace_filepath = path_to_traces / filename
    trace_data = pd.read_parquet(trace_filepath)
    return trace_data


def _get_marginal_cost_timeseries(
    generator_id: str, path_to_marginal_costs: Path
) -> pd.Series:
    """Fetches marginal cost timeseries data for a generator and returns a Series
    with marginal costs and (investment_period, snapshots) multi-index.

    Args:
        generator_id: String defining the generator's id (name with special characters
            replaced by "_").
        path_to_marginal_costs: `pathlib.Path` for directory containing marginal costs.

    Returns:
        Series with marginal cost timeseries data.
    """
    filename = Path(f"{generator_id}.parquet")
    trace_filepath = path_to_marginal_costs / filename
    marginal_costs = pd.read_parquet(trace_filepath)
    marginal_costs = marginal_costs.set_index(
        ["investment_periods", "snapshots"]
    ).squeeze()
    return marginal_costs


def _add_generator_to_network(
    generator_definition: dict,
    network: pypsa.Network,
    path_to_solar_traces: Path,
    path_to_wind_traces: Path,
    path_to_marginal_costs: Path,
) -> None:
    """Adds a generator to a pypsa.Network based on a dict containing PyPSA Generator
    attributes.

    If the carrier of a generator is Wind or Solar then a dynamic maximum availability
    for the generator is applied (via `p_max_pu`). Otherwise, the nominal capacity of the
    generator is used to apply a static maximum availability.

    Args:
        generator_definition: dict containing pypsa Generator parameters
        network: The `pypsa.Network` object
        path_to_solar_traces: `pathlib.Path` for directory containing solar traces
        path_to_wind_traces: `pathlib.Path` for directory containing wind traces

    Returns: None
    """
    generator_definition["class_name"] = "Generator"

    if generator_definition["carrier"] == "Wind":
        trace_data = _get_trace_data(generator_definition["name"], path_to_wind_traces)
    elif generator_definition["carrier"] == "Solar":
        trace_data = _get_trace_data(generator_definition["name"], path_to_solar_traces)
    elif generator_definition["carrier"] == "Water":
        trace_data = _build_seasonal_hydro_trace(network.snapshots)
    else:
        trace_data = None

    if trace_data is not None:
        trace_data = trace_data.set_index(["investment_periods", "snapshots"])
        generator_definition["p_max_pu"] = trace_data["p_max_pu"]

    if isinstance(generator_definition["marginal_cost"], str):
        marginal_cost_timeseries = _get_marginal_cost_timeseries(
            generator_definition["marginal_cost"], path_to_marginal_costs
        )
        generator_definition["marginal_cost"] = marginal_cost_timeseries

    pypsa_attributes_only = {
        key: value
        for key, value in generator_definition.items()
        if not key.startswith("isp_") or key == "isp_technology_type"
    }
    network.add(**pypsa_attributes_only)


def _add_generators_to_network(
    network: pypsa.Network,
    generators: pd.DataFrame,
    path_to_timeseries_data: Path,
) -> None:
    """Adds the generators in a pypsa-friendly `pd.DataFrame` to the `pypsa.Network`.

    Args:
        network: The `pypsa.Network` object
        generators:  `pd.DataFrame` with `PyPSA` style `Generator` attributes.
        path_to_timeseries_data: `pathlib.Path` that points to the directory containing
            timeseries data
    Returns: None
    """
    path_to_solar_traces = path_to_timeseries_data / Path("solar_traces")
    path_to_wind_traces = path_to_timeseries_data / Path("wind_traces")
    path_to_marginal_costs = path_to_timeseries_data / Path("marginal_cost_timeseries")

    # This is needed because numbers can be converted to strings if the data has been saved to a csv.
    generators = convert_to_numeric_if_possible(generators, cols=["marginal_cost"])

    generators.apply(
        lambda row: _add_generator_to_network(
            row.to_dict(),
            network,
            path_to_solar_traces,
            path_to_wind_traces,
            path_to_marginal_costs,
        ),
        axis=1,
    )


def _add_hydro_energy_budget_constraint(
    network: pypsa.Network, filtered_to_regions: list[str] | None = None
) -> None:
    """Caps total annual Water-carrier generation at AEMO's modelled budget.

    Adds a PyPSA `GlobalConstraint` (type "operational_limit") per investment
    period, so the LP must allocate a limited annual water budget to its
    highest-value hours rather than dispatching hydro at its `p_max_pu`
    ceiling in every hour. The budget is the AEMO 2026 ISP Step Change
    conventional-hydro generation for that financial year (see
    `_HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY` for the source).

    The budget is a NEM-wide annual total and the NEM-wide hydro capacity it
    belongs to is not recoverable from the pypsa-friendly tables, which are
    already region-filtered, so the budget cannot be scaled to the modelled
    share of the fleet. It is therefore skipped, with a warning, whenever the
    caller reports that the run models only a subset of regions. Does nothing
    if the network has no Water generators.

    Args:
        network: The `pypsa.Network` object, with generators already added.
        filtered_to_regions: NEM regions or ISP sub-regions the run is filtered
            to, or None for an unfiltered whole-of-NEM run.

    Returns: None
    """
    water_capacity_mw = network.generators.loc[
        network.generators["carrier"] == "Water", "p_nom"
    ].sum()
    if water_capacity_mw == 0:
        return

    if filtered_to_regions:
        logging.warning(
            f"Run is filtered to regions {sorted(filtered_to_regions)}, so the NEM-wide "
            "annual conventional-hydro energy budget is not applied and hydro is "
            "limited only by its capacity factor ceiling."
        )
        return

    for period, years in network.investment_period_weightings["years"].items():
        network.add(
            "GlobalConstraint",
            f"water_annual_energy_budget_aemo2026sc_{period}",
            type="operational_limit",
            carrier_attribute="Water",
            sense="<=",
            constant=_hydro_annual_budget_mwh(period) * years,
            investment_period=period,
        )


def _add_custom_constraint_generators_to_network(
    network: pypsa.Network, generators: pd.DataFrame
) -> None:
    """Adds the Generators defined in `custom_constraint_generators.csv` in the `path_pypsa_inputs` directory to the
    `pypsa.Network` object. These are generators that connect to a dummy bus, not part of the rest of the network,
    the generators are used to model custom constraint investment by referencing the p_nom of the generators in the
    custom constraints.

    Args:
        network: The `pypsa.Network` object
        generators:  `pd.DataFrame` with `PyPSA` style `Generator` attributes.

    Returns: None
    """
    generators["class_name"] = "Generator"
    generators.apply(lambda row: network.add(**row.to_dict()), axis=1)


def _update_generator_availability_timeseries(
    name: str,
    carrier: str,
    network: pypsa.Network,
    path_to_solar_traces: Path,
    path_to_wind_traces: Path,
) -> None:
    """Updates the timeseries availability of the generator in the `pypsa.Network`.

    The function is used to set up the model for operational modelling following
    capacity expansion optimisation. Once the model snapshots are updated then the
    generator time series also need to be updated to match.

    Args:
        name: str specifying the generators name
        carrier: the generator fuel type
        network: The `pypsa.Network` object
        path_to_solar_traces: `pathlib.Path` for directory containing solar traces
        path_to_wind_traces: `pathlib.Path` for directory containing wind traces

    Returns: None
    """

    if carrier == "Wind":
        trace_data = _get_trace_data(name, path_to_wind_traces)
    elif carrier == "Solar":
        trace_data = _get_trace_data(name, path_to_solar_traces)
    else:
        trace_data = None

    if trace_data is not None:
        trace_data = trace_data.set_index(["investment_periods", "snapshots"])
        network.generators_t.p_max_pu[name] = trace_data.loc[:, ["p_max_pu"]]


def _update_generators_availability_timeseries(
    network: pypsa.Network,
    generators: pd.DataFrame,
    path_to_timeseries_data: Path,
) -> None:
    """Updates the timeseries availability of the generators in the pypsa-friendly `
    pd.DataFrame` in the `pypsa.Network`.

    Args:
        network: The `pypsa.Network` object
        generators:  `pd.DataFrame` with `PyPSA` style `Generator` attributes.
        path_to_timeseries_data: `pathlib.Path` that points to the directory containing
            timeseries data
    Returns: None
    """
    path_to_solar_traces = path_to_timeseries_data / Path("solar_traces")
    path_to_wind_traces = path_to_timeseries_data / Path("wind_traces")
    generators.apply(
        lambda row: _update_generator_availability_timeseries(
            row["name"],
            row["carrier"],
            network,
            path_to_solar_traces,
            path_to_wind_traces,
        ),
        axis=1,
    )
