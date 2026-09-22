"""Plot the build rate premium the campaign charges on new capacity, straight from the file the model reads.

One panel per carrier group: cumulative new-build megawatts inside one five-year period against the adder in Australian
dollars per megawatt per year, drawn as the step function the tranche block enforces. One line per investment period, so a
reader can see both the widths falling as AEMO's planned build rate falls and the adders falling with capital cost. The
uncapped backstop tranche has no width, so it is drawn as a tread running to twice the second tranche's cumulative cap.
Derivations and sources are in ``research.md``.

Run with ``uv run --with kaleido python analysis/research/build_rate_premium/plot_build_rate_premium.py``; writes
``build_rate_premium.html`` and ``build_rate_premium.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_PREMIUM_CSV = (
    Path(__file__).parents[2] / "model" / "data" / "build_rate_premiums_central.csv"
)
_OUTPUT_STEM = Path(__file__).with_name("build_rate_premium")

#: Panel order, chosen so the two largest carriers lead and storage sits together at the end.
_GROUPS = ("Wind", "Solar", "Gas", "Battery", "Water")

#: One colour per investment period, darkening as the horizon advances.
_PERIOD_COLOUR = {
    2030: "#1f77b4",
    2035: "#4c9f70",
    2040: "#e4a11b",
    2045: "#e4572e",
    2050: "#7b2d8e",
}

_ANNOTATION = (
    "Widths: first tranche is the Step Change five-year capacity addition (floored at the horizon average), second is "
    "the Accelerated Transition addition<br>"
    "or twice the first, whichever is larger. Adders: +17.5% and +45% of the group's annuitised capital cost in that "
    "year. Every width is a five-year total,<br>"
    "and each period is charged only the megawatts built in that period, so the premium prices compression where it "
    "occurs."
)


def _ladder_steps(tranches: pd.DataFrame) -> tuple[list[float], list[float]]:
    """Build the staircase of cumulative megawatts against adder for one group and period.

    Each tranche contributes a riser at its lower bound and a tread to its cumulative cap; the uncapped backstop runs to
    twice the last capped bound so the reader can see it continues rather than ends.
    """
    steps_mw: list[float] = [0.0]
    steps_adder: list[float] = [float(tranches["adder_$/mw/yr"].iloc[0])]
    lower = 0.0
    for cap, adder in zip(tranches["cap_mw"], tranches["adder_$/mw/yr"]):
        upper = float(cap) if pd.notna(cap) else lower * 2
        steps_mw += [lower, upper]
        steps_adder += [float(adder), float(adder)]
        lower = upper
    return steps_mw, steps_adder


def _add_group_panel(
    figure: go.Figure, curve: pd.DataFrame, group: str, row: int, column: int
) -> None:
    """Draw every period's step function for one carrier group into one subplot cell."""
    for year, tranches in curve[curve["group"] == group].groupby("financial_year"):
        steps_mw, steps_adder = _ladder_steps(tranches.sort_values("adder_$/mw/yr"))
        figure.add_trace(
            go.Scatter(
                x=steps_mw,
                y=steps_adder,
                name=str(year),
                legendgroup=str(year),
                showlegend=group == _GROUPS[0],
                mode="lines",
                line={"color": _PERIOD_COLOUR[int(year)], "width": 2.5},
            ),
            row=row,
            col=column,
        )


def build_figure() -> go.Figure:
    """Assemble the per-carrier panels of the build rate premium step function."""
    curve = pd.read_csv(_PREMIUM_CSV)
    figure = make_subplots(
        rows=2,
        cols=3,
        subplot_titles=_GROUPS,
        horizontal_spacing=0.08,
        vertical_spacing=0.16,
    )
    for index, group in enumerate(_GROUPS):
        _add_group_panel(figure, curve, group, row=index // 3 + 1, column=index % 3 + 1)
    figure.update_xaxes(title_text="new build in the period (MW)")
    figure.update_yaxes(title_text="adder (A$2025 per MW per year)")
    figure.update_layout(
        title="Build rate premium charged on new capacity above AEMO's planned five-year build rate",
        template="plotly_white",
        width=1300,
        height=780,
        legend={
            "title": "investment period",
            "orientation": "h",
            "yanchor": "top",
            "y": -0.10,
            "x": 0,
        },
        margin={"b": 210},
    )
    figure.add_annotation(
        text=_ANNOTATION,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.30,
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
