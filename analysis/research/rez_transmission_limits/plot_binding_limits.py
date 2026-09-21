"""Plot how many campaign limits bind, by limit family, before and after the REZ relaxation.

The pre-relaxation counts are recomputed from the limits inventory's own tables (source S001 in ``source_data.md``) against the deepest
carbon cap. The post-relaxation counts come from a probe of the doubled-limit run set whose transcript is not committed, so only two
families have one and the renewable energy zone (REZ) corridor family does not reconcile with the inventory. Both facts are drawn on the
figure rather than resolved in favour of one number.

Run with ``uv run --with kaleido python analysis/research/rez_transmission_limits/plot_binding_limits.py``; writes ``binding_limits.html``
and ``binding_limits.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

_OUTPUT_STEM = Path(__file__).with_name("binding_limits")

# Limits enumerated and binding at the deepest cap (the 2060 stress chain held to 0.0005 t CO2e/MWh), counted from the inventory's tables.
# "unknown" families are omitted: the probe script does not inspect PyPSA global constraints or the biomass capacity cap.
_FAMILIES = [
    ("REZ transmission corridors", 56, 18),
    ("Flow-path expansion limits", 16, 7),
    ("REZ resource and land-use limits", 203, 24),
    ("Biomass supply tranches", 4, 1),
    ("PHES shared-site limits", 9, 0),
]

# Reported from the doubled-limit probe. The corridor pair is reported as 42 binding before and 28 after, which does not reconcile with the
# 18 + 7 = 25 corridor and flow-path limits the inventory flags at the deepest cap; the land-use pair (24 before, 14 after) does reconcile.
_PROBE_STILL_BINDING = {
    "REZ transmission corridors": 28,
    "REZ resource and land-use limits": 14,
}

_ANNOTATION = (
    "Probe counts come from a transcript that is not committed. It reports 42 corridors binding before relaxation,<br>"
    "against 25 in the inventory (18 REZ transmission plus 7 flow-path); the land-use count of 24 reconciles exactly."
)


def build_figure() -> go.Figure:
    """Assemble the binding-limits figure."""
    names = [name for name, _, _ in _FAMILIES]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=names,
            y=[enumerated for _, enumerated, _ in _FAMILIES],
            name="limits enumerated",
            marker_color="#c9d6e3",
        )
    )
    figure.add_trace(
        go.Bar(
            x=names,
            y=[binding for _, _, binding in _FAMILIES],
            name="binding at the deepest cap (inventory)",
            marker_color="#1f77b4",
        )
    )
    figure.add_trace(
        go.Bar(
            x=names,
            y=[_PROBE_STILL_BINDING.get(name) for name in names],
            name="still binding after a 2x relaxation (probe, unreconciled)",
            marker_color="#e4572e",
        )
    )
    figure.update_layout(
        title="Campaign limits by family: how many exist, how many bind, how many survive a 2x relaxation",
        yaxis_title="number of limits",
        yaxis_type="log",
        barmode="group",
        template="plotly_white",
        width=1100,
        height=650,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.25,
            "xanchor": "left",
            "x": 0,
        },
        margin={"b": 190},
    )
    figure.add_annotation(
        text=_ANNOTATION,
        xref="paper",
        yref="paper",
        x=0,
        y=-0.42,
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
