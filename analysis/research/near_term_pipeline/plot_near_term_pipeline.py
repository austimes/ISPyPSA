"""Plot the 2030 fleet the campaign starts from against the fleet AEMO's Step Change path reaches.

Each carrier is a stack of what the model already holds at 2030 -- existing plant, then the committed, anticipated and
policy-supported pipeline -- with the new-entrant allowance stacked on top and AEMO's own Step Change 2030 capacity drawn
as a marker. Where the stack reaches the marker the allowance is exactly the gap; where the stack overshoots it, the model
holds more than the path does and no allowance is offered. Derivations and sources are in ``research.md``.

Run with ``uv run --with kaleido python analysis/research/near_term_pipeline/plot_near_term_pipeline.py``; writes
``near_term_pipeline.html`` and ``near_term_pipeline.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_CDP4_CAPACITY = (
    Path(__file__).parents[3]
    / "iasr outputs"
    / "NEM-aemo2026draft-step_change-CDP4 (ODP)-capacity.csv"
)
_OUTPUT_STEM = Path(__file__).with_name("near_term_pipeline")

#: Gigawatts on the model's 2030 roster, summed from the templated inputs of the reference run's 2030 solve (S003).
#: Pipeline is committed plus anticipated plus additional policy-supported; storage is battery plus pumped hydro.
_ROSTER = {
    "Wind": (11.749, 8.358),
    "Solar, utility": (10.859, 8.741),
    "Gas": (10.070, 1.324),
    "Coal": (15.285, 0.0),
    "Hydro, conventional": (6.885, 0.0),
    "Storage": (4.840, 15.859),
}

#: The CDP4 column each carrier is measured against. Storage has no CDP4 column at all, so it takes the draft ISP's
#: reported grid-scale battery and pumped hydro milestone of 27 GW by 2030 (S004) instead.
_CDP4_COLUMN = {
    "Wind": "Wind",
    "Solar, utility": "Solar (Utility)",
    "Gas": "Gas",
    "Coal": "Coal",
    "Hydro, conventional": "Hydro",
}
_STORAGE_2030_GW = 27.0

#: Carriers the model offers no new entrant for, or already exceeds the path in, so no allowance is drawn.
_NO_NEW_ENTRANT = ("Coal", "Hydro, conventional")

_SEGMENT_COLOUR = {
    "Existing": "#4c6a8c",
    "Committed, anticipated and policy-supported": "#4c9f70",
    "New-entrant allowance": "#e4a11b",
}

_ANNOTATION = (
    "The allowance is the gap between the fleet the model already holds at 2030 and the fleet AEMO's Step Change "
    "optimal development path reaches.<br>"
    "Pooled it is about 19 GW of generation (--new-entrant-cap-mw) and 6 GW of storage "
    "(--new-entrant-storage-cap-mw). Coal is not shown with<br>an allowance because closures follow "
    "announced years only, which leaves the model 2.3 GW above the path; conventional hydro has no new entrant in the "
    "model."
)


def _cdp4_2030() -> pd.Series:
    """Read AEMO's Step Change 2030 installed capacity by fuel, in gigawatts."""
    frame = pd.read_csv(_CDP4_CAPACITY)
    frame["year"] = frame["date"].str.extract(r"(\d{4})").astype(int)
    return frame.set_index("year").loc[2030]


def _target_gw(carrier: str, cdp4: pd.Series) -> float:
    """Return the 2030 capacity target for one carrier, in gigawatts."""
    if carrier == "Storage":
        return _STORAGE_2030_GW
    return float(cdp4[_CDP4_COLUMN[carrier]])


def _allowance_gw(carrier: str, cdp4: pd.Series) -> float:
    """Return the buildable new-entrant allowance for one carrier, floored at zero."""
    if carrier in _NO_NEW_ENTRANT:
        return 0.0
    existing, pipeline = _ROSTER[carrier]
    return max(_target_gw(carrier, cdp4) - existing - pipeline, 0.0)


def build_figure() -> go.Figure:
    """Assemble the stacked 2030 fleet with AEMO's Step Change capacity marked on each carrier."""
    cdp4 = _cdp4_2030()
    carriers = list(_ROSTER)
    segments = {
        "Existing": [_ROSTER[c][0] for c in carriers],
        "Committed, anticipated and policy-supported": [
            _ROSTER[c][1] for c in carriers
        ],
        "New-entrant allowance": [_allowance_gw(c, cdp4) for c in carriers],
    }
    figure = go.Figure()
    for name, values in segments.items():
        figure.add_trace(
            go.Bar(x=carriers, y=values, name=name, marker_color=_SEGMENT_COLOUR[name])
        )
    figure.add_trace(
        go.Scatter(
            x=carriers,
            y=[_target_gw(c, cdp4) for c in carriers],
            name="AEMO Step Change 2030 capacity",
            mode="markers",
            marker={
                "symbol": "line-ew",
                "size": 46,
                "line": {"color": "#111111", "width": 3},
            },
        )
    )
    figure.update_layout(
        title="The 2030 fleet the campaign starts from, and the new-entrant allowance that reaches AEMO's Step Change path",
        barmode="stack",
        yaxis_title="capacity at 2030 (GW)",
        template="plotly_white",
        width=1150,
        height=680,
        legend={"orientation": "h", "yanchor": "top", "y": -0.14, "x": 0},
        margin={"b": 230},
    )
    figure.add_annotation(
        text=_ANNOTATION,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.40,
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
