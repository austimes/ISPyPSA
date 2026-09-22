"""Plot the two biomass limits the model enforces: the fuel supply curve and the capacity cap.

The left panel is the supply curve as the solver sees it, read row by row from
``analysis/model/data/biomass_supply_curve_central_held_to_2060.csv``: tranches ordered by their price adder, drawn as a step of cumulative
petajoules (PJ) against adder in Australian dollars per gigajoule. The right panel is the National Electricity Market (NEM) wide capacity
ceiling, imported from ``analysis.model.biomass_cap`` because those megawatt values live only in that module.

Run with ``uv run --with kaleido python analysis/research/biomass/plot_biomass_limits.py``; writes ``biomass_limits.html`` and
``biomass_limits.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.model.biomass_cap import _BIOMASS_CAP_MW_BY_YEAR

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUPPLY_CURVE = (
    _REPO_ROOT
    / "analysis"
    / "model"
    / "data"
    / "biomass_supply_curve_central_held_to_2060.csv"
)
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("biomass_limits")

# The curve's earliest year, plotted alongside the campaign milestones so the tranche ramp has a starting point.
_BASE_YEAR = 2025

# An unbounded tranche has a blank cap_pj; it is drawn as a step running this far past the bounded total rather than to infinity.
_BACKSTOP_OVERHANG_PJ = 60.0

# Biomass fuel drawn under the deepest cap ladder, reported in research.md: 30 PJ of byproduct at its cap plus 2.5 PJ of residues.
_FUEL_USED_UNDER_DEEPEST_CAP_PJ = 32.5

_YEAR_COLOURS = {
    2025: "#c9d6e3",
    2030: "#7fb3d5",
    2040: "#2e86c1",
    2050: "#1f4e79",
    2060: "#e4572e",
}


def _milestone_years() -> list[int]:
    """Curve years to draw: the campaign milestones plus the curve's base year."""
    plan = json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))
    return [_BASE_YEAR, *plan["milestone_years"]]


def _supply_curve() -> pd.DataFrame:
    """The supply curve as stored, ordered cheapest adder first within each financial year."""
    curve = pd.read_csv(_SUPPLY_CURVE)
    return curve.sort_values(["financial_year", "adder_$/gj"]).reset_index(drop=True)


def _ladder_steps(year_rows: pd.DataFrame) -> tuple[list[float], list[float]]:
    """Step coordinates for one year: cumulative PJ against adder, with the unbounded tranche overhanging the bounded total.

    Drawn with plotly's ``hv`` shape, so each tranche is one horizontal run at its adder and the price rises where it runs out.
    """
    sizes = year_rows["cap_pj"].fillna(_BACKSTOP_OVERHANG_PJ)
    adders = year_rows["adder_$/gj"].tolist()
    return [0.0, *sizes.cumsum()], [*adders, adders[-1]]


def _add_ladder_traces(
    figure: go.Figure, curve: pd.DataFrame, years: list[int]
) -> None:
    """Add one step line per plotted financial year to the supply-curve panel."""
    for year in years:
        quantities, prices = _ladder_steps(curve[curve["financial_year"] == year])
        figure.add_trace(
            go.Scatter(
                x=quantities,
                y=prices,
                name=f"FY{year}",
                mode="lines",
                line={"color": _YEAR_COLOURS[year], "width": 2, "shape": "hv"},
                legendgroup="curve",
            ),
            row=1,
            col=1,
        )


def _add_fuel_used_marker(figure: go.Figure) -> None:
    """Mark the fuel actually drawn under the deepest cap ladder."""
    figure.add_vline(
        x=_FUEL_USED_UNDER_DEEPEST_CAP_PJ,
        line={"color": "#b03030", "width": 2, "dash": "dash"},
        annotation_text=f"{_FUEL_USED_UNDER_DEEPEST_CAP_PJ} PJ drawn under the deepest cap",
        annotation_position="top right",
        row=1,
        col=1,
    )


def _add_capacity_cap_trace(figure: go.Figure) -> None:
    """Add the NEM-wide new-entrant biomass capacity ceiling panel."""
    figure.add_trace(
        go.Bar(
            x=list(_BIOMASS_CAP_MW_BY_YEAR),
            y=list(_BIOMASS_CAP_MW_BY_YEAR.values()),
            name="capacity cap",
            marker_color="#2e86c1",
            text=[f"{mw:,}" for mw in _BIOMASS_CAP_MW_BY_YEAR.values()],
            textposition="outside",
        ),
        row=1,
        col=2,
    )


def build_figure() -> go.Figure:
    """Assemble the two-panel biomass limits figure."""
    figure = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.6, 0.4],
        subplot_titles=(
            "Fuel supply curve: cumulative availability against price adder",
            "NEM-wide new-entrant capacity cap",
        ),
    )
    curve = _supply_curve()
    _add_ladder_traces(figure, curve, _milestone_years())
    _add_fuel_used_marker(figure)
    _add_capacity_cap_trace(figure)
    figure.update_xaxes(
        title_text="cumulative fuel availability (PJ per year)", row=1, col=1
    )
    figure.update_yaxes(
        title_text="price adder above base fuel cost (A$/GJ)",
        range=[0, curve["adder_$/gj"].max() * 1.12],
        row=1,
        col=1,
    )
    figure.update_xaxes(title_text="financial year", dtick=5, row=1, col=2)
    figure.update_yaxes(title_text="capacity cap (MW)", row=1, col=2)
    figure.update_layout(
        title="Biomass limits the model enforces: a priced fuel ladder and a capacity ceiling",
        template="plotly_white",
        width=1200,
        height=820,
        barmode="group",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.32,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 300},
    )
    figure.add_annotation(
        text=(
            "The dearest tranche is unbounded in the file, so its step is drawn "
            f"{_BACKSTOP_OVERHANG_PJ:.0f} PJ past the bounded total rather than to infinity.<br>"
            'FY2060 repeats FY2055, which is what "held to 2060" in the file name means, so the FY2050 and FY2060 ladders coincide.'
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=-0.18,
        yanchor="top",
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
