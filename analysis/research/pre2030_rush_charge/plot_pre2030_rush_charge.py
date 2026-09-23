"""Plot the pre-2030 rush charge against what a new megawatt already costs in 2030.

Derives the generation and storage rush adders from ShARP's A$37.447769/MWh short-lead-time charge and draws them beside
the 2030 annuitised capital cost and the build-rate premium's first adder for wind, solar and batteries. The annuities are
recovered from the build-rate premium file the model reads, whose first adder is 17.5% of each group's annuity.
Derivations and sources are in ``research.md``.

Run with ``uv run --with kaleido python analysis/research/pre2030_rush_charge/plot_pre2030_rush_charge.py``; writes
``pre2030_rush_charge.html`` and ``pre2030_rush_charge.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PREMIUM_CSV = (
    _REPO_ROOT / "analysis" / "model" / "data" / "build_rate_premiums_central.csv"
)
_CDP4_STEM = _REPO_ROOT / "iasr outputs" / "NEM-aemo2026draft-step_change-CDP4 (ODP)"
_OUTPUT_STEM = Path(__file__).with_name("pre2030_rush_charge")

#: ShARP A045 short-lead-time charge, A$2024 per MWh delivered.
_SHARP_RUSH_AUD_2024_PER_MWH = 37.447769
#: ABS CPI June quarter 2025 over the mean of the four 2024 quarters.
_CPI_2024_TO_JUNE_2025 = 141.7 / 138.675
#: ShARP A052 delivery factor: MWh delivered per MWh of NEM generation.
_DELIVERED_PER_GENERATED = 0.7914939324516337
#: Base chain of run 2026-09-22T22.46_sc5, 2030 period: 12.016 TWh discharged from 14.59 GW of batteries.
_BATTERY_DISCHARGE_HOURS = 12.016e6 / 14_590
#: Share of annuitised capex the build-rate premium's first adder charges.
_FIRST_ADDER_SHARE = 0.175
_HOURS_PER_YEAR = 8_760
_NEW_BUILD_FUELS = ["Wind", "Solar (Utility)", "Gas"]
_ENERGY_FUELS = ["Wind", "Solar (Utility)"]


def _cdp4_row(kind: str, year: int) -> pd.Series:
    """One year's row of the Step Change CDP4 capacity (GW) or energy (TWh) file."""
    frame = pd.read_csv(f"{_CDP4_STEM}-{kind}.csv")
    frame.index = frame.pop("date").str.extract(r"(\d{4})")[0].astype(int)
    return frame.loc[year]


def new_build_capacity_factor() -> float:
    """Added wind and solar energy over added wind, solar and gas capacity, FY2026 to FY2030."""
    added_gw = _cdp4_row("capacity", 2030) - _cdp4_row("capacity", 2026)
    added_twh = _cdp4_row("energy", 2030) - _cdp4_row("energy", 2026)
    return (
        added_twh[_ENERGY_FUELS].sum()
        * 1e3
        / (added_gw[_NEW_BUILD_FUELS].sum() * _HOURS_PER_YEAR)
    )


def rush_adders() -> dict[str, float]:
    """Generation and storage rush adders, A$/MW/yr in real June 2025 dollars."""
    per_mwh_generated = (
        _SHARP_RUSH_AUD_2024_PER_MWH * _CPI_2024_TO_JUNE_2025 * _DELIVERED_PER_GENERATED
    )
    return {
        "generation": per_mwh_generated * _HOURS_PER_YEAR * new_build_capacity_factor(),
        "storage": per_mwh_generated * _BATTERY_DISCHARGE_HOURS,
    }


def _first_adders_2030() -> pd.Series:
    """The build-rate premium's first adder in 2030 per carrier group, A$/MW/yr."""
    curve = pd.read_csv(_PREMIUM_CSV)
    rows = curve[
        (curve["financial_year"] == 2030) & (curve["tranche"] == "accelerated_rate")
    ]
    return rows.set_index("group")["adder_$/mw/yr"]


def build_figure() -> go.Figure:
    """Rush adders as horizontal lines over grouped bars of annuity and first build-rate adder per carrier."""
    adders = rush_adders()
    first = _first_adders_2030()[["Wind", "Solar", "Battery"]]
    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=first.index,
            y=first / _FIRST_ADDER_SHARE,
            name="annuitised capital cost, 2030",
            marker_color="#4c6a8c",
        )
    )
    figure.add_trace(
        go.Bar(
            x=first.index,
            y=first,
            name="build-rate premium, first adder (+17.5%)",
            marker_color="#4c9f70",
        )
    )
    styles = {"generation": ("#e4572e", "dash"), "storage": ("#7b2d8e", "dot")}
    for kind, value in adders.items():
        colour, dash = styles[kind]
        figure.add_hline(
            y=value,
            line={"color": colour, "dash": dash, "width": 2.5},
            annotation_text=f"{kind} rush charge {value:,.0f}",
            annotation_position="top right",
        )
    figure.update_layout(
        title="Pre-2030 rush charge against the 2030 cost of a new megawatt",
        yaxis_title="A$2025 per MW per year",
        barmode="group",
        template="plotly_white",
        width=1000,
        height=620,
        legend={"orientation": "h", "yanchor": "top", "y": -0.12, "x": 0},
    )
    return figure


def main() -> None:
    """Build the figure and write it as HTML and PNG beside this script."""
    figure = build_figure()
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)


if __name__ == "__main__":
    main()
