"""Plot the campaign's Step Change demand knots against the AEMO series they are derived from, and the measured factor.

The top panel draws the plan's ``iasr_step_change`` knots from ``analysis/hpc/demand_plan.json`` beside AEMO's final 2026
ISP Step Change generation (as published and net of storage losses), the draft ISP CDP4 generation the knots were scaled
from, and the parsed operational-demand trace store. The bottom panel draws the two ratios to generation that bound the
generation-to-operational-demand factor, with the authored 0.97 as a reference line.

The parsed trace store lives on a network share rather than in the repository, so its per-year Step Change totals are
carried here as constants with their source named beside them.

Run with ``uv run --with kaleido python analysis/research/demand_plan/plot_demand_trajectories.py``; writes
``demand_trajectories.html`` and ``demand_trajectories.png`` beside this script.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEMAND_PLAN = _REPO_ROOT / "analysis" / "hpc" / "demand_plan.json"
_CDP4_ENERGY = (
    _REPO_ROOT / "iasr outputs" / "NEM-aemo2026draft-step_change-CDP4 (ODP)-energy.csv"
)
_FINAL_ISP = (
    _REPO_ROOT
    / "analysis"
    / "research"
    / "aemo_scenario_cost"
    / "aemo_2026_isp_cdp4_costs_generation.csv"
)
_OUTPUT_STEM = Path(__file__).with_name("demand_trajectories")

_TRAJECTORY = "iasr_step_change"
_GENERATION = "Generation excluding rooftop and storage"
_STORAGE_NET = "Storage and DSP net generation"
_AUTHORED_FACTOR = 0.97

#: Step Change OPSO_MODELLING summed over the 15 ISP sub-regions per financial year, TWh, from the parsed 2026 final IASR
#: trace store (traces/isp_2026/demand/, Step Change, POE50, reference year 2018); see source_data.md, S001.
_TRACE_TWH = {
    2026: 178.116, 2027: 179.483, 2028: 181.121, 2029: 183.191, 2030: 189.818, 2031: 196.103, 2032: 203.635,
    2033: 210.146, 2034: 215.296, 2035: 219.336, 2036: 224.376, 2037: 229.470, 2038: 234.131, 2039: 237.622,
    2040: 240.051, 2041: 241.796, 2042: 243.442, 2043: 244.922, 2044: 246.224, 2045: 247.158, 2046: 248.818,
    2047: 250.048, 2048: 251.214, 2049: 251.808, 2050: 251.925, 2051: 251.984, 2052: 252.088, 2053: 251.659,
    2054: 251.475, 2055: 251.825, 2056: 251.168,
}  # fmt: skip


def _plan_knots() -> pd.Series:
    """The plan's Step Change knots in TWh, indexed by milestone year."""
    knots = json.loads(_DEMAND_PLAN.read_text(encoding="utf-8"))[
        "demand_paths_source_twh"
    ][_TRAJECTORY]
    return pd.Series({int(year): twh for year, twh in knots.items()}).sort_index()


def _final_isp_twh() -> pd.DataFrame:
    """Final 2026 ISP Step Change generation and storage net generation in TWh, indexed by financial year."""
    frame = pd.read_csv(_FINAL_ISP)
    frame = frame[
        (frame["scenario"] == "Step Change")
        & frame["series"].isin([_GENERATION, _STORAGE_NET])
    ]
    return (
        frame.pivot(index="financial_year_ending", columns="series", values="value")
        / 1e3
    )


def _draft_generation_twh() -> pd.Series:
    """Draft ISP CDP4 Step Change generation excluding rooftop in TWh, indexed by year, from 2026."""
    frame = pd.read_csv(_CDP4_ENERGY)
    frame.index = frame.pop("date").str.extract(r"(\d{4})")[0].astype(int)
    series = frame.sum(axis=1) - frame["Solar (Rooftop)"]
    return series[series.index >= 2026]


def _line(
    x: pd.Index, y: pd.Series, name: str, colour: str, dash: str = "solid"
) -> go.Scatter:
    """One labelled line trace."""
    return go.Scatter(
        x=list(x),
        y=list(y),
        name=name,
        mode="lines+markers",
        line={"color": colour, "dash": dash},
        marker={"size": 4},
    )


def build_figure() -> go.Figure:
    """Knots and AEMO series on top, the two measured ratios below."""
    final = _final_isp_twh()
    generation = final[_GENERATION]
    net_of_storage = generation + final[_STORAGE_NET]
    trace = pd.Series(_TRACE_TWH)
    knots = _plan_knots()
    draft = _draft_generation_twh()
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.62, 0.38],
        vertical_spacing=0.06,
    )
    figure.add_trace(
        _line(knots.index, knots, "campaign knots (source NEM load)", "#1f77b4"),
        row=1,
        col=1,
    )
    figure.add_trace(
        _line(
            draft.index,
            draft,
            "draft ISP CDP4 generation excl. rooftop",
            "#d4a017",
            "dot",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        _line(
            generation.index,
            generation,
            "final ISP generation excl. rooftop and storage",
            "#e4572e",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        _line(
            net_of_storage.index,
            net_of_storage,
            "final ISP generation net of storage losses",
            "#7b2d8e",
            "dash",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        _line(
            trace.index,
            trace,
            "operational demand trace (OPSO_MODELLING)",
            "#444444",
            "dash",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        _line(
            generation.index,
            trace.reindex(generation.index) / generation,
            "operational demand / generation",
            "#444444",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        _line(
            generation.index,
            net_of_storage / generation,
            "generation net of storage losses / generation",
            "#7b2d8e",
        ),
        row=2,
        col=1,
    )
    figure.add_hline(
        y=_AUTHORED_FACTOR,
        line={"color": "#999999", "dash": "dot"},
        annotation_text="authored 0.97",
        row=2,
        col=1,
    )
    figure.update_yaxes(title_text="TWh per year", row=1, col=1)
    figure.update_yaxes(title_text="ratio to generation", row=2, col=1)
    figure.update_xaxes(title_text="financial year", row=2, col=1)
    figure.update_layout(
        title="Step Change demand knots against AEMO generation and operational demand",
        template="plotly_white",
        width=1100,
        height=820,
        legend={"orientation": "h", "yanchor": "top", "y": -0.1, "x": 0},
    )
    return figure


def main() -> None:
    """Build the figure and write it as HTML and PNG beside this script."""
    figure = build_figure()
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)


if __name__ == "__main__":
    main()
