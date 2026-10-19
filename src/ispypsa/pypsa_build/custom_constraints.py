import logging
from pathlib import Path

import linopy
import numpy as np
import pandas as pd
import pypsa
import xarray as xr


def _get_variables(
    model: linopy.Model, component_name: str, component_type: str, attribute_type: str
):
    """Retrieves variable objects from a linopy model based on a component name and
    type.

    Args:
        model: The `linopy.Model` object
        component_name: str, the name given to the component when added by ISPyPSA to
            the `pypsa.Network`.
        component_type: str, the type of variable, should be one of
            'Generator', 'Link', 'Load', 'Storage', or 'StorageUnit'.
        attribute_type: str, the type of variable, should be one of
            'p' or 'p_nom'

    Returns: linopy.variables.Variable, or None if the variable cannot be
        resolved (e.g. component not in the model, or not extendable).

    """
    var = None
    if component_type == "Generator" and attribute_type == "p_nom":
        var = model.variables.Generator_p_nom.at[f"{component_name}"]
    elif component_type == "Link" and attribute_type == "p":
        var = model.variables.Link_p.loc[:, f"{component_name}"]
    elif component_type == "Link" and attribute_type == "p_nom":
        var = model.variables.Link_p_nom.at[f"{component_name}"]
    elif component_type == "Generator" and attribute_type == "p":
        var = model.variables.Generator_p.loc[:, f"{component_name}"]
    elif component_type == "StorageUnit" and attribute_type == "p_nom":
        # Only extendable storage units have a StorageUnit_p_nom variable in
        # linopy. Non-extendable units (fixed p_nom) are constants that
        # _add_custom_constraints moves to the RHS; a unit absent from the
        # network returns None so its NaN-filtering drops it.
        try:
            var = model.variables.StorageUnit_p_nom.at[f"{component_name}"]
        except (KeyError, AttributeError):
            var = None
    elif component_type == "StorageUnit" and attribute_type == "p_dispatch":
        # Battery (StorageUnit) discharge — its contribution to a transmission /
        # security corridor when exporting. PyPSA splits dispatch into
        # p_dispatch (discharge >= 0) and p_store (charge >= 0); the output term
        # counts discharge. Guarded because storage terms aren't pre-filtered
        # against the model like generator terms are, so a battery absent in the
        # modelled period (not yet built / retired / not in the candidate set)
        # must drop to None rather than raise.
        try:
            var = model.variables.StorageUnit_p_dispatch.loc[:, f"{component_name}"]
        except (KeyError, AttributeError):
            var = None
    elif component_type == "Load" and attribute_type == "p":
        logging.info(
            f"Load component {component_name} not added to custom constraint. "
            f"Load variables not implemented."
        )
    elif component_type == "Storage" and attribute_type == "p":
        logging.info(
            f"Storage component {component_name} not added to custom constraint. "
            f"Storage variables not implemented."
        )
    else:
        raise ValueError(f"{component_type} and {attribute_type} is not defined.")
    return var


def _fixed_capacity(network: pypsa.Network, terms: pd.DataFrame) -> pd.Series:
    """Returns coefficient x p_nom for each p_nom term of a non-extendable component.

    Other terms (variables, or components absent from the network) are NaN.
    """
    fixed = pd.Series(np.nan, index=terms.index)
    capacity_terms = terms[terms["attribute"] == "p_nom"]
    for component, group in capacity_terms.groupby("component"):
        static = network.static(component).reindex(group["variable_name"])
        is_fixed = static["p_nom_extendable"].eq(False).to_numpy()
        fixed[group.index[is_fixed]] = (
            group["coefficient"].to_numpy() * static["p_nom"].to_numpy()
        )[is_fixed]
    return fixed


def _period_generator_weights(network: pypsa.Network, period: int) -> np.ndarray:
    """Generator snapshot weightings (hours), zeroed outside the investment period."""
    in_period = network.snapshots.get_level_values(0) == period
    return network.snapshot_weightings["generators"].to_numpy() * in_period


def _convert_available_energy_to_capacity(
    network: pypsa.Network, terms: pd.DataFrame, period: int | None
) -> pd.DataFrame:
    """Turns 'available_energy' terms into p_nom terms scaled by each generator's
    available energy per MW of capacity (MWh/MW) over the investment period.

    The available energy is the snapshot-weighted sum of the generator's `p_max_pu`,
    i.e. its capacity factor times the hours the period's snapshots represent.
    """
    available = terms["attribute"] == "available_energy"
    if not available.any():
        return terms
    names = terms.loc[available, "variable_name"]
    p_max_pu = network.get_switchable_as_dense("Generator", "p_max_pu")[names]
    mwh_per_mw = p_max_pu.mul(_period_generator_weights(network, period), axis=0).sum()
    terms = terms.copy()
    terms.loc[available, "coefficient"] *= names.map(mwh_per_mw).to_numpy()
    terms.loc[available, "attribute"] = "p_nom"
    return terms


def _weighted_energy(
    network: pypsa.Network, terms: pd.DataFrame, period: int
) -> linopy.LinearExpression:
    """Sums coefficient x dispatch (MWh) over the investment period's snapshots.

    Dispatch is weighted by the generator snapshot weightings, which scale the
    period's snapshots to one year, so the sum is an annual energy.
    """
    weights = _period_generator_weights(network, period)
    energy = 0
    for component, group in terms.groupby("component"):
        p = network.model.variables[f"{component}-p"].loc[
            :, group["variable_name"].to_list()
        ]
        # Built with the variable's own coords so xarray aligns rather than clashing
        # with linopy's snapshot MultiIndex.
        mwh_factors = xr.DataArray(
            np.outer(weights, group["coefficient"].to_numpy()),
            coords=p.coords,
            dims=p.dims,
        )
        energy = energy + (p * mwh_factors).sum()
    return energy


def _add_custom_constraints(
    network: pypsa.Network,
    custom_constraints_rhs: pd.DataFrame,
    custom_constraints_lhs: pd.DataFrame,
):
    """Adds constrains defined in `custom_constraints_lhs.csv` and
    `custom_constraints_rhs.csv` in the `path_to_pypsa_inputs` directory
    to the `pypsa.Network`.

    Args:
        network: The `pypsa.Network` object
        custom_constraints_rhs: `pd.DataFrame` specifying custom constraint RHS values,
            has two columns 'constraint_name' and 'rhs'.
        custom_constraints_lhs: `pd.DataFrame` specifying custom constraint LHS values.
            The DataFrame has five columns 'constraint_name', 'variable_name',
            'component', 'attribute', and 'coefficient'. The 'component' specifies
            whether the LHS variable belongs to a `PyPSA` 'Bus', 'Generator', 'Link',
            etc. The 'variable_name' specifies the name of the `PyPSA` component, and
            the 'attribute' specifies the attribute of the component that the variable
            belongs to i.e. 'p_nom', 's_nom', etc. Two attributes sum over the
            snapshots of the constraint's 'investment_period' (an optional RHS
            column): 'energy' is a Generator's or Link's annual dispatch (MWh), and
            'available_energy' is a Generator's p_nom times its available energy
            per MW (see `_convert_available_energy_to_capacity`).

    Returns: None
    """
    lhs = custom_constraints_lhs
    rhs = custom_constraints_rhs

    for index, row in rhs.iterrows():
        constraint_name = row["constraint_name"]
        # The concatenated LHS tables can repeat index labels, which label-based
        # assignment in _fixed_capacity cannot resolve.
        constraint_lhs = lhs[lhs["constraint_name"] == constraint_name].reset_index(
            drop=True
        )
        period = row.get("investment_period")
        constraint_lhs = _convert_available_energy_to_capacity(
            network, constraint_lhs, period
        )

        # Non-extendable capacity is a constant, not a variable, so move it to the RHS.
        fixed_capacity = _fixed_capacity(network, constraint_lhs)
        constraint_rhs = row["rhs"] - fixed_capacity.sum()
        constraint_lhs = constraint_lhs[fixed_capacity.isna()]
        is_energy = constraint_lhs["attribute"] == "energy"
        energy_terms = constraint_lhs[is_energy]
        constraint_lhs = constraint_lhs[~is_energy]

        # Retrieve the variable objects needed on the constraint lhs from the linopy
        # model used by the pypsa.Network
        model_variables = constraint_lhs.apply(
            lambda lhs_var: _get_variables(
                network.model,
                lhs_var["variable_name"],
                lhs_var["component"],
                lhs_var["attribute"],
            ),
            axis=1,
            # Keeps the result a Series when every term is an energy term or constant.
            result_type="reduce",
        )

        # Some variables may not be present in the modeled so these a filtered out.
        # variables that couldn't be found are logged in _get_variables so this doesn't
        # result in 'silent failure'.
        retrieved_vars = ~model_variables.isna()
        model_variables = model_variables.loc[retrieved_vars]
        coefficients = constraint_lhs.loc[retrieved_vars, "coefficient"]

        x = tuple(zip(coefficients, model_variables))
        linear_expression = 0
        if x:
            linear_expression = network.model.linexpr(*x)
        if not energy_terms.empty:
            linear_expression = linear_expression + _weighted_energy(
                network, energy_terms, period
            )
        if row["constraint_type"] == "<=":
            network.model.add_constraints(
                linear_expression <= constraint_rhs, name=constraint_name
            )
        elif row["constraint_type"] == ">=":
            network.model.add_constraints(
                linear_expression >= constraint_rhs, name=constraint_name
            )
        elif row["constraint_type"] == "==":
            network.model.add_constraints(
                linear_expression == constraint_rhs, name=constraint_name
            )
        else:
            raise ValueError(
                f"{row['constraint_type']} is not a valid constraint type."
            )
