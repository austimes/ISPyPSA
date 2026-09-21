"""Plot the campaign's demand trajectories against the AEMO series they are judged by.

Reads the five trajectories from ``analysis/hpc/demand_plan.json`` and the three AEMO 2026 draft ISP candidate development path 4 (CDP4)
scenario files from the repository's ``iasr outputs`` directory. The parsed 2026 final IASR demand trace store the campaign actually reads
lives on a network share rather than in the repository, so its Step Change annual totals are carried here as constants with their source
named beside them.

The plan's low and stress trajectories are their matching CDP4 scenario scaled by an authored generation-to-operational factor, so they sit
below the dotted series they are drawn against rather than on top of it; the legend names the factor.

Run with ``uv run --with kaleido python analysis/research/demand_plan/plot_demand_trajectories.py``; writes
``demand_trajectories.html`` and ``demand_trajectories.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_CDP4_DIR = _REPO_ROOT / "iasr outputs"
_OUTPUT_STEM = Path(__file__).with_name("demand_trajectories")

# Total generation less rooftop photovoltaics: behind-the-meter rooftop output never crosses the NEM, so the remainder is the closest
# available proxy for grid-supplied energy in these generation-basis files.
_ROOFTOP_COLUMN = "Solar (Rooftop)"
# Every CDP4 row is stamped like "1 Jan 2010 12:00 am"; AEMO labels an annual result by the financial year ending 30 June of that year.
_CDP4_DATE_FORMAT = "%d %b %Y %I:%M %p"
_FUEL_COLUMNS = [
    "Demand Response",
    "Coal",
    "Bioenergy",
    "Distillate",
    "Gas",
    "Hydro",
    "Wind",
    "Solar (Utility)",
    _ROOFTOP_COLUMN,
]

_CDP4_SCENARIOS = {
    "slower_growth": "draft ISP Slower Growth (CDP4 gen. excl. rooftop)",
    "step_change": "draft ISP Step Change (CDP4 gen. excl. rooftop)",
    "accelerated_transition": "draft ISP Accelerated Transition (CDP4 gen. excl. rooftop)",
}

# Step Change source-NEM load summed over the 15 ISP sub-regions in the parsed 2026 final IASR trace store
# (traces/isp_2026/demand/, scenario Step Change, POE50, demand type OPSO_MODELLING, reference year 2018). FY2060 is not in the store: the
# campaign builds its 2060 shape by relabelling FY2050, so FY2050 energy is repeated here for the same reason.
_TRACE_STORE_STEP_CHANGE_TWH = {
    2030: 189.818,
    2040: 240.051,
    2050: 251.925,
    2060: 251.925,
}

_TRAJECTORY_LABELS = {
    "iasr_stress": "plan stress (0.97 x draft ISP Accelerated Transition to 2050)",
    "iasr_high": "plan high",
    "iasr_central": "plan central",
    "iasr_low": "plan low (0.97 x draft ISP Slower Growth to 2050)",
    "iasr_low_bracket": "plan low_bracket (0.92 x low)",
}
_TRAJECTORY_COLOURS = {
    "iasr_stress": "#e4572e",
    "iasr_high": "#7952b3",
    "iasr_central": "#1f77b4",
    "iasr_low": "#2aa198",
    "iasr_low_bracket": "#2e8b30",
}
_CDP4_COLOURS = {
    "slower_growth": "#d68fa8",
    "step_change": "#d4a017",
    "accelerated_transition": "#e4572e",
}


def _read_plan(path: Path) -> dict:
    """Return the demand plan as parsed JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def _trajectory_series(plan: dict, trajectory: str) -> pd.Series:
    """Milestone TWh for one trajectory, indexed by financial year and restricted to the plan's milestone years."""
    knots = plan["demand_paths_source_twh"][trajectory]
    milestones = plan["milestone_years"]
    return pd.Series(
        {year: knots[str(year)] for year in milestones if str(year) in knots}
    )


def _cdp4_grid_supplied_twh(scenario: str) -> pd.Series:
    """Annual NEM generation excluding rooftop photovoltaics for one CDP4 scenario, indexed by year."""
    frame = pd.read_csv(
        _CDP4_DIR / f"NEM-aemo2026draft-{scenario}-CDP4 (ODP)-energy.csv"
    )
    frame["year"] = pd.to_datetime(frame["date"], format=_CDP4_DATE_FORMAT).dt.year
    excluding_rooftop = frame[_FUEL_COLUMNS].sum(axis=1) - frame[_ROOFTOP_COLUMN]
    return pd.Series(excluding_rooftop.to_numpy(), index=frame["year"])


def _add_plan_traces(figure: go.Figure, plan: dict) -> None:
    """Add one solid line per campaign demand trajectory."""
    for trajectory, label in _TRAJECTORY_LABELS.items():
        series = _trajectory_series(plan, trajectory)
        figure.add_trace(
            go.Scatter(
                x=series.index,
                y=series.to_numpy(),
                name=label,
                mode="lines+markers",
                line={"color": _TRAJECTORY_COLOURS[trajectory], "width": 2},
            )
        )


def _add_trace_store_reference(figure: go.Figure) -> None:
    """Add the parsed final-IASR Step Change trace as a dashed reference line."""
    figure.add_trace(
        go.Scatter(
            x=list(_TRACE_STORE_STEP_CHANGE_TWH),
            y=list(_TRACE_STORE_STEP_CHANGE_TWH.values()),
            name="AEMO 2026 final Step Change trace (source-NEM, FY2050 held for 2060)",
            mode="lines+markers",
            line={"color": "#444444", "width": 3, "dash": "dash"},
        )
    )


def _add_cdp4_traces(figure: go.Figure, first_year: int) -> None:
    """Add one dotted line per draft-ISP CDP4 scenario, from the first plotted milestone onward."""
    for scenario, label in _CDP4_SCENARIOS.items():
        series = _cdp4_grid_supplied_twh(scenario)
        series = series[series.index >= first_year]
        figure.add_trace(
            go.Scatter(
                x=series.index,
                y=series.to_numpy(),
                name=label,
                mode="lines+markers",
                line={"color": _CDP4_COLOURS[scenario], "width": 1.5, "dash": "dot"},
                marker={"size": 4},
            )
        )


def build_figure(plan: dict) -> go.Figure:
    """Assemble the demand comparison figure."""
    figure = go.Figure()
    _add_plan_traces(figure, plan)
    _add_trace_store_reference(figure)
    _add_cdp4_traces(figure, min(plan["milestone_years"]))
    figure.update_layout(
        title="NEM demand by year: campaign trajectories against the AEMO series they are judged by",
        xaxis_title="financial year",
        yaxis_title="TWh per year",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.2,
            "xanchor": "left",
            "x": 0,
        },
        template="plotly_white",
        width=1100,
        height=700,
    )
    return figure


def main() -> None:
    """Build the figure and write it as HTML and PNG beside this script."""
    figure = build_figure(_read_plan(_DEMAND_PLAN))
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)


if __name__ == "__main__":
    main()
