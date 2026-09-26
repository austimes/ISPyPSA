"""Plot the 2030 fleet the campaign starts from against the fleet AEMO's Step Change path reaches.

Each carrier is a stack of what the model already holds at 2030 -- existing plant, then the committed, anticipated and
policy-supported pipeline -- with the new-entrant allowance stacked on top and AEMO's own Step Change 2030 capacity drawn
as a marker. Where the stack reaches the marker the allowance is exactly the gap; where the stack overshoots it, the model
holds more than the path does and no allowance is offered. Wind, utility solar and batteries are measured against the
final 2026 ISP and the IASR roster commissioned by 1 July 2029; gas, coal and conventional hydro are still measured
against the draft-ISP CDP4 series, for which no final-ISP reading was derived. Derivations and sources are in
``research.md``.

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

#: Gigawatts on the roster each carrier is measured against. Wind, solar and storage are measured against the IASR
#: roster commissioned by 1 July 2029 (17.6, 22.9 and 28.2 GW respectively, S007): existing plant unchanged, with the
#: remainder folded into pipeline. Gas, coal and conventional hydro are still measured against the corrected model
#: roster (S002, S003): committed plus anticipated plus additional policy-supported; storage there is battery plus
#: pumped hydro.
_ROSTER = {
    "Wind": (11.749, 5.851),
    "Solar, utility": (10.859, 12.041),
    "Gas": (10.070, 1.324),
    "Coal": (15.285, 0.0),
    "Hydro, conventional": (6.885, 0.0),
    "Storage": (4.840, 23.360),
}

#: The CDP4 column each carrier is measured against, for the carriers still read from the draft-ISP series.
_CDP4_COLUMN = {
    "Gas": "Gas",
    "Coal": "Coal",
    "Hydro, conventional": "Hydro",
}

#: Final 2026 ISP Step Change capacity at 1 July 2029 (S006): wind, utility solar and grid-scale batteries (medium
#: and shallow storage). Supersedes the draft-ISP CDP4 reading for these three carriers.
_FINAL_ISP_2030_GW = {"Wind": 29.8, "Solar, utility": 31.2, "Storage": 33.3}

#: Carriers the model offers no new entrant for, or already exceeds the path in, so no allowance is drawn.
_NO_NEW_ENTRANT = ("Coal", "Hydro, conventional")

_SEGMENT_COLOUR = {
    "Existing": "#4c6a8c",
    "Committed, anticipated and policy-supported": "#4c9f70",
    "New-entrant allowance": "#e4a11b",
}

_ANNOTATION = (
    "Wind, utility solar and batteries are measured against the final 2026 ISP and the IASR roster commissioned by "
    "1 July 2029: the allowance is 20.5 GW of generation (12.2 GW wind, 8.3 GW solar) and 5.1 GW of batteries.<br>"
    "Gas, coal and conventional hydro are still measured against the draft-ISP CDP4 series. Coal is not shown with "
    "an allowance because closures follow announced years only, which leaves the model 2.3 GW above the path; "
    "conventional hydro has no new entrant in the model."
)


def _cdp4_2030() -> pd.Series:
    """Read AEMO's draft-ISP Step Change 2030 installed capacity by fuel, in gigawatts."""
    frame = pd.read_csv(_CDP4_CAPACITY)
    frame["year"] = frame["date"].str.extract(r"(\d{4})").astype(int)
    return frame.set_index("year").loc[2030]


def _target_gw(carrier: str, cdp4: pd.Series) -> float:
    """Return the 2030 capacity target for one carrier, in gigawatts."""
    if carrier in _FINAL_ISP_2030_GW:
        return _FINAL_ISP_2030_GW[carrier]
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
