"""Derive a per-year NEM cost intensity for each AEMO 2026 ISP scenario, as a sanity reference for the campaign pathways.

AEMO's 2026 ISP generation and storage outlook publishes annual costs by class and annual generation by technology for the optimal
development path, candidate development path 4 (CDP4). ``aemo_2026_isp_cdp4_costs_generation.csv`` beside this script carries both in
long form, in thousands of real July 2023 dollars and gigawatt hours, so a cost over a generation is directly in dollars per megawatt
hour. The drawn measure is every cost class less fuel and emissions costs over generation excluding rooftop and storage, which matches
the dashboard's conversion cost (cost excluding fuel and carbon per MWh).

Run with ``uv run --with kaleido python analysis/research/aemo_scenario_cost/plot_aemo_scenario_cost.py``; writes
``aemo_scenario_cost.csv``, ``.html`` and ``.png`` beside this script.
"""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

_HERE = Path(__file__).parent
_SOURCE_CSV = _HERE / "aemo_2026_isp_cdp4_costs_generation.csv"
_OUTPUT_STEM = _HERE / "aemo_scenario_cost"
_GENERATION = "Generation excluding rooftop and storage"
_SCENARIOS = ["Slower Growth", "Step Change", "Accelerated Transition"]
_MILESTONE_YEARS = [2030, 2035, 2040, 2045, 2050]


def _wide_series() -> pd.DataFrame:
    """One row per year and scenario, one column per source series, with dollar and GWh series split by unit."""
    table = pd.read_csv(_SOURCE_CSV)
    return table.pivot_table(
        index=["financial_year_ending", "scenario"],
        columns=["unit", "series"],
        values="value",
    )


def cost_table() -> pd.DataFrame:
    """Cost per MWh generated excluding rooftop and storage for each scenario and year, split into fuel, emissions and the rest."""
    wide = _wide_series()
    costs, generation_gwh = wide["$000 real Jul-2023"], wide["GWh"][_GENERATION]
    per_year = {
        "cost_excl_fuel_emissions": costs.drop(
            columns=["Fuel costs", "Emissions costs"]
        ).sum(axis=1),
        "fuel": costs["Fuel costs"],
        "emissions_cost": costs["Emissions costs"],
        "all_cost": costs.sum(axis=1),
    }
    table = pd.DataFrame(
        {
            f"{name}_aud_per_mwh": cost / generation_gwh
            for name, cost in per_year.items()
        }
    )
    table["generation_twh"] = generation_gwh / 1000
    return table.round(3).rename_axis(["year", "scenario"]).reset_index()


def build_figure(table: pd.DataFrame) -> go.Figure:
    """One line per scenario of cost excluding fuel and emissions, the measure the dashboard draws."""
    figure = go.Figure()
    for scenario in _SCENARIOS:
        series = table[table["scenario"].eq(scenario)]
        figure.add_scatter(
            x=series["year"],
            y=series["cost_excl_fuel_emissions_aud_per_mwh"],
            name=f"2026 ISP {scenario} (CDP4)",
        )
    return figure.update_layout(
        title="NEM cost excluding fuel and emissions per MWh generated, AEMO 2026 ISP CDP4 (real July 2023 dollars)",
        xaxis_title="financial year ending",
        yaxis_title="A$/MWh generated (excluding rooftop and storage)",
        template="plotly_white",
        width=1100,
        height=700,
    )


def main() -> None:
    """Write the derived series as CSV and the figure as HTML and PNG beside this script."""
    table = cost_table()
    table.to_csv(_OUTPUT_STEM.with_suffix(".csv"), index=False, encoding="utf-8")
    figure = build_figure(table)
    figure.write_html(_OUTPUT_STEM.with_suffix(".html"), include_plotlyjs="cdn")
    figure.write_image(_OUTPUT_STEM.with_suffix(".png"), scale=2)
    milestones = table[table["year"].isin(_MILESTONE_YEARS)]
    print(
        milestones.pivot(
            index="year",
            columns="scenario",
            values="cost_excl_fuel_emissions_aud_per_mwh",
        )
        .round(1)
        .to_string()
    )


if __name__ == "__main__":
    main()
