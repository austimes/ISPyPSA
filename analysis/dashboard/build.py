"""Turn one or more campaign runs' export CSVs into a single self-contained ``dashboard.html``.

Five CSVs are read from ``<run>/exports/``: ``results.csv`` (one row per cell and year),
``marginals.csv`` (the cost and emissions consequence of stepping from one demand trajectory to
the next), ``manifest.csv`` and ``acceptance_per_cell.csv`` (caps, shadow prices and solve status)
and ``storage.csv`` (installed power by carrier and duration class). They are joined into one tidy
frame, one row per cell-year, and every figure in :mod:`analysis.dashboard.figures` reads it. Given
several runs, their frames are stacked and the run set each row came from names the run directory it
was read from. The source commit shown in the page heading is read from each run's solve records,
``<run>/records/*.json``, and the assumptions table from its ``<run>/campaign/``.

The page carries plotly's javascript inline, so it opens straight off the data share with no
server and no build step.
"""

from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path
from typing import Annotated

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from cyclopts import Parameter
from plotly.offline import get_plotlyjs

from analysis.dashboard import figures
from analysis.env import OutputLayout

log = logging.getLogger(__name__)

#: One or more run directories, so the page can compare runs.
Runs = Annotated[list[Path], Parameter(consume_multiple=True)]

#: Results columns carried through unchanged, and the ones renamed for the figures.
RESULT_KEYS = [
    "cell",
    "trajectory",
    "pressure",
    "pressure_kind",
    "pressure_value",
    "year",
    "delivered_twh",
    "boundary",
    "co2e_total_kt_per_yr",
    "use_pct_of_demand",
    "cost_per_mwh_excl_fuel_carbon",
    "diagnostic_fuel_cost_per_mwh",
    "diagnostic_carbon_cost_per_mwh",
    "carried_capex_aud_per_yr",
    "existing_fleet_fom_aud_per_yr",
]
RESULT_MEASURES = {
    "co2e_total_t_per_mwh": "fleet_intensity",
    "avg_cost_aud_per_mwh": "avg_cost",
    "total_cost_aud_per_yr": "total_cost",
}

#: Marginals columns renamed so they join the results frame on its own trajectory key.
MARGINAL_MEASURES = {
    "to_level": "trajectory",
    "marginal_cost_aud_per_mwh": "marginal_cost",
    "marginal_co2e_t_per_mwh": "marginal_intensity",
}

#: Manifest columns the figures need: the solve status, each cap chain's cap tonnage and the shadow
#: price that cap carried.
MANIFEST_KEYS = [
    "cell",
    "year",
    "model_status",
    "co2_cap_annual_t",
    "implied_carbon_price_aud_per_t",
]

#: The two per-cell acceptance tests a solve has to pass to count as solved.
ACCEPTANCE_TESTS = ["test1_serves_demand", "test4_termination"]


def tidy_frame(exports: Path) -> pd.DataFrame:
    """Join the five export CSVs into one row per cell and milestone year.

    :param exports: The run's ``exports/`` directory.
    :return: The run set the rows came from, named after the run directory, then trajectory and
        pressure keys, delivered energy, both emissions intensities, cost and its components, the
        cap and its shadow price, boundary flag, solve status and the per-carrier generation shares
        and storage power.
    """
    results = pd.read_csv(exports / "results.csv").rename(columns=RESULT_MEASURES)
    marginals = pd.read_csv(exports / "marginals.csv").rename(columns=MARGINAL_MEASURES)
    manifest = pd.read_csv(exports / "manifest.csv")[MANIFEST_KEYS]
    acceptance = pd.read_csv(exports / "acceptance_per_cell.csv")[
        ["cell", "year", *ACCEPTANCE_TESTS]
    ]
    storage = _storage_power_columns(pd.read_csv(exports / "storage.csv"))
    shares = list(results.filter(regex=r"^share_"))
    frame = results[[*RESULT_KEYS, *RESULT_MEASURES.values(), *shares]].merge(
        marginals[
            ["pressure", "year", "trajectory", "marginal_cost", "marginal_intensity"]
        ],
        on=["pressure", "year", "trajectory"],
        how="left",
        validate="many_to_one",
    )
    _log_unmatched_marginals(frame)
    frame = (
        frame.merge(manifest, on=["cell", "year"], how="left")
        .merge(acceptance, on=["cell", "year"], how="left")
        .merge(storage, on=["cell", "year"], how="left")
    )
    return frame.assign(
        run_set=exports.parent.name,
        status=_status_label(frame),
        pressure_name=frame["pressure"].map(figures.pressure_label),
    )


def _storage_power_columns(storage: pd.DataFrame) -> pd.DataFrame:
    """Installed storage power as one column per carrier and duration class, keyed on cell and year."""
    wide = storage.pivot_table(
        index=["cell", "year"], columns=["carrier", "duration_class"], values="power_gw"
    )
    wide.columns = [
        f"storage_{carrier}_{duration}" for carrier, duration in wide.columns
    ]
    return wide.reset_index()


def _log_unmatched_marginals(frame: pd.DataFrame) -> None:
    """Report cell-years whose trajectory has no adjacent-trajectory step to take a marginal from."""
    unmatched = frame["marginal_intensity"].isna()
    if unmatched.any():
        trajectories = sorted(frame.loc[unmatched, "trajectory"].unique())
        log.info(
            f"Cell-years with no matching marginal: {int(unmatched.sum())}, "
            f"in trajectories {trajectories}"
        )


def _status_label(frame: pd.DataFrame) -> pd.Series:
    """Label each cell-year ``solved`` or ``unaccepted`` from its solver status and acceptance tests."""
    passed = frame[ACCEPTANCE_TESTS].eq(True).all(axis=1)
    accepted = passed & frame["model_status"].eq("Optimal")
    return pd.Series(np.where(accepted, "solved", "unaccepted"), index=frame.index)


#: Page heading to section builder, in the order the dashboard shows them. A builder returns either
#: a plotly figure or ready-made html, and ``None`` where the run holds too little to draw.
SECTIONS = {
    "Cost frontier": figures.figure_cost_frontier,
    "Cost frontier, animated by year": figures.figure_cost_frontier_animated,
    "Cost frontier, years overlaid": figures.figure_cost_frontier_overlaid,
    "Cost against emissions intensity": figures.figure_cost_families,
    "Cost surface over demand and marginal intensity": figures.figure_cost_contours,
    "Cost surface as heatmap": figures.figure_cost_heatmap,
    "Cost pathway over time": figures.figure_cost_pathway,
    "Implied carbon price of each cap": figures.figure_implied_carbon_price,
    "Marginal cost and intensity of demand": figures.figure_demand_marginals,
    "Cost decomposition, central trajectory": figures.figure_cost_decomposition,
    "Cap tracking and unserved energy": figures.figure_cap_tracking,
    "Summary measure matrix": figures.figure_summary_matrix,
    "Parallel coordinates": figures.figure_parallel_coordinates,
    "Searched parameter grid": figures.html_search_grid,
    "Technology mix": figures.figure_tech_mix,
    "Storage build": figures.figure_storage_build,
}

#: The run-assumptions table, which reads the runs themselves rather than the tidy frame, and so
#: sits outside ``SECTIONS``. It is shown under the section it follows.
ASSUMPTIONS_HEADING = "Assumptions by run"
ASSUMPTIONS_FOLLOWS = "Technology mix"

#: Columns of the assumptions table, in the order it lists them.
ASSUMPTION_KEYS = ["run_set", "rez_limit_factor", "max_cap", "chains", "inputs"]


#: Each section sits in a box of its own height, which the divider below it drags taller or shorter.
SECTION_WRAPPER = (
    '<div class="box" style="overflow: auto; height: {height}px">{body}</div>'
)

#: Height for a section that sets none of its own, in pixels, and the room a box leaves around a
#: figure for the plotly modebar above it.
DEFAULT_SECTION_HEIGHT = 500
SECTION_PADDING = 40

#: Full-width grab bar under one figure's box, dragged to set that box's height.
DIVIDER = (
    '<div class="divider" style="height: 8px; background: #bbb; '
    'cursor: row-resize"></div>'
)

#: Everything the page does once it is open: drag a divider to resize the box above it, click a
#: table heading to sort on that column, and click a plot's fullscreen button to blow its box up.
#: The button is added by re-rendering each plot with plotly's own modebar hook, which drops the
#: plot's animation frames, so the animated figure's frames are put back and it keeps its year
#: slider. Each divider is paired with its box by position, because plotly parks a hidden measuring
#: svg in the body next to the first plot, which leaves the first divider no box as a previous sibling.
PAGE_SCRIPT = """<script>
const fit = box => {
  const plot = box.querySelector(".js-plotly-plot");
  if (plot) Plotly.Plots.resize(plot);
};
const bars = document.querySelectorAll(".divider");
document.querySelectorAll(".box").forEach((box, section) => bars[section].addEventListener("mousedown", start => {
  const height = box.offsetHeight;
  const drag = move => {
    box.style.height = `${height + move.clientY - start.clientY}px`;
    fit(box);
  };
  const stop = () => {
    document.removeEventListener("mousemove", drag);
    document.removeEventListener("mouseup", stop);
  };
  document.addEventListener("mousemove", drag);
  document.addEventListener("mouseup", stop);
}));
document.querySelectorAll(".grid th").forEach(head => head.addEventListener("click", () => {
  const body = head.closest("table").querySelector("tbody"), rows = [...body.rows];
  const text = row => row.cells[head.cellIndex].textContent;
  const sign = head.dataset.descending ? -1 : 1;
  rows.sort((left, right) => {
    const numeric = parseFloat(text(left)) - parseFloat(text(right));
    return sign * (isNaN(numeric) ? text(left).localeCompare(text(right)) : numeric);
  });
  head.dataset.descending = head.dataset.descending ? "" : "yes";
  rows.forEach(row => body.appendChild(row));
}));
window.addEventListener("load", () => document.querySelectorAll(".js-plotly-plot").forEach(plot => {
  const button = {name: "fullscreen", title: "Fullscreen", icon: Plotly.Icons.autoscale,
    click: gd => document.fullscreenElement
      ? document.exitFullscreen() : gd.closest(".box").requestFullscreen()};
  const frames = ((plot._transitionData || {})._frames || []).slice();
  Plotly.react(plot, plot.data, plot.layout, {responsive: true, modeBarButtonsToAdd: [button]})
    .then(() => frames.length ? Plotly.addFrames(plot, frames) : null);
}));
document.addEventListener("fullscreenchange", () => (document.fullscreenElement
  ? [document.fullscreenElement] : [...document.querySelectorAll(".box")]).forEach(fit));
</script>"""


def _section_box(body: go.Figure | str) -> str:
    """Box one section at its own height: html a builder wrote, or a figure stretched to fill the box.

    A figure carrying its own ``layout.height`` would keep that height however far the box is
    dragged, so the box takes the height over and the figure is left to autosize into it.
    """
    if isinstance(body, str):
        return SECTION_WRAPPER.format(height=DEFAULT_SECTION_HEIGHT, body=body)
    height = int(body.layout.height or DEFAULT_SECTION_HEIGHT) + SECTION_PADDING
    body.update_layout(height=None, width=None, autosize=True)
    html = body.to_html(
        full_html=False, include_plotlyjs=False, config={"responsive": True}
    )
    return SECTION_WRAPPER.format(height=height, body=html)


def _drawn_sections(
    frame: pd.DataFrame, layouts: list[OutputLayout]
) -> list[tuple[str, go.Figure | str | None]]:
    """Every section in page order, with the run-assumptions table under the technology mix."""
    drawn = [(heading, build(frame)) for heading, build in SECTIONS.items()]
    under = list(SECTIONS).index(ASSUMPTIONS_FOLLOWS) + 1
    assumptions = (ASSUMPTIONS_HEADING, _html_assumptions(layouts))
    return [*drawn[:under], assumptions, *drawn[under:]]


def _html_assumptions(layouts: list[OutputLayout]) -> str:
    """The assumptions each run was launched under, one row per run, styled like the searched grid."""
    rows = pd.DataFrame(
        [_assumptions_row(layout) for layout in layouts], columns=ASSUMPTION_KEYS
    )
    return figures.GRID_STYLE + rows.fillna("").to_html(index=False, classes="grid")


def _assumptions_row(layout: OutputLayout) -> dict[str, object]:
    """One run's recorded assumptions, or the inputs package it named instead, or neither."""
    recorded = layout.campaign / "assumptions.json"
    inputs = layout.campaign / "inputs.txt"
    if recorded.exists():
        return {
            "run_set": layout.root.name,
            **json.loads(recorded.read_text(encoding="utf-8")),
        }
    named = inputs.read_text(encoding="utf-8").strip() if inputs.exists() else ""
    return {"run_set": layout.root.name, "inputs": named}


def _provenance(layouts: list[OutputLayout]) -> str:
    """Name every run directory the page draws, and the source commit each one's solves recorded."""
    named = [f"{layout.root}: {_commits(layout)}" for layout in layouts]
    return (
        f"<h1>Campaign dashboard: {', '.join(layout.root.name for layout in layouts)}</h1>"
        f"<p>Run directory and source commit<br>{'<br>'.join(named)}</p>"
    )


def _commits(layout: OutputLayout) -> str:
    """The source commits one run's solve records name."""
    records = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in layout.records.glob("*.json")
    )
    commits = sorted({record.get("source_git_commit") for record in records} - {None})
    return ", ".join(commits) or "not recorded"


def main(run: Runs, show: bool = False) -> Path:
    """Write ``dashboard.html`` into the first run directory, from every named run's exports.

    :param run: One or more stamped run directories, each holding an ``exports/`` sub-directory.
        Named more than one, the page compares them: the figures that can carry a run set
        distinguish the runs, and the assumptions table lists what each was launched under.
    :param show: Open the finished page in the default browser.
    :return: The path written.
    """
    layouts = [OutputLayout(path) for path in run]
    frame = pd.concat(
        [tidy_frame(layout.exports) for layout in layouts], ignore_index=True
    )
    sections = [_provenance(layouts), f"<script>{get_plotlyjs()}</script>"]
    for heading, body in _drawn_sections(frame, layouts):
        if body is None:
            continue
        sections.append(f"<h2>{heading}</h2>")
        sections.append(_section_box(body))
        sections.append(DIVIDER)
    sections.append(PAGE_SCRIPT)
    page = layouts[0].root / "dashboard.html"
    page.write_text("\n".join(sections), encoding="utf-8")
    if show:
        webbrowser.open(page.as_uri())
    return page
