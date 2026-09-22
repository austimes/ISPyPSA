"""Plot the proposed stepped social licence premium against the published anchors that bracket it.

The step curve is the premium a megawatt of relaxed renewable energy zone (REZ) or corridor capacity would pay on top of
AEMO's published per-megawatt expansion price, drawn against the relaxation factor. The horizontal reference lines are the
published figures that bound the proposal: AEMO's own penalty for building past a REZ resource limit, its penalty for building
outside a REZ, and the landholder payment schemes it already carries as costs. Derivations and sources are in ``research.md``.

Run with ``uv run --with kaleido python analysis/research/social_licence_premium/plot_social_licence_premium.py``; writes
``social_licence_premium.html`` and ``social_licence_premium.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

_OUTPUT_STEM = Path(__file__).with_name("social_licence_premium")

# Capacity-weighted expansion price per megawatt (A$2025), computed over every augmentation option that publishes a capacity,
# an easement length and a cost: 65 REZ options and 33 flow-path options.
_BASE_PRICE = {"REZ transmission": 1_075_349.0, "Sub-region corridors": 1_150_983.0}

# Proposed premium on the option's own published price, by relaxation tranche.
_TRANCHES = ((1.0, 2.0, 0.15), (2.0, 4.0, 0.60))

_SERIES_COLOUR = {"REZ transmission": "#1f77b4", "Sub-region corridors": "#e4572e"}

# Published figures that bracket the proposal, as a premium in A$/MW. The two penalties are AEMO's price for a megawatt built
# past a REZ resource limit and for one built outside a REZ; the payment line is the NSW scheme at AEMO's own easement lengths.
_ANCHORS = (
    (
        "AEMO REZ resource limit violation penalty, in-REZ (A$0.3M/MW)",
        300_000.0,
        "#7f7f7f",
    ),
    ("AEMO violation penalty outside a REZ (A$1.0M/MW)", 1_000_000.0, "#444444"),
    (
        "NSW landholder payments at AEMO easement lengths (A$29,880/MW)",
        29_880.0,
        "#2ca02c",
    ),
)

_ANNOTATION = (
    "Premium is charged on the option's own published A$/MW, so it scales with a price range spanning two orders of "
    "magnitude.<br>"
    "First tranche: AEMO's 15% transmission cost impost for low social licence. Second tranche: the top of AEMO's "
    "+5% to +60% uplift<br>"
    "graduated by private land parcel density, transferred from REZ generation build cost to transmission expansion cost."
)


def _step_points(base_price: float) -> tuple[list[float], list[float]]:
    """Build the staircase of relaxation factor against premium in A$/MW for one base price.

    Each tranche contributes a vertical riser at its lower bound and a flat tread to its upper bound, so the premium a
    megawatt pays is read off the tread it falls under rather than interpolated between tranches.
    """
    factors = [0.0, _TRANCHES[0][0]]
    premiums = [0.0, 0.0]
    for start, end, rate in _TRANCHES:
        factors += [start, end]
        premiums += [base_price * rate, base_price * rate]
    return factors, premiums


def build_figure() -> go.Figure:
    """Assemble the stepped premium figure with its published anchors."""
    figure = go.Figure()
    for name, base_price in _BASE_PRICE.items():
        factors, premiums = _step_points(base_price)
        figure.add_trace(
            go.Scatter(
                x=factors,
                y=premiums,
                name=f"{name} (base A${base_price:,.0f}/MW)",
                mode="lines",
                line={"color": _SERIES_COLOUR[name], "width": 3},
            )
        )
    for label, value, colour in _ANCHORS:
        figure.add_hline(
            y=value,
            line={"color": colour, "width": 1, "dash": "dot"},
            annotation_text=label,
            annotation_position="top left",
            annotation_font={"size": 10, "color": colour},
        )
    figure.update_layout(
        title="Proposed social licence premium on relaxed REZ and corridor capacity, against AEMO's published anchors",
        xaxis_title="capacity as a multiple of AEMO's published limit",
        yaxis_title="premium on the published expansion price (A$2025 per MW)",
        template="plotly_white",
        width=1100,
        height=650,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 230},
    )
    figure.update_xaxes(range=[0, 4.2], dtick=1)
    figure.add_annotation(
        text=_ANNOTATION,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.46,
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
