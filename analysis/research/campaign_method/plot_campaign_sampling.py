"""Plot what a campaign chain actually looks at: which weeks of the year are sampled, and which years are solved.

Both panels are read from the submission script and the config template rather than transcribed. The week list and the milestone list come
from ``analysis/hpc/slurm/chain.sbatch``; the names of the two optional stress weeks come from the config template in
``analysis/hpc/solve.py``. Those two weeks are selected from the demand and renewable traces at solve time and so have no fixed week number,
which is why they are drawn as a disabled row rather than at a position.

Run with ``uv run --with kaleido python analysis/research/campaign_method/plot_campaign_sampling.py``; writes ``campaign_sampling.html`` and
``campaign_sampling.png`` beside this script.
"""

from __future__ import annotations

import re
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SBATCH = _REPO_ROOT / "analysis" / "hpc" / "slurm" / "chain.sbatch"
_SOLVE = _REPO_ROOT / "analysis" / "hpc" / "solve.py"
_OUTPUT_STEM = Path(__file__).with_name("campaign_sampling")

_WEEKS_IN_YEAR = 52

# Half-hour snapshots in one sampled week: 7 days at 48 periods a day, at the config template's 30-minute resolution.
_SNAPSHOTS_PER_WEEK = 7 * 48
_HOURS_IN_YEAR = 8760

# "--rep-weeks 1 6 10 ... 50" in the submission script, up to the next flag.
_REP_WEEKS_PATTERN = re.compile(r"--rep-weeks((?:\s+\d+)+)")
# "--periods 2030 2040 2050 2060" in the submission script.
_PERIODS_PATTERN = re.compile(r"--periods((?:\s+\d+)+)")
# The config template's named-week list, e.g. 'named_representative_weeks: {"[residual-peak-demand, peak-demand]" if named_weeks else "~"}'.
_NAMED_WEEKS_PATTERN = re.compile(r'"\[([^\]]+)\]" if named_weeks')


def _integers(source: str, pattern: re.Pattern[str]) -> list[int]:
    """Whitespace-separated integers following a command-line flag."""
    return [int(token) for token in pattern.search(source).group(1).split()]


def _named_week_names(source: str) -> list[str]:
    """Names of the two optional stress weeks, as the config template writes them."""
    return [
        name.strip() for name in _NAMED_WEEKS_PATTERN.search(source).group(1).split(",")
    ]


def _named_weeks_enabled(source: str) -> bool:
    """Whether the submission script leaves the named stress weeks on."""
    return "--no-named-weeks" not in source


# The two rows of the week panel: numbered weeks on top, the optional named weeks beneath, so neither row covers the other.
_NUMBERED_ROW_BASE = 0.55
_NAMED_ROW_HEIGHT = 0.4


def _add_week_samples(figure: go.Figure, weeks: list[int]) -> None:
    """Draw the full year as a background band and the sampled weeks on top of it."""
    figure.add_trace(
        go.Bar(
            x=list(range(1, _WEEKS_IN_YEAR + 1)),
            y=[1 - _NUMBERED_ROW_BASE] * _WEEKS_IN_YEAR,
            base=_NUMBERED_ROW_BASE,
            name=f"not sampled ({_WEEKS_IN_YEAR - len(weeks)} weeks)",
            marker_color="#e8ecf0",
            width=0.9,
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=weeks,
            y=[1 - _NUMBERED_ROW_BASE] * len(weeks),
            base=_NUMBERED_ROW_BASE,
            name=f"representative week ({len(weeks)} sampled)",
            marker_color="#2e86c1",
            width=0.9,
        ),
        row=1,
        col=1,
    )


def _add_named_week_row(figure: go.Figure, names: list[str], enabled: bool) -> None:
    """Draw the two optional stress weeks as their own row, at no position because they are selected from the traces."""
    state = "on" if enabled else "off by --no-named-weeks"
    figure.add_trace(
        go.Bar(
            x=list(range(1, _WEEKS_IN_YEAR + 1)),
            y=[_NAMED_ROW_HEIGHT] * _WEEKS_IN_YEAR,
            name=f"{' and '.join(names)}: {state}, week number set at solve time",
            marker_color="#e4572e" if enabled else "#f2ded9",
            width=0.9,
        ),
        row=1,
        col=1,
    )


def _add_milestones(figure: go.Figure, periods: list[int]) -> None:
    """Draw the milestone sequence, with the last milestone marked as a hold on the one before it."""
    held = max(periods)
    published = [year for year in periods if year != held]
    figure.add_trace(
        go.Scatter(
            x=periods,
            y=[1] * len(periods),
            name="milestone solve",
            mode="lines",
            line={"color": "#8899aa", "width": 2},
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    figure.add_trace(
        go.Scatter(
            x=published,
            y=[1] * len(published),
            name="milestone on published AEMO inputs",
            mode="markers",
            marker={"color": "#2e86c1", "size": 20, "symbol": "circle"},
        ),
        row=1,
        col=2,
    )
    figure.add_trace(
        go.Scatter(
            x=[held],
            y=[1],
            name=f"{held}: {max(published)} inputs held forward",
            mode="markers",
            marker={
                "color": "#e4572e",
                "size": 20,
                "symbol": "circle-open",
                "line": {"width": 3},
            },
        ),
        row=1,
        col=2,
    )
    figure.add_annotation(
        x=held,
        y=1,
        ax=max(published),
        ay=1,
        xref="x2",
        yref="y2",
        axref="x2",
        ayref="y2",
        showarrow=True,
        arrowhead=2,
        arrowwidth=2,
        arrowcolor="#e4572e",
        text="",
    )


def build_figure() -> go.Figure:
    """Assemble the two-panel campaign sampling figure."""
    sbatch = _SBATCH.read_text(encoding="utf-8")
    weeks = _integers(sbatch, _REP_WEEKS_PATTERN)
    periods = _integers(sbatch, _PERIODS_PATTERN)
    names = _named_week_names(_SOLVE.read_text(encoding="utf-8"))
    weighting = _HOURS_IN_YEAR / (len(weeks) * _SNAPSHOTS_PER_WEEK / 2)
    figure = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.66, 0.34],
        subplot_titles=(
            f"Weeks of the year each solve looks at ({len(weeks)} of {_WEEKS_IN_YEAR})",
            "Milestones a chain solves, and the hold at the last one",
        ),
    )
    _add_week_samples(figure, weeks)
    _add_named_week_row(figure, names, _named_weeks_enabled(sbatch))
    _add_milestones(figure, periods)
    figure.update_xaxes(
        title_text="week of the financial year",
        dtick=2,
        range=[0.4, _WEEKS_IN_YEAR + 0.6],
        row=1,
        col=1,
    )
    figure.update_yaxes(visible=False, range=[0, 1.05], row=1, col=1)
    figure.update_xaxes(
        title_text="milestone year",
        tickvals=periods,
        range=[min(periods) - 5, max(periods) + 5],
        row=1,
        col=2,
    )
    figure.update_yaxes(visible=False, range=[0.5, 1.6], row=1, col=2)
    figure.update_layout(
        title=f"What a campaign chain looks at: {len(weeks)} weeks of each year, at {len(periods)} milestones",
        template="plotly_white",
        barmode="overlay",
        bargap=0.1,
        width=1300,
        height=820,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.46,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 300},
    )
    figure.add_annotation(
        text=(
            f"The {len(weeks)} sampled weeks carry {len(weeks) * _SNAPSHOTS_PER_WEEK:,} half-hourly snapshots, weighted by about "
            f"{weighting:.1f} to annualise to {_HOURS_IN_YEAR:,} hours. No selection<br>"
            "method is recorded for these particular weeks. The two named stress weeks are chosen from the demand and renewable traces at<br>"
            "solve time, so they have no fixed week number and are drawn as a row rather than at a position; the campaign disables them, so<br>"
            f"an extreme hour enters only if one of the {len(weeks)} happens to contain it. Every AEMO input stops at "
            f"{max(year for year in periods if year != max(periods))}, so the {max(periods)} milestone reuses<br>"
            f"that year's weather, demand shape, water and fuel availability under an authored demand level and an authored cap."
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
