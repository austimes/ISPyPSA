import logging

import linopy
import numpy as np
import pandas as pd
import pypsa
import xarray as xr

from ispypsa.translator.ccs_supply_curve import _map_generators_to_sinks

# Injection purchase variables are denominated in kt/year, for the same reason
# the fuel supply curve uses TJ rather than GJ. kt lands the caps (~1e2-1e4),
# the objective coefficients (~1e4) and the capture-coupling coefficients
# (~1e-4) inside the model's existing magnitude range. Mt would put objective
# coefficients at ~1e7 and tonnes would put caps at ~1e7, either of which risks
# the excessive-bound behaviour that produced a spurious Optimal at iteration 0
# on the rep-week NEM LP.
_T_PER_KT = 1.0e3


def _add_ccs_supply_curve(
    network: pypsa.Network,
    ccs_sink_tranches: pd.DataFrame,
    ccs_transport_adders: pd.DataFrame,
    generators: pd.DataFrame,
) -> None:
    """Adds per-sink CO2 injectivity limits and storage costs to the linopy model.

    Captured CO2 has to go somewhere, and the annual rate at which a given
    reservoir will take it is the scarce resource, so the quantity limit lives
    at the sink and is shared by every generator assigned to it. Per investment
    period and per sink, a purchase variable buys annual injection (kt) up to
    that sink's cap, and the annual captured tonnage of the generators assigned
    to the sink must be covered by that purchase.

    Unlike `_add_fuel_supply_curve` there is no uncapped backstop tranche, so
    the curve terminates: injectivity beyond the enumerated tranches does not
    exist at a price. A sink whose cap is zero therefore forces its generators'
    captured tonnage, and hence their generation, to zero.

    The constraint is annual-against-annual. `snapshot_weightings` sum to one
    year per period, so no investment-period `years` factor belongs on the cap;
    that factor applies only to PyPSA `GlobalConstraint` operational limits,
    which multiply the weightings by `years` internally. The period's span
    enters through the objective weighting on the storage price, exactly as it
    does for every other operational cost.

    Must be called after `network.optimize.create_model()` and re-called after
    any model rebuild, like `_add_custom_constraints`.

    Args:
        network: The `pypsa.Network` object with its linopy model built.
        ccs_sink_tranches: `pd.DataFrame` with columns 'investment_period',
            'sink', 'cap_kt' and 'storage_$/t', holding exactly one row per sink
            per investment period (enforced when the table is translated).
        ccs_transport_adders: `pd.DataFrame` with columns 'isp_sub_region_id',
            'sink' and 'transport_$/t', giving each bus its assigned sink.
        generators: `pd.DataFrame` of PyPSA friendly generator definitions, used
            for the 'bus' and 'isp_captured_co2_t_per_mwh' columns that are
            stripped from `network.generators` at build time.

    Returns: None
    """
    captured = _get_captured_intensities_by_sink(
        generators, ccs_transport_adders, network
    )
    if not captured:
        logging.warning(
            "CCS supply curve configured but the network has no CO2-capturing "
            "generators, so no CCS supply curve constraints were added."
        )
        return
    logging.info(
        f"Adding CCS supply curve constraints over {len(captured)} CO2 sinks "
        f"covering {sum(len(s) for s in captured.values())} capturing generators"
    )
    for period in network.investment_periods:
        tranches = ccs_sink_tranches[ccs_sink_tranches["investment_period"] == period]
        _add_sink_constraints_for_period(network, tranches, captured, period)


def _add_sink_constraints_for_period(
    network: pypsa.Network,
    tranches: pd.DataFrame,
    captured: dict[str, pd.Series],
    period: int,
) -> None:
    """Builds the purchase variable, coupling constraint and cost for each sink."""
    for sink, intensities in captured.items():
        tranche = tranches[tranches["sink"] == sink]
        purchases = _add_injection_purchase_variable(
            network.model, tranche, period, sink
        )
        _constrain_captured_co2_to_purchases(
            network, intensities, purchases, period, sink
        )
        _add_storage_cost_to_objective(network, tranche, purchases, period, sink)


def _get_captured_intensities_by_sink(
    generators: pd.DataFrame, transport_adders: pd.DataFrame, network: pypsa.Network
) -> dict[str, pd.Series]:
    """Captured tCO2/MWh of each capturing generator present, grouped by its sink."""
    present = generators[generators["name"].isin(network.generators.index)].copy()
    present["isp_captured_co2_t_per_mwh"] = pd.to_numeric(
        present["isp_captured_co2_t_per_mwh"], errors="coerce"
    ).fillna(0.0)
    capturing = present[present["isp_captured_co2_t_per_mwh"] > 0]
    sinks = _map_generators_to_sinks(capturing, transport_adders)
    return {
        sink: group.set_index("name")["isp_captured_co2_t_per_mwh"]
        for sink, group in capturing.groupby(
            sinks.reindex(capturing["name"]).to_numpy()
        )
    }


def _add_injection_purchase_variable(
    model: linopy.Model, tranche: pd.DataFrame, period: int, sink: str
) -> linopy.Variable:
    """One purchase variable (kt/year) for the sink, bounded by its injectivity cap."""
    return model.add_variables(
        lower=0.0,
        upper=float(tranche["cap_kt"].iloc[0]),
        name=f"ccs_injection_purchases_kt_{sink}_{period}",
    )


def _constrain_captured_co2_to_purchases(
    network: pypsa.Network,
    intensities: pd.Series,
    purchases: linopy.Variable,
    period: int,
    sink: str,
) -> None:
    """Requires the period's annual captured CO2 (kt) to be covered by the purchase."""
    p = network.model.variables.Generator_p.loc[:, intensities.index.to_list()]
    weights = network.snapshot_weightings["generators"].to_numpy()
    in_period = (network.snapshots.get_level_values(0) == period).astype(float)
    # Outer product of per-snapshot annualisation weights (zeroed outside the
    # period) and per-generator captured intensities gives each Generator_p
    # entry's kt contribution. Built with the variable's own coords so xarray
    # aligns rather than clashing with linopy's snapshot MultiIndex. Kept as a
    # per-generator intensity rather than a single scalar so that per-plant
    # capture rates do not silently break the accounting when IASR publishes them.
    kt_per_mw = xr.DataArray(
        np.outer(weights * in_period, intensities.to_numpy() / _T_PER_KT),
        coords=p.coords,
        dims=p.dims,
    )
    annual_captured_kt = (p * kt_per_mw).sum()
    network.model.add_constraints(
        annual_captured_kt - purchases <= 0,
        name=f"ccs_injection_cap_{sink}_{period}",
    )


def _add_storage_cost_to_objective(
    network: pypsa.Network,
    tranche: pd.DataFrame,
    purchases: linopy.Variable,
    period: int,
    sink: str,
) -> None:
    """Prices injection at the sink's storage cost, weighted like other opex."""
    objective_weight = float(network.investment_period_weightings["objective"][period])
    storage_cost_per_kt = float(tranche["storage_$/t"].iloc[0]) * _T_PER_KT
    network.model.objective = network.model.objective + (
        storage_cost_per_kt * objective_weight * purchases
    )
