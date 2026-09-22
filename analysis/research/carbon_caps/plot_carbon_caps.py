"""Plot the carbon caps the campaign solves: the base chain's per-milestone intensity and tonnage.

The base chain follows the Step Change scenario's own emissions intensity at each milestone year, and the manifest turns
each intensity into the absolute annual tonnage the solver is given against that year's source load. The increment grid's
cells are the same arithmetic at a scaled intensity and a scaled load, so they are drawn as faint points beside the base
line.

This script builds the caps with ``analysis.hpc.manifest``'s own ``build_caps_table`` against
``analysis/hpc/demand_plan.json``, so the figure cannot drift from what a launch would write.

Run with ``uv run --with kaleido python analysis/research/carbon_caps/plot_carbon_caps.py``; writes ``carbon_caps.html``
and ``carbon_caps.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.hpc.campaign_grid import BASE_CHAIN_KEY
from analysis.hpc.manifest import build_caps_table

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("carbon_caps")

# The caps table stamps the commit that built a manifest; a plot builds no manifest, so the field is filled with what it
# means here.
_NOT_A_MANIFEST_BUILD = "not-a-build"

_BASE_COLOUR = "#1f4e79"
_BRANCH_COLOUR = "#9fb6cc"

#: Field of the caps table plotted in each panel, and that panel's axis title.
_PANELS = {
    "intensity": "cap intensity (t CO2e/MWh generated)",
    "cap_t": "annual cap (t CO2e, log scale)",
}


def _caps() -> pd.DataFrame:
    """Every cap of the campaign in tonnes, built by the manifest's own arithmetic."""
    plan = json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))
    return build_caps_table(plan, _NOT_A_MANIFEST_BUILD)


def _series(
    rows: pd.DataFrame, field: str, name: str, colour: str, faint: bool, legend: bool
) -> go.Scatter:
    """One set of caps at the milestone years: a line for the base chain, points for the cells."""
    return go.Scatter(
        x=rows["year"],
        y=rows[field],
        name=name,
        legendgroup=name,
        showlegend=legend,
        mode="markers" if faint else "lines+markers",
        line={"color": colour, "width": 2},
        marker={"color": colour, "size": 6, "opacity": 0.4 if faint else 1.0},
    )


def build_figure() -> go.Figure:
    """Assemble the two-panel figure: cap intensity, then the tonnage it becomes."""
    caps = _caps()
    base = caps[caps["chain"] == BASE_CHAIN_KEY]
    cells = caps[caps["chain"] != BASE_CHAIN_KEY]
    figure = make_subplots(rows=1, cols=2, subplot_titles=list(_PANELS.values()))
    for column, field in enumerate(_PANELS, start=1):
        figure.add_trace(
            _series(cells, field, "increment cells", _BRANCH_COLOUR, True, column == 1),
            row=1,
            col=column,
        )
        figure.add_trace(
            _series(
                base, field, "Step Change base chain", _BASE_COLOUR, False, column == 1
            ),
            row=1,
            col=column,
        )
        figure.update_xaxes(
            title_text="milestone",
            tickvals=sorted(caps["year"].unique()),
            row=1,
            col=column,
        )
    figure.update_yaxes(type="log", row=1, col=2)
    figure.update_layout(
        title="The campaign's carbon caps: the Step Change base chain and its increment cells",
        template="plotly_white",
        width=1300,
        height=700,
        legend={"orientation": "h", "yanchor": "top", "y": -0.3, "x": 0},
        margin={"b": 240},
    )
    figure.add_annotation(
        text=(
            f"The base intensity is the Step Change scenario's own emissions intensity at each milestone, quoted on the "
            f"{base['intensity_basis'].iloc[0]} basis (emissions over<br>generation), so the solver's cap is "
            "intensity x source load x 1e6 tonnes with no delivery factor. An increment cell scales the intensity by its "
            "own<br>intensity level and the load by its own demand level, which is why the cells fan out below and around "
            "the base line."
        ),
        xref="paper",
        yref="paper",
        x=0,
        y=-0.14,
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
