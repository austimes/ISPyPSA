"""Plot the carbon cap ladder as the absolute annual tonnages the solver is actually given.

The manifest converts an intensity rung into a tonnage against that trajectory's source load, so the same named rung is a different physical
budget on each trajectory. This script therefore builds the caps with ``analysis.hpc.manifest``'s own ``build_caps_table`` against
``analysis/hpc/demand_plan.json``, and facets by trajectory so the spread across trajectories is visible next to the spread across rungs.

Run with ``uv run --with kaleido python analysis/research/carbon_caps/plot_carbon_caps.py``; writes ``carbon_caps.html`` and
``carbon_caps.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.hpc.manifest import CAP_LADDER, SOURCE_BASIS, build_caps_table

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("carbon_caps")

# The caps table stamps the commit that built a manifest; a plot builds no manifest, so the field is filled with what it means here.
_NOT_A_MANIFEST_BUILD = "plot"

# Shallow to deep, matching the ladder's own order.
_RUNG_COLOURS = [
    "#c9d6e3",
    "#7fb3d5",
    "#2e86c1",
    "#1f4e79",
    "#7952b3",
    "#e4572e",
]


def _caps() -> pd.DataFrame:
    """Every cap rung of the campaign in tonnes, built by the manifest's own arithmetic."""
    plan = json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))
    return build_caps_table(plan, _NOT_A_MANIFEST_BUILD)


def _trajectories(caps: pd.DataFrame) -> list[str]:
    """Trajectories in the order the plan lists them, lowest demand first."""
    return list(dict.fromkeys(caps["trajectory"]))


def _rung_colour(schedule_key: str) -> str:
    """Colour for one cap schedule, shallow rungs light and deep rungs dark."""
    order = [schedule.key for schedule in CAP_LADDER].index(schedule_key)
    return _RUNG_COLOURS[order]


def _add_trajectory_panel(
    figure: go.Figure, caps: pd.DataFrame, trajectory: str, column: int
) -> None:
    """Add one line per cap schedule to one trajectory's panel."""
    for schedule in CAP_LADDER:
        rungs = caps[
            (caps["trajectory"] == trajectory) & (caps["cap_key"] == schedule.key)
        ]
        figure.add_trace(
            go.Scatter(
                x=rungs["year"],
                y=rungs["cap_t"],
                name=f"{schedule.key} (2050 target {schedule.target_2050} t/MWh)",
                legendgroup=schedule.key,
                showlegend=column == 1,
                mode="lines+markers",
                line={"color": _rung_colour(schedule.key), "width": 2},
                marker={"size": 6},
            ),
            row=1,
            col=column,
        )


def _add_source_basis_markers(
    figure: go.Figure, caps: pd.DataFrame, trajectory: str, column: int
) -> None:
    """Ring the rungs quoted on the source basis, which skip the delivery factor."""
    source_rungs = caps[
        (caps["trajectory"] == trajectory) & (caps["intensity_basis"] == SOURCE_BASIS)
    ]
    figure.add_trace(
        go.Scatter(
            x=source_rungs["year"],
            y=source_rungs["cap_t"],
            name="quoted on the source basis",
            legendgroup="basis",
            showlegend=column == 1,
            mode="markers",
            marker={
                "color": "#111111",
                "size": 16,
                "symbol": "circle-open",
                "line": {"width": 2},
            },
        ),
        row=1,
        col=column,
    )


def build_figure() -> go.Figure:
    """Assemble the faceted cap-ladder figure."""
    caps = _caps()
    trajectories = _trajectories(caps)
    figure = make_subplots(
        rows=1,
        cols=len(trajectories),
        shared_yaxes=True,
        subplot_titles=trajectories,
        horizontal_spacing=0.012,
    )
    for column, trajectory in enumerate(trajectories, start=1):
        _add_trajectory_panel(figure, caps, trajectory, column)
        _add_source_basis_markers(figure, caps, trajectory, column)
        figure.update_xaxes(
            title_text="milestone",
            tickvals=sorted(caps["year"].unique()),
            row=1,
            col=column,
        )
    figure.update_yaxes(
        title_text="annual CO2e cap (tonnes, log scale)", type="log", row=1, col=1
    )
    figure.update_layout(
        title="The carbon cap ladder as absolute annual tonnages, by trajectory",
        template="plotly_white",
        width=1400,
        height=820,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.42,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 320},
    )
    figure.add_annotation(
        text=(
            "A rung is named by its 2050 target intensity on the customer-delivered basis and enforced as a tonnage on the source basis:<br>"
            "cap_t = 0.91 x intensity x source load. A rung already quoted on the source basis skips that 0.91 and is ringed above. Because<br>"
            "the tonnage scales with demand, the same named rung is a different physical budget on every trajectory; the panels share one<br>"
            "log axis so that spread is read directly. The 0.91 delivery fraction is an unratified placeholder, so a cap said to be per MWh<br>"
            "delivered is only that if 0.91 is right."
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
