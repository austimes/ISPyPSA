"""Tests for the two priced capacity curves.

The load-bearing behaviours are that the tranche block really prices the second step (a solved LP,
not a hand-checked coefficient), that the published headroom is looked up by the right key per link
class and undone by the run's relaxation factor, and that the REZ relaxation generator becomes two
bounded generators with two matching left-hand side rows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pypsa
import pytest

from analysis.env import MODEL_DATA
from analysis.model.capacity_tranches import (
    _build_rate_tranches,
    _link_headroom_mw,
    add_priced_tranches,
    campaign_tranches,
    load_build_rate_curve,
    tranche_usage,
)
from analysis.model.relaxation_tranches import apply as relaxation_tranches_apply

# ---------------------------------------------------------------------------
# The tranche block, solved
# ---------------------------------------------------------------------------


def _one_bus_network(load_mw: float, generator: str = "wind") -> pypsa.Network:
    """A single-period, single-snapshot network whose one extendable generator must serve `load_mw`."""
    network = pypsa.Network()
    network.set_snapshots(pd.MultiIndex.from_tuples([(2030, "now")]))
    network.investment_periods = [2030]
    network.add("Bus", "node")
    network.add("Load", "load", bus="node", p_set=load_mw)
    network.add(
        "Generator",
        generator,
        bus="node",
        p_nom_extendable=True,
        build_year=2030,
        lifetime=30,
        capital_cost=100.0,
        marginal_cost=0.0,
    )
    network.optimize.create_model(multi_investment_periods=True)
    return network


def _two_tranches() -> tuple[pd.DataFrame, pd.DataFrame]:
    """A 50 MW step at A$5/MW/yr and an unbounded step at A$20/MW/yr, over the one generator."""
    tranches = pd.DataFrame(
        {
            "kind": ["build_rate", "build_rate"],
            "group": ["Wind", "Wind"],
            "period": [2030, 2030],
            "tranche": [1, 2],
            "width_mw": [50.0, np.inf],
            "adder": [5.0, 20.0],
        }
    )
    members = pd.DataFrame(
        {
            "kind": ["build_rate"],
            "group": ["Wind"],
            "component": ["Generator"],
            "name": ["wind"],
        }
    )
    return tranches, members


@pytest.mark.parametrize(
    ("load_mw", "expected_mw", "expected_premium"),
    [(40.0, [40.0, 0.0], [200.0, 0.0]), (80.0, [50.0, 30.0], [250.0, 600.0])],
)
def test_tranche_usage_fills_the_cheap_step_first(
    load_mw, expected_mw, expected_premium
):
    network = _one_bus_network(load_mw)
    tranches, members = _two_tranches()

    add_priced_tranches(network, tranches, members)
    network.optimize.solve_model(solver_name="highs")
    result = tranche_usage(network, tranches)

    expected = tranches.assign(mw_used=expected_mw, premium_aud_per_yr=expected_premium)
    pd.testing.assert_frame_equal(result, expected, check_exact=False, rtol=1e-5)


@pytest.mark.parametrize(
    ("load_mw", "expected_mw", "expected_premium"),
    [(8.0, [8.0, 0.0], [0.0, 0.0]), (15.0, [10.0, 5.0], [0.0, 35.0])],
)
def test_pipeline_build_above_the_allowance_pays_the_rush_charge(
    load_mw, expected_mw, expected_premium, csv_str_to_df
):
    network = _one_bus_network(load_mw, generator="wind_sq_2030")
    tables = {
        "new_entrant_generators": csv_str_to_df("""
            generator,  status
            wind_sq,    New__Entrant
        """),
        "new_entrant_batteries": pd.DataFrame(columns=["storage_name", "status"]),
    }

    tranches, members = campaign_tranches(
        network,
        tables,
        2030,
        None,
        None,
        1.0,
        1.0,
        (10.0, 5.0),
        (7.0, 3.0),
        (25.0, 6.0),
    )
    add_priced_tranches(network, tranches, members)
    network.optimize.solve_model(solver_name="highs")
    result = tranche_usage(network, tranches)

    expected = csv_str_to_df("""
        kind,           group,                period,  tranche,  width_mw,  adder
        pipeline_rush,  pipeline_generation,  2030,    1,        10.0,      0.0
        pipeline_rush,  pipeline_generation,  2030,    2,        15.0,      7.0
    """).assign(mw_used=expected_mw, premium_aud_per_yr=expected_premium)
    pd.testing.assert_frame_equal(
        result, expected, check_exact=False, rtol=1e-5, check_dtype=False
    )


# ---------------------------------------------------------------------------
# Published headroom per expandable link
# ---------------------------------------------------------------------------


def test_link_headroom_sums_a_flow_path_s_options_and_keys_a_rez_link_on_bus0(
    csv_str_to_df,
):
    links = csv_str_to_df("""
        name,             isp_name,  isp_type,   bus0,  bus1,  p_nom_extendable,  build_year
        CNSW-SNW_exp,     CNSW-SNW,  flow_path,  CNSW,  SNW,   True,              2030
        N2-CNSW_exp,      N2-CNSW,   rez,        N2,    CNSW,  True,              2030
        CNSW-SNW_existing,CNSW-SNW,  flow_path,  CNSW,  SNW,   False,             2029
    """).set_index("name")
    tables = {
        "flow_path_expansion_costs": csv_str_to_df("""
            flow_path,  option,     additional_network_capacity_mw
            CNSW-SNW,   Option__1,  1200.0
            CNSW-SNW,   Option__2,  2800.0
        """),
        "rez_transmission_expansion_costs": csv_str_to_df("""
            rez_constraint_id,  option,     additional_network_capacity_mw
            N2,                 Option__1,  2000.0
        """),
    }

    result = _link_headroom_mw(
        links, tables, 2030, rez_factor=4.0, flow_path_factor=4.0
    )

    expected = pd.Series(
        [1000.0, 500.0], index=["CNSW-SNW_exp", "N2-CNSW_exp"], name=None
    )
    pd.testing.assert_series_equal(result, expected, check_names=False)


# ---------------------------------------------------------------------------
# The shipped build-rate curve
# ---------------------------------------------------------------------------


def test_shipped_build_rate_curve_validates_and_rises_to_one_uncapped_step_per_carrier(
    csv_str_to_df,
):
    curve = load_build_rate_curve(
        MODEL_DATA / "build_rate_premiums_central.csv", [2030, 2035, 2040, 2045, 2050]
    )

    result = _build_rate_tranches(curve, 2030)

    summary = (
        result.groupby("group")
        .agg(
            steps=("tranche", "size"),
            uncapped=("width_mw", lambda width: int(np.isinf(width).sum())),
            rising=("adder", lambda adder: bool(adder.diff().fillna(0).ge(0).all())),
        )
        .reset_index()
    )
    expected = csv_str_to_df("""
        group,    steps,  uncapped,  rising
        Battery,  3,      1,         True
        Gas,      3,      1,         True
        Solar,    3,      1,         True
        Water,    3,      1,         True
        Wind,     3,      1,         True
    """)
    pd.testing.assert_frame_equal(summary, expected)


# ---------------------------------------------------------------------------
# Relaxation-generator explosion
# ---------------------------------------------------------------------------


def test_relaxation_tranches_gives_two_bounded_generators_and_two_lhs_rows(
    csv_str_to_df,
):
    pypsa_friendly = {
        "custom_constraints_generators": csv_str_to_df("""
            name,                     isp_name,      bus,                            p_nom,  p_nom_extendable,  build_year,  lifetime,  capital_cost
            N2_WH_resource_relax_2030,N2_WH_resource,bus_for_custom_constraint_gens, 0.0,    True,              2030,        30,        15306.0
            SWQLD1_exp_2030,          SWQLD1,        bus_for_custom_constraint_gens, 0.0,    True,              2030,        30,        500.0
        """),
        "custom_constraints_rhs": csv_str_to_df("""
            constraint_name,         constraint_type,  rhs
            N2_WH_resource,          <=,               1000.0
            SWQLD1_expansion_limit,  <=,               400.0
        """),
        "custom_constraints_lhs": csv_str_to_df("""
            constraint_name,  variable_name,             component,  attribute,  coefficient
            N2_WH_resource,   wind_high_n2_2030,         Generator,  p_nom,      1.0
            N2_WH_resource,   wind_high_n2_alt_2030,     Generator,  p_nom,      1.0
            N2_WH_resource,   N2_WH_resource_relax_2030, Generator,  p_nom,      -1.0
            SWQLD1_expansion_limit, SWQLD1_exp_2030,     Generator,  p_nom,      -1.0
        """),
        "generators": csv_str_to_df("""
            name,                   capital_cost
            wind_high_n2_2030,      100000.0
            wind_high_n2_alt_2030,  140000.0
        """),
    }

    result = relaxation_tranches_apply(pypsa_friendly, (0.15, 0.60))

    expected_generators = csv_str_to_df("""
        name,                      isp_name,       bus,                             p_nom,  p_nom_extendable,  build_year,  lifetime,  capital_cost,  p_nom_max
        SWQLD1_exp_2030,           SWQLD1,         bus_for_custom_constraint_gens,  0.0,    True,              2030,        30,        500.0,
        N2_WH_resource_relax1_2030,N2_WH_resource, bus_for_custom_constraint_gens,  0.0,    True,              2030,        30,        33306.0,       1000.0
        N2_WH_resource_relax2_2030,N2_WH_resource, bus_for_custom_constraint_gens,  0.0,    True,              2030,        30,        87306.0,       2000.0
    """)
    pd.testing.assert_frame_equal(
        result["custom_constraints_generators"],
        expected_generators[result["custom_constraints_generators"].columns],
    )

    expected_lhs = csv_str_to_df("""
        constraint_name,  variable_name,              component,  attribute,  coefficient
        N2_WH_resource,   wind_high_n2_2030,          Generator,  p_nom,      1.0
        N2_WH_resource,   wind_high_n2_alt_2030,      Generator,  p_nom,      1.0
        SWQLD1_expansion_limit, SWQLD1_exp_2030,      Generator,  p_nom,      -1.0
        N2_WH_resource,   N2_WH_resource_relax1_2030, Generator,  p_nom,      -1.0
        N2_WH_resource,   N2_WH_resource_relax2_2030, Generator,  p_nom,      -1.0
    """)
    pd.testing.assert_frame_equal(result["custom_constraints_lhs"], expected_lhs)
