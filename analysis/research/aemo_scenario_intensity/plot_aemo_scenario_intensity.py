"""Per-year NEM emissions intensity for each AEMO 2026 ISP scenario: the final ISP's dashboard overlay and the draft ISP's cap source.

The overlay is the final 2026 ISP generation and storage outlook's candidate development path 4 (CDP4) NEM emissions over operational
demand, from ``aemo_2026_isp_cdp4_emissions_generation.csv`` beside this script, written to ``aemo_scenario_intensity_final_isp.csv``.
Operational demand is generation excluding rooftop and storage net of storage and demand-side participation (DSP) losses: the load basis
of the campaign's own fleet intensity and of the cost overlay in ``../aemo_scenario_cost/``.

The base chain's carbon caps come from the draft ISP series in ``aemo_scenario_intensity.csv``. The draft published no per-year
emissions, so that series is derived: the draft 2026 ISP CDP4 generation outputs tracked in this repository's ``iasr outputs`` directory supply annual TWh by fuel, and the
fork's NGER cross-walk (``analysis/sharp/nger_factors.py``) supplies the combustion emission factors. Intensity is combustion emissions
over generation excluding rooftop photovoltaics, in tonnes carbon dioxide equivalent per megawatt hour, which is numerically the same as
megatonnes per terawatt hour.

Heat rates convert a fuel's electricity output back to fuel energy. Each is the median of the units burning that fuel in the 2026 final
IASR table ``heat_rates_existing_committed_anticipated_additional_generators.csv``, which lives in the input package on the data share
rather than in this repository, so the four medians are carried here as constants with that table named beside them.

Run with ``uv run --with kaleido python analysis/research/aemo_scenario_intensity/plot_aemo_scenario_intensity.py``; writes
both CSVs and ``aemo_scenario_intensity.html`` and ``.png`` beside this script.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from analysis.sharp.nger_factors import nger_factor_table

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CDP4_DIR = _REPO_ROOT / "iasr outputs"
_OUTPUT_STEM = Path(__file__).with_name("aemo_scenario_intensity")
_FINAL_SOURCE_CSV = Path(__file__).with_name(
    "aemo_2026_isp_cdp4_emissions_generation.csv"
)
_FINAL_OUTPUT_CSV = Path(__file__).with_name("aemo_scenario_intensity_final_isp.csv")

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

#: Median heat rate in GJ/MWh sent out of the IASR units burning each CDP4 fuel. Coal is the 15 sub- and super-critical steam units, gas
#: the 48 combined-cycle, open-cycle and reciprocating units, bioenergy the two biomass units. CDP4 does not separate liquid-fuelled
#: plant, so distillate takes the small open-cycle gas turbines, which is where the NGER cross-walk places diesel in the IASR fleet.
_HEAT_RATE_GJ_PER_MWH = {
    "Coal": 10.052,
    "Gas": 11.155,
    "Distillate": 12.001,
    "Bioenergy": 17.535,
}

#: Share of coal generation by energy taken as black rather than brown coal, so the coal factor is one blended number. CDP4 reports a
#: single Coal column, and the two coals carry different NGER factors.
_BLACK_COAL_SHARE = 0.75

_SCENARIO_LABELS = {
    "slower_growth": "Slower Growth",
    "step_change": "Step Change",
    "accelerated_transition": "Accelerated Transition",
}
_SCENARIO_COLOURS = {
    "slower_growth": "#d68fa8",
    "step_change": "#d4a017",
    "accelerated_transition": "#e4572e",
}
_MILESTONE_YEARS = [2030, 2040, 2050]


def _nger_total_kg_per_gj() -> pd.Series:
    """Combined Scope 1 emission factor in kg CO2e/GJ for every carrier in the NGER cross-walk, indexed by carrier."""
    return nger_factor_table().set_index("carrier")["total_co2e_kg_per_gj"]


def _fuel_factors() -> dict[str, float]:
    """Emissions per MWh generated in t CO2e/MWh for each CDP4 fuel column, from the NGER factors and the heat rates above."""
    kg_per_gj = _nger_total_kg_per_gj()
    coal = (
        _BLACK_COAL_SHARE * kg_per_gj["Black Coal"]
        + (1 - _BLACK_COAL_SHARE) * kg_per_gj["Brown Coal"]
    )
    carriers = {
        "Coal": coal,
        "Gas": kg_per_gj["Gas"],
        "Distillate": kg_per_gj["Liquid Fuel"],
        "Bioenergy": kg_per_gj["Biomass"],
    }
    return {
        fuel: factor * _HEAT_RATE_GJ_PER_MWH[fuel] / 1000
        for fuel, factor in carriers.items()
    }


def _read_cdp4(scenario: str) -> pd.DataFrame:
    """One CDP4 scenario's annual generation by fuel in TWh, with a ``year`` column parsed from its date stamp."""
    frame = pd.read_csv(
        _CDP4_DIR / f"NEM-aemo2026draft-{scenario}-CDP4 (ODP)-energy.csv"
    )
    frame["year"] = pd.to_datetime(frame["date"], format=_CDP4_DATE_FORMAT).dt.year
    return frame


def _scenario_intensity(scenario: str) -> pd.DataFrame:
    """Generation, emissions and intensity per year for one scenario: year, scenario, generation_twh, emissions_mt, t_co2e_per_mwh."""
    frame = _read_cdp4(scenario)
    generation = frame[_FUEL_COLUMNS].sum(axis=1) - frame[_ROOFTOP_COLUMN]
    emissions = sum(frame[fuel] * factor for fuel, factor in _fuel_factors().items())
    return pd.DataFrame(
        {
            "year": frame["year"],
            "scenario": _SCENARIO_LABELS[scenario],
            "generation_twh": generation.round(3),
            "emissions_mt": emissions.round(3),
            "t_co2e_per_mwh": (emissions / generation).round(5),
        }
    )


def intensity_table() -> pd.DataFrame:
    """The three scenarios' derived draft ISP intensity series, stacked and sorted by year."""
    return pd.concat(
        [_scenario_intensity(scenario) for scenario in _SCENARIO_LABELS]
    ).sort_values(["year", "scenario"], ignore_index=True)


def final_intensity_table() -> pd.DataFrame:
    """The final ISP's NEM emissions over operational demand per scenario and year, beside the emissions and energy behind it."""
    wide = pd.read_csv(_FINAL_SOURCE_CSV).pivot_table(
        index=["financial_year_ending", "scenario"], columns="series", values="value"
    )
    emissions = wide["NEM emissions"]
    generation = wide["Generation excluding rooftop and storage"] / 1000
    demand = generation + wide["Storage and DSP net generation"] / 1000
    table = pd.DataFrame(
        {
            "emissions_mt": emissions,
            "generation_twh": generation,
            "operational_demand_twh": demand,
            "t_co2e_per_mwh": (emissions / demand).round(5),
        }
    )
    return table.rename_axis(["year", "scenario"]).reset_index()


def _add_scenario_band(figure: go.Figure, table: pd.DataFrame) -> None:
    """Shade the span between the lowest and highest scenario intensity each year."""
    span = table.pivot(index="year", columns="scenario", values="t_co2e_per_mwh")
    figure.add_trace(
        go.Scatter(
            x=span.index,
            y=span.max(axis=1),
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=span.index,
            y=span.min(axis=1),
            name="2026 ISP scenario range",
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(120,120,120,0.18)",
            hoverinfo="skip",
        )
    )


def _add_scenario_lines(
    figure: go.Figure, table: pd.DataFrame, isp: str, dash: str
) -> None:
    """Add one line per scenario, coloured as the demand-trajectory plot colours the same three scenarios."""
    for scenario, label in _SCENARIO_LABELS.items():
        series = table[table["scenario"].eq(label)]
        figure.add_trace(
            go.Scatter(
                x=series["year"],
                y=series["t_co2e_per_mwh"],
                name=f"{isp} {label} (CDP4)",
                mode="lines+markers",
                line={"color": _SCENARIO_COLOURS[scenario], "width": 2, "dash": dash},
                marker={"size": 4},
            )
        )


def build_figure(draft: pd.DataFrame, final: pd.DataFrame) -> go.Figure:
    """The final ISP range and lines the dashboard draws, over the draft ISP lines the base chain's caps come from."""
    figure = go.Figure()
    _add_scenario_band(figure, final)
    _add_scenario_lines(figure, final, "2026 ISP", "solid")
    _add_scenario_lines(figure, draft[draft["year"].ge(2026)], "draft ISP", "dot")
    figure.update_layout(
        title="NEM emissions intensity, AEMO 2026 ISP CDP4 (dashboard overlay, solid) and draft ISP (base chain caps, dotted)",
        xaxis_title="financial year ending",
        yaxis_title="t CO2e/MWh (2026 ISP: per MWh of operational demand<br>draft ISP: per MWh generated excluding rooftop)",
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
    """Write both derived series as CSV and the figure as HTML and PNG beside this script."""
    draft, final = intensity_table(), final_intensity_table()
    draft.to_csv(_OUTPUT_STEM.with_suffix(".csv"), index=False, encoding="utf-8")
    final.to_csv(_FINAL_OUTPUT_CSV, index=False, encoding="utf-8", float_format="%.6g")
    figure = build_figure(draft, final)
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)
    for table in (draft, final):
        milestones = table[table["year"].isin(_MILESTONE_YEARS)]
        pivot = milestones.pivot(
            index="year", columns="scenario", values="t_co2e_per_mwh"
        )
        print(pivot.to_string())


if __name__ == "__main__":
    main()
