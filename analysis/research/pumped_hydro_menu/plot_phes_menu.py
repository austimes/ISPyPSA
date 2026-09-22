"""Plot the pumped hydro energy storage (PHES) candidate menu: capital cost against storage duration, and the shared site ceilings.

The left panel shows what a candidate costs per kilowatt of power capacity at each storage depth. The published 10, 24 and 48-hour points
come straight from the parsed workbook cache; the authored 168 and 336-hour points are produced here by calling
``analysis.model.phes_menu``'s own least-squares fit, so the plotted authored capex is the number the model builds with rather than a
transcription of it. The right panel is the shared site ceiling per ISP sub-region, which is the 48-hour build limit applied as a cap on the
sum of all new-entrant PHES power in that sub-region.

Both source tables live in the versioned input package on the data share, resolved through ``analysis.env``, so ``IO_DIR`` must be set and
the share mounted.

Run with ``uv run --with kaleido python analysis/research/pumped_hydro_menu/plot_phes_menu.py``; writes ``phes_menu.html`` and
``phes_menu.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analysis.env import Env
from analysis.model.phes_menu import (
    _EXTRAPOLATED_CLASSES,
    _PHES_48H_TECH,
    _PUBLISHED_FIT_DURATIONS,
    _fit_capex_against_duration,
    _limit_column,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_OUTPUT_STEM = Path(__file__).with_name("phes_menu")

# The campaign scenario, which selects one GenCost cost trajectory out of the workbook's build-cost table.
_SCENARIO = "Step Change"

_YEAR_COLOURS = {2030: "#7fb3d5", 2040: "#2e86c1", 2050: "#1f4e79", 2060: "#e4572e"}


def _milestone_years() -> list[int]:
    """Campaign milestone years, one cost curve per year that the workbook covers."""
    return json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))["milestone_years"]


def _build_cost_column(year: int) -> str:
    """Workbook column holding the financial year ending in ``year``, e.g. 2030 -> ``2029-30``."""
    return f"{year - 1}-{str(year)[2:]}"


def _published_capex_per_kw(cache: Path) -> pd.DataFrame:
    """Published PHES capital cost in A$/kW for the campaign scenario, indexed by technology."""
    costs = pd.read_csv(cache / "build_costs.csv")
    scenario_rows = costs[costs["IASR Scenario"] == _SCENARIO].set_index("Technology")
    return scenario_rows.loc[list(_PUBLISHED_FIT_DURATIONS)]


def _covered_years(capex: pd.DataFrame, years: list[int]) -> list[int]:
    """Milestone years the workbook's build-cost table actually carries a column for."""
    return [year for year in years if _build_cost_column(year) in capex.columns]


def _authored_capex_per_kw(capex: pd.DataFrame, year: int) -> dict[float, float]:
    """Authored long-duration capex for one year, from the model's own capex-against-duration fit."""
    column = capex[_build_cost_column(year)].astype(float)
    power_cost, reservoir_cost, _ = _fit_capex_against_duration(column)
    return {
        phes_class["duration_hours"]: power_cost
        + reservoir_cost * phes_class["duration_hours"]
        for phes_class in _EXTRAPOLATED_CLASSES
    }


def _add_published_traces(
    figure: go.Figure, capex: pd.DataFrame, years: list[int]
) -> None:
    """Add the published 10, 24 and 48-hour capital cost points, one line per year."""
    durations = [_PUBLISHED_FIT_DURATIONS[tech] for tech in capex.index]
    for year in years:
        figure.add_trace(
            go.Scatter(
                x=durations,
                y=capex[_build_cost_column(year)].astype(float).to_numpy(),
                name=f"FY{year} published (10 / 24 / 48 h)",
                mode="lines+markers",
                line={"color": _YEAR_COLOURS[year], "width": 2},
                marker={"size": 10, "symbol": "circle"},
            ),
            row=1,
            col=1,
        )


def _add_authored_traces(
    figure: go.Figure, capex: pd.DataFrame, years: list[int]
) -> None:
    """Add the authored 168 and 336-hour points as a dashed extrapolation from the 48-hour point."""
    for year in years:
        authored = _authored_capex_per_kw(capex, year)
        anchor = float(capex.loc[_PHES_48H_TECH, _build_cost_column(year)])
        figure.add_trace(
            go.Scatter(
                x=[_PUBLISHED_FIT_DURATIONS[_PHES_48H_TECH], *authored],
                y=[anchor, *authored.values()],
                name=f"FY{year} authored (168 / 336 h, fitted)",
                mode="lines+markers",
                line={"color": _YEAR_COLOURS[year], "width": 2, "dash": "dash"},
                marker={"size": 12, "symbol": "x-open", "line": {"width": 2}},
            ),
            row=1,
            col=1,
        )


def _shared_site_limits(cache: Path) -> pd.Series:
    """Shared site ceiling in MW per ISP sub-region: the 48-hour build limit, dropping sub-regions with none."""
    limits = pd.read_csv(cache / "build_limits_phes.csv")
    column = _limit_column({"build_limits_phes": limits}, _PHES_48H_TECH)
    ceilings = limits.set_index("ISP Sub-region")[column].astype(float)
    return ceilings[ceilings > 0].sort_values(ascending=False)


def _add_site_limit_trace(figure: go.Figure, ceilings: pd.Series) -> None:
    """Add the shared site ceiling bar panel."""
    figure.add_trace(
        go.Bar(
            x=ceilings.index,
            y=ceilings.to_numpy(),
            name="shared site ceiling (48 h build limit)",
            marker_color="#2aa198",
            text=[f"{mw:,.0f}" for mw in ceilings],
            textposition="outside",
        ),
        row=1,
        col=2,
    )


def build_figure() -> go.Figure:
    """Assemble the two-panel PHES menu figure."""
    cache = Env.from_env().workbook_cache
    capex = _published_capex_per_kw(cache)
    years = _covered_years(capex, _milestone_years())
    figure = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.55, 0.45],
        subplot_titles=(
            f"Capital cost against storage duration, {_SCENARIO}",
            "Shared site ceiling on total new-entrant PHES power",
        ),
    )
    _add_published_traces(figure, capex, years)
    _add_authored_traces(figure, capex, years)
    _add_site_limit_trace(figure, _shared_site_limits(cache))
    durations = sorted(
        [*_PUBLISHED_FIT_DURATIONS.values(), *_authored_capex_per_kw(capex, years[0])]
    )
    figure.update_xaxes(
        title_text="storage duration (hours, log scale)",
        type="log",
        tickvals=durations,
        ticktext=[f"{hours:.0f}" for hours in durations],
        row=1,
        col=1,
    )
    figure.update_yaxes(title_text="capital cost (A$/kW of power)", row=1, col=1)
    figure.update_xaxes(title_text="ISP sub-region", row=1, col=2)
    figure.update_yaxes(title_text="shared site ceiling (MW)", row=1, col=2)
    figure.update_layout(
        title="The PHES candidate menu: what each storage depth costs, and how much power a sub-region may build",
        template="plotly_white",
        width=1300,
        height=820,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.46,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 320},
    )
    figure.add_annotation(
        text=(
            "The authored points are the model's own per-year least-squares fit of capital cost against duration, evaluated beyond the<br>"
            "published range; every other parameter of those two classes is inherited from the 48-hour class unchanged. The workbook's<br>"
            f"build-cost table carries no column past FY{max(years)}, so no cost curve is drawn for a later milestone. One ceiling per<br>"
            "sub-region caps the sum of every duration class, so the classes compete for one site budget; the ceilings exclude Snowy 2.0<br>"
            "and Borumba and so are additive with them."
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
