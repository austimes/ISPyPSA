"""Plot the annual conventional-hydro energy budget the model enforces, including the clamp past the last published year.

The budget lives only in code, so both the published series and the clamping rule are imported from
``src/ispypsa/pypsa_build/generators.py`` rather than copied here. Megawatt-hours are converted to terawatt-hours (TWh) for reading; the
campaign milestones are marked because the 2060 milestone is served entirely by the clamp.

Run with ``uv run --with kaleido python analysis/research/hydro_energy_budget/plot_hydro_budget.py``; writes ``hydro_budget.html`` and
``hydro_budget.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import plotly.graph_objects as go

from ispypsa.pypsa_build.generators import (
    _HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY,
    _hydro_annual_budget_mwh,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("hydro_budget")

_MWH_PER_TWH = 1e6


def _milestone_years() -> list[int]:
    """Campaign milestone years, which the clamp is drawn out to."""
    return json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))["milestone_years"]


def _published_twh() -> dict[int, float]:
    """The published budget series in TWh, keyed by financial year."""
    return {
        year: mwh / _MWH_PER_TWH
        for year, mwh in _HYDRO_ANNUAL_ENERGY_BUDGET_MWH_BY_FY.items()
    }


def _clamped_twh(last_published: int, last_milestone: int) -> dict[int, float]:
    """The budget the clamping rule returns for every year past the published range, in TWh."""
    years = range(last_published, last_milestone + 1)
    return {year: _hydro_annual_budget_mwh(year) / _MWH_PER_TWH for year in years}


def _add_published_trace(figure: go.Figure, published: dict[int, float]) -> None:
    """Add the published FY2027 to FY2050 budget as a solid line."""
    figure.add_trace(
        go.Scatter(
            x=list(published),
            y=list(published.values()),
            name="published budget (AEMO Step Change modelled hydro generation)",
            mode="lines+markers",
            line={"color": "#1f77b4", "width": 2},
        )
    )


def _add_clamp_trace(figure: go.Figure, clamped: dict[int, float]) -> None:
    """Add the clamped extension past the last published year as a dashed line."""
    figure.add_trace(
        go.Scatter(
            x=list(clamped),
            y=list(clamped.values()),
            name="clamped to the last published year",
            mode="lines",
            line={"color": "#e4572e", "width": 2, "dash": "dash"},
        )
    )


def _add_milestone_markers(
    figure: go.Figure, budgets: dict[int, float], milestones: list[int]
) -> None:
    """Mark the budget each campaign milestone actually solves against."""
    figure.add_trace(
        go.Scatter(
            x=milestones,
            y=[budgets[year] for year in milestones],
            name="campaign milestone",
            mode="markers+text",
            marker={"color": "#111111", "size": 11, "symbol": "diamond"},
            text=[f"{budgets[year]:.2f} TWh" for year in milestones],
            textposition="top center",
        )
    )


def build_figure() -> go.Figure:
    """Assemble the hydro energy budget figure."""
    published = _published_twh()
    milestones = _milestone_years()
    last_published = max(published)
    clamped = _clamped_twh(last_published, max(milestones))
    figure = go.Figure()
    _add_published_trace(figure, published)
    _add_clamp_trace(figure, clamped)
    _add_milestone_markers(figure, published | clamped, milestones)
    figure.update_layout(
        title="Annual conventional-hydro energy budget, and the clamp that serves every year past FY"
        f"{last_published}",
        xaxis_title="financial year",
        yaxis_title="annual energy budget (TWh)",
        yaxis_rangemode="tozero",
        template="plotly_white",
        width=1100,
        height=700,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.42,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 210},
    )
    figure.add_annotation(
        text=(
            f"The published series ends at FY{last_published}. A period outside FY{min(published)} to FY{last_published} takes the nearest "
            "published year's budget,<br>so the 2060 milestone is solved against FY"
            f"{last_published}'s water and a 2025 or 2026 period would take FY{min(published)}'s."
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
