"""Derive ShARP's current-policy grid supply as a dashboard reference, with its clean ladder converted approximately to emissions intensity.

Reads five files of the ShARP ``generate_grid_electricity`` role from the ``austimes/sharp`` GitHub repository at a pinned commit, through
the authenticated ``gh`` command line, and keeps the ``current_policy_clean_transition`` future for 2030 to 2050. Each clean-ladder point's
renewable fraction becomes an intensity by assuming the non-renewable remainder keeps the planned year's emissions factor. Columns prefixed
``common_`` restate ShARP's national delivered quantities and costs on the campaign's basis: NEM operational demand in real June 2025
dollars, with ``common_futures_min_twh`` and ``common_futures_max_twh`` the range over every ShARP grid future.

Run with ``uv run --with kaleido python analysis/research/sharp_grid_reference/plot_sharp_grid_reference.py``; writes
``sharp_grid_reference.csv``, ``.html`` and ``.png`` beside this script.
"""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

_SHARP_COMMIT = "eaf1ca27"
_ROLE_PATH = "library/roles/generate_grid_electricity"
_METHOD = "electricity__grid_supply__current_policy_clean_transition"
_YEARS = [2030, 2035, 2040, 2045, 2050]
#: ShARP extends every clean ladder to a nominal 99% renewable endpoint at its final published interval's incremental price.
_LADDER_END = 0.99
_OUTPUT_STEM = Path(__file__).with_name("sharp_grid_reference")
#: ShARP's A052 factors from NEM source generation to national delivered electricity (S007).
_GEOGRAPHIC_FACTOR = 1.3
_DELIVERY_FACTOR = 0.7914939324516337
#: Operational demand as a share of NEM generation excluding rooftop, the demand plan's authored factor (A008).
_OPERATIONAL_SHARE = 0.97
_QUANTITY_COLUMNS = ["planned_twh", "futures_min_twh", "futures_max_twh"]
#: ABS All groups CPI, weighted average of eight capital cities (series A2325846C): June quarter 2025 over the 2024 mean (A009).
_CPI_2024_TO_JUN_2025 = 141.7 / ((137.4 + 138.8 + 139.1 + 139.4) / 4)


def _read_sharp(name: str) -> pd.DataFrame:
    """One role CSV from the pinned ShARP commit, restricted to the milestone years."""
    url = f"repos/austimes/sharp/contents/{_ROLE_PATH}/{name}?ref={_SHARP_COMMIT}"
    text = subprocess.run(
        ["gh", "api", url, "-H", "Accept: application/vnd.github.raw"],
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout
    frame = pd.read_csv(StringIO(text))
    return frame[frame["year"].isin(_YEARS)]


def _planned() -> pd.DataFrame:
    """Planned quantity, renewable share, non-fuel cost, intensity and total fuel input per year for the clean-transition future."""
    states = _read_sharp("overflow_supply_pathway_states.csv")
    methods = _read_sharp("method_years.csv")
    states, methods = (
        frame[frame["method_id"].eq(_METHOD)].set_index("year")
        for frame in (states, methods)
    )
    return pd.DataFrame(
        {
            "planned_twh": states["planned_quantity"],
            "planned_renewable_fraction": states["planned_renewable_fraction"],
            "planned_cost_aud_per_mwh": methods["output_cost_per_unit"],
            "planned_t_co2e_per_mwh": methods["energy_emissions_by_pollutant"].map(
                lambda cell: json.loads(cell)[0]["value"]
            ),
            "planned_pj_per_twh": methods["input_coefficients"].map(
                lambda cell: sum(json.loads(cell))
            ),
        }
    )


def _extend_ladder(points: pd.DataFrame) -> pd.DataFrame:
    """Add the nominal 99% endpoint, priced along the last published segment's slope."""
    last, end = points.iloc[-2], points.iloc[-1]
    slope = (end["ladder_cost_aud_per_mwh"] - last["ladder_cost_aud_per_mwh"]) / (
        end["ladder_renewable_fraction"] - last["ladder_renewable_fraction"]
    )
    cost = end["ladder_cost_aud_per_mwh"] + slope * (
        _LADDER_END - end["ladder_renewable_fraction"]
    )
    endpoint = {
        "ladder_point": "nominal_99",
        "ladder_renewable_fraction": _LADDER_END,
        "ladder_cost_aud_per_mwh": cost,
    }
    return pd.concat([points, pd.DataFrame([endpoint])], ignore_index=True)


def _ladder() -> pd.DataFrame:
    """Every year's clean ladder of renewable fraction against average cost, extended to 99%."""
    curve = _read_sharp("overflow_supply_cleanliness_curve.csv").sort_values(
        ["year", "point_order"]
    )
    curve = curve.rename(
        columns={
            "point_id": "ladder_point",
            "renewable_fraction": "ladder_renewable_fraction",
            "average_cost_per_unit": "ladder_cost_aud_per_mwh",
        }
    )
    columns = ["ladder_point", "ladder_renewable_fraction", "ladder_cost_aud_per_mwh"]
    return pd.concat(
        {
            year: _extend_ladder(points[columns])
            for year, points in curve.groupby("year")
        },
        names=["year"],
    ).droplevel(1)


def _share_cost(ladder: pd.DataFrame, share: float) -> float:
    """One year's ladder cost interpolated at a renewable share."""
    return float(
        np.interp(
            share,
            ladder["ladder_renewable_fraction"],
            ladder["ladder_cost_aud_per_mwh"],
        )
    )


def reference_table() -> pd.DataFrame:
    """Per year and ladder point: the planned state, the futures range, the converted ladder, the extra-MWh price and their common basis."""
    planned = _planned()
    planned["residual_t_co2e_per_mwh"] = planned["planned_t_co2e_per_mwh"] / (
        1 - planned["planned_renewable_fraction"]
    )
    ladder = _ladder()
    planned["planned_share_ladder_cost_aud_per_mwh"] = [
        _share_cost(ladder.loc[year], share)
        for year, share in planned["planned_renewable_fraction"].items()
    ]
    premiums = _read_sharp("overflow_supply_scale_premiums.csv").set_index("year")[
        "overflow_scale_premium_per_unit"
    ]
    planned["scale_premium_aud_per_mwh"] = premiums
    planned["extra_mwh_price_aud_per_mwh"] = (
        planned["planned_share_ladder_cost_aud_per_mwh"] + premiums
    )
    table = planned.join(_futures_range()).join(ladder).reset_index()
    table["ladder_t_co2e_per_mwh"] = (1 - table["ladder_renewable_fraction"]) * table[
        "residual_t_co2e_per_mwh"
    ]
    return _common_basis(table).round(5)


def _futures_range() -> pd.DataFrame:
    """Lowest and highest planned quantity over every ShARP grid future, per year, in national delivered TWh."""
    states = _read_sharp("overflow_supply_pathway_states.csv")
    quantity = states.groupby("year")["planned_quantity"]
    return pd.DataFrame(
        {"futures_min_twh": quantity.min(), "futures_max_twh": quantity.max()}
    )


def _common_basis(table: pd.DataFrame) -> pd.DataFrame:
    """Every A$/MWh column per MWh of NEM operational demand in June 2025 dollars, and every TWh column as NEM operational demand."""
    cost = _DELIVERY_FACTOR / _OPERATIONAL_SHARE * _CPI_2024_TO_JUN_2025
    energy = _OPERATIONAL_SHARE / (_GEOGRAPHIC_FACTOR * _DELIVERY_FACTOR)
    common = {
        **{f"common_{c}": table[c] * cost for c in table.filter(like="aud_per_mwh")},
        **{f"common_{c}": table[c] * energy for c in _QUANTITY_COLUMNS},
    }
    return table.assign(**common)


def build_figure(table: pd.DataFrame) -> go.Figure:
    """Each year's converted ladder as cost against intensity, with the planned point marked on it."""
    figure = go.Figure()
    for year, rows in table.groupby("year"):
        figure.add_trace(
            go.Scatter(
                x=rows["ladder_t_co2e_per_mwh"],
                y=rows["ladder_cost_aud_per_mwh"],
                name=f"{year} ladder",
                mode="lines+markers",
            )
        )
        planned = rows.iloc[0]
        figure.add_trace(
            go.Scatter(
                x=[planned["planned_t_co2e_per_mwh"]],
                y=[planned["planned_share_ladder_cost_aud_per_mwh"]],
                name=f"{year} planned",
                mode="markers",
                marker={"symbol": "x", "size": 11, "color": "black"},
            )
        )
    return figure.update_layout(
        title="ShARP current-policy clean ladder, renewable share converted to emissions intensity (approximate)",
        xaxis_title="t CO2e/MWh (non-renewable remainder at the planned year's emissions factor)",
        yaxis_title="ladder average cost (A$2024/MWh)",
        xaxis_type="log",
        template="plotly_white",
        width=1100,
        height=700,
    )


def main() -> None:
    """Write the reference table as CSV and the figure as HTML and PNG beside this script."""
    table = reference_table()
    table.to_csv(_OUTPUT_STEM.with_suffix(".csv"), index=False, encoding="utf-8")
    figure = build_figure(table)
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)
    print(table.to_string())


if __name__ == "__main__":
    main()
