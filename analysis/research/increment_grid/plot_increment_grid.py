"""Plot the increment grid's two axes against the Step Change base chain they scale.

The increment grid re-solves each milestone year at a set of demand levels and a set of intensity levels, both
multiples of the base chain's own value for that year. This script reads the grid's levels and the base chain's
per-year knots straight from ``analysis/hpc/demand_plan.json``, so the figure cannot drift from what a launch would
build. It draws the intensity axis as the absolute cap intensity each level implies, log scaled with the base chain's
own path (``i1000``) highlighted, and the demand axis as the source load each level implies, with the base chain's own
path (``d100``) highlighted.

Run with ``uv run --with kaleido python analysis/research/increment_grid/plot_increment_grid.py``; writes
``increment_grid.html`` and ``increment_grid.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.hpc.increments import base_trajectory

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("increment_grid")

#: Base chain's own level on each axis, drawn highlighted rather than faint.
_BASE_INTENSITY_LEVEL = "i1000"
_BASE_DEMAND_LEVEL = "d100"

_HIGHLIGHT_COLOUR = "#1f4e79"
_FAINT_COLOURS = [
    "#9fb6cc",
    "#b7c9a8",
    "#d9a441",
    "#c46666",
    "#8a6bab",
    "#4f9d9d",
    "#c98bbf",
    "#7f7f7f",
]


def _load_plan() -> dict:
    """The demand plan JSON the increment grid and the base chain are built from."""
    return json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))


def _faint_colours(keys: list[str], highlight: str) -> dict[str, str]:
    """One colour per level key, cycling the faint palette and reserving the highlight colour for the base level."""
    others = [key for key in keys if key != highlight]
    colours = {
        key: _FAINT_COLOURS[i % len(_FAINT_COLOURS)] for i, key in enumerate(others)
    }
    colours[highlight] = _HIGHLIGHT_COLOUR
    return colours


def _level_trace(
    years: list[int],
    values: list[float],
    key: str,
    factor: float,
    colour: str,
    highlight: bool,
) -> go.Scatter:
    """One level's line across the increment years, bold if it is the base chain's own level."""
    return go.Scatter(
        x=years,
        y=values,
        name=f"{key} ({factor:g}x)",
        mode="lines+markers",
        line={"color": colour, "width": 3 if highlight else 1.5},
        marker={"color": colour, "size": 7 if highlight else 5},
    )


def _intensity_traces(plan: dict, years: list[int]) -> list[go.Scatter]:
    """One trace per intensity level: the level factor times the base chain's own cap intensity, by year."""
    grid = plan["increment_grid"]
    base_intensity = plan["cap_intensity_t_per_mwh"]
    colours = _faint_colours(list(grid["intensity_levels"]), _BASE_INTENSITY_LEVEL)
    return [
        _level_trace(
            years,
            [base_intensity[str(year)] * factor for year in years],
            key,
            factor,
            colours[key],
            key == _BASE_INTENSITY_LEVEL,
        )
        for key, factor in grid["intensity_levels"].items()
    ]


def _demand_traces(plan: dict, years: list[int]) -> list[go.Scatter]:
    """One trace per demand level: the level factor times the base chain's own source load, by year."""
    grid = plan["increment_grid"]
    _, knots = base_trajectory(plan)
    colours = _faint_colours(list(grid["demand_levels"]), _BASE_DEMAND_LEVEL)
    return [
        _level_trace(
            years,
            [knots[str(year)] * factor for year in years],
            key,
            factor,
            colours[key],
            key == _BASE_DEMAND_LEVEL,
        )
        for key, factor in grid["demand_levels"].items()
    ]


def build_figure() -> go.Figure:
    """Assemble the two-panel figure: cap intensity by year per intensity level, then source load per demand level."""
    plan = _load_plan()
    years = plan["increment_years"]
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=[
            "cap intensity by level (t CO2e/MWh generated, log scale)",
            "source NEM load by level (TWh)",
        ],
    )
    for trace in _intensity_traces(plan, years):
        figure.add_trace(trace, row=1, col=1)
    for trace in _demand_traces(plan, years):
        figure.add_trace(trace, row=1, col=2)
    figure.update_yaxes(type="log", row=1, col=1)
    figure.update_xaxes(title_text="increment year", tickvals=years, row=1, col=1)
    figure.update_xaxes(title_text="increment year", tickvals=years, row=1, col=2)
    figure.update_layout(
        title="The increment grid: intensity and demand levels against the Step Change base chain",
        template="plotly_white",
        width=1400,
        height=700,
        legend={"orientation": "h", "yanchor": "top", "y": -0.25, "x": 0},
        margin={"b": 200},
    )
    figure.add_annotation(
        text=(
            f"Each level scales the base chain's own value for that year: intensity levels scale "
            f"cap_intensity_t_per_mwh, demand levels scale the base trajectory's source load. "
            f"{_BASE_INTENSITY_LEVEL} and {_BASE_DEMAND_LEVEL} (both 1.0x, highlighted) are the base chain's own path."
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=-0.16,
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
