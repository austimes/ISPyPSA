"""Plot the social licence premium the campaign charges, in the form the model implements it.

Two panels. The left panel is renewable energy zone (REZ) generation above the published resource limit: today the model
charges AEMO's violation penalty on unlimited megawatts, and the campaign replaces that with two bounded tranches priced
against the REZ's own new-entrant variable renewable energy (VRE) cost. The right panel is REZ and corridor transmission
above published headroom, priced against each link's own annuitised cost, with the flat landholder payment adder that
applies from the first megawatt. Both are drawn for a median component; the spread across components is in ``research.md``.

Run with ``uv run --with kaleido python analysis/research/social_licence_premium/plot_social_licence_premium.py``; writes
``social_licence_premium.html`` and ``social_licence_premium.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

_OUTPUT_STEM = Path(__file__).with_name("social_licence_premium")

# AEMO's REZ resource limit violation penalty of A$0.3M/MW, annuitised at the 3.0% regulated transmission WACC over 30
# years, which is the price every unbounded relax generator carries in the templated 2030 network.
_PENALTY = 15_305.78

# Median annuitised cost of a new-entrant onshore wind or large-scale solar candidate in a REZ, A$/MW/yr, over the 39
# REZs that have candidates in the templated 2030 network.
_MEDIAN_VRE_COST = 301_823.0

# Median annuitised cost of an expandable link in the same network, A$/MW/yr, by link type.
_MEDIAN_LINK_COST = {"REZ transmission": 35_689.0, "Sub-region corridors": 18_781.0}

# Flat landholder payment adder on a median REZ link in New South Wales or Victoria, A$/MW/yr.
_LANDHOLDER_ADDER = 1_524.0

# Premium on the option's own cost, by tranche, as (lower bound, upper bound, rate) in multiples of the published limit.
_TRANCHES = ((1.0, 2.0, 0.15), (2.0, 4.0, 0.60))

_SERIES_COLOUR = {"REZ transmission": "#1f77b4", "Sub-region corridors": "#e4572e"}

_ANNOTATION = (
    "Left: each soft REZ resource limit's unbounded relax generator becomes two bounded tranches, one published limit "
    "wide at the penalty plus 15% of the<br>"
    "REZ's median new-entrant VRE cost and two more at the penalty plus 60%. The scaled land-use limit is the hard "
    "ceiling at 4x. Right: each expansion<br>"
    "link gets one published headroom at +0%, one at +15% and the rest to its 4x expansion limit at +60% of its own "
    "annuitised cost, plus a flat landholder<br>"
    "payment adder from the first megawatt. Percentages are AEMO's own: 15% is its transmission cost impost for low "
    "social licence and 60% the top of its<br>"
    "REZ generation uplift graduated by private land parcel density."
)


def _step_points(base: float, floor: float) -> tuple[list[float], list[float]]:
    """Build the staircase of relaxation factor against price for one base cost and one floor price.

    Each tranche contributes a riser at its lower bound and a flat tread to its upper bound, so the price a megawatt pays
    is read off the tread it falls under rather than interpolated between tranches.
    """
    factors = [0.0, _TRANCHES[0][0]]
    prices = [floor, floor]
    for start, end, rate in _TRANCHES:
        factors += [start, end]
        prices += [floor + base * rate, floor + base * rate]
    return factors, prices


def _add_generation_panel(figure: go.Figure) -> None:
    """Draw the REZ generation relax tranches against what the model charges today."""
    factors, prices = _step_points(_MEDIAN_VRE_COST, _PENALTY)
    figure.add_trace(
        go.Scatter(
            x=factors,
            y=prices,
            name="Campaign tranches, median REZ",
            mode="lines",
            line={"color": "#1f77b4", "width": 3},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, 4.0],
            y=[_PENALTY, _PENALTY],
            name="AEMO penalty today, unlimited MW",
            mode="lines",
            line={"color": "#7f7f7f", "width": 2, "dash": "dot"},
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, 4.0],
            y=[_MEDIAN_VRE_COST] * 2,
            name="Median new-entrant VRE annuitised cost",
            mode="lines",
            line={"color": "#444444", "width": 2, "dash": "dash"},
        ),
        row=1,
        col=1,
    )


def _add_transmission_panel(figure: go.Figure) -> None:
    """Draw the REZ and corridor link tranches and the flat landholder payment adder."""
    for name, base in _MEDIAN_LINK_COST.items():
        factors, prices = _step_points(base, _LANDHOLDER_ADDER)
        figure.add_trace(
            go.Scatter(
                x=factors,
                y=prices,
                name=f"{name}, median link",
                mode="lines",
                line={"color": _SERIES_COLOUR[name], "width": 3},
            ),
            row=1,
            col=2,
        )
    figure.add_trace(
        go.Scatter(
            x=[0.0, 4.0],
            y=[_LANDHOLDER_ADDER] * 2,
            name="Landholder payments, NSW and Victoria",
            mode="lines",
            line={"color": "#2ca02c", "width": 2, "dash": "dot"},
        ),
        row=1,
        col=2,
    )


def build_figure() -> go.Figure:
    """Assemble the two implemented step functions side by side."""
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(
            "REZ generation above the published resource limit",
            "REZ and corridor transmission above published headroom",
        ),
        horizontal_spacing=0.10,
    )
    _add_generation_panel(figure)
    _add_transmission_panel(figure)
    figure.update_xaxes(
        title_text="capacity as a multiple of AEMO's published limit",
        range=[0, 4.2],
        dtick=1,
    )
    figure.update_yaxes(title_text="price charged (A$2025 per MW per year)")
    figure.update_layout(
        title="Social licence premium as implemented: bounded tranches in place of a free ceiling lift",
        template="plotly_white",
        width=1250,
        height=780,
        legend={"orientation": "h", "yanchor": "top", "y": -0.18, "x": 0},
        margin={"b": 330},
    )
    figure.add_annotation(
        text=_ANNOTATION,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.60,
        showarrow=False,
        align="left",
        font={"size": 11, "color": "#555555"},
    )
    return figure


def main() -> None:
    """Build the figure and write it as HTML and PNG beside this script."""
    figure = build_figure()
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)


if __name__ == "__main__":
    main()
