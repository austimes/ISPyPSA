"""Turn one campaign run's export CSVs into a single self-contained ``dashboard.html``.

Five CSVs are read from ``<run>/exports/``: ``results.csv`` (one row per cell and year),
``marginals.csv`` (the cost and emissions consequence of stepping from one demand trajectory to
the next), ``manifest.csv`` and ``acceptance_per_cell.csv`` (caps, shadow prices and solve status)
and ``storage.csv`` (installed power by carrier and duration class). They are joined into one tidy
frame, one row per cell-year, and every figure in :mod:`analysis.dashboard.figures` reads it. The
source commit shown in the page heading is read from the run's solve records,
``<run>/records/*.json``, and the assumptions table from its ``<run>/campaign/``.

Several sections read the run directory rather than the tidy frame: the assumptions table; the
technology cost inputs, from ``exports/input_costs.csv`` where the assemble stage found templated
inputs on disk to read them from; the transmission build, from ``exports/transmission.csv`` and the
relaxation factors the run recorded in ``<run>/campaign/``; the increment grid, from
``exports/increments.csv`` where the campaign solved branch cells; the duals, from
``exports/per_chain/duals_<base cell>.csv``; the near-term pipeline, from the base solve's own
templated ``ecaa_*`` rosters; and the priced build curves, from each base solve's
``outputs/capacity_tranches.json`` and relaxation tranches plus the build-rate curve the run was
launched with.

The page carries plotly's javascript inline, so it opens straight off the data share with no
server and no build step.
"""

from __future__ import annotations

import json
import logging
import webbrowser
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

from analysis.dashboard import figures
from analysis.env import MODEL_DATA, OutputLayout
from analysis.sharp.deliverables import BRANCH_COLUMNS, base_rows

log = logging.getLogger(__name__)

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
    :return: Trajectory and pressure keys, delivered energy, both emissions intensities, cost and
        its components, the cap and its shadow price, boundary flag, solve status and the
        per-carrier energy delivered, per-fuel input intensities, priced-curve premiums and
        storage power, for the campaign's base chains. Increment-grid branches have their own
        section instead.
    """
    results = base_rows(
        pd.read_csv(exports / "results.csv").rename(columns=RESULT_MEASURES)
    )
    marginals = pd.read_csv(exports / "marginals.csv").rename(columns=MARGINAL_MEASURES)
    manifest = pd.read_csv(exports / "manifest.csv")[MANIFEST_KEYS]
    acceptance = pd.read_csv(exports / "acceptance_per_cell.csv")[
        ["cell", "year", *ACCEPTANCE_TESTS]
    ]
    storage = _storage_power_columns(pd.read_csv(exports / "storage.csv"))
    carriers = list(results.filter(regex=r"^twh_"))
    fuels = list(results.filter(regex=r"^gj_per_mwh_"))
    premiums = list(results.filter(regex=r"_premium_aud_per_yr$"))
    frame = results[
        [*RESULT_KEYS, *RESULT_MEASURES.values(), *carriers, *fuels, *premiums]
    ].merge(
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
        status=_status_label(frame),
        pressure_name=frame["pressure"].map(figures.pressure_label),
    )


def tidy_branches(exports: Path) -> pd.DataFrame:
    """The increment grid's branch rows of ``results.csv``, keyed on the increment cell each solved.

    :param exports: The run's ``exports/`` directory.
    :return: One row per branch cell, carrying the base cell it branched from, its branch year, the
        measures the pathway-intensity panels draw, and an ``increment`` key naming its two levels.
        A run with no increment grid returns those columns with no rows.
    """
    results = pd.read_csv(exports / "results.csv").rename(columns=RESULT_MEASURES)
    if not set(BRANCH_COLUMNS) <= set(results):
        return pd.DataFrame(columns=["base_cell", "year", "increment"])
    branches = results[results["base_cell"].notna()]
    levels = branches["demand_level"] + "_" + branches["intensity_level"]
    return branches.assign(increment=levels)


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


#: Heading of the pathway-intensity row, which both the increment fans and the pipeline hang off.
INTENSITIES_HEADING = "Pathway intensities (every chain, ShARP-style)"

#: Heading of the increment cells' technology mix, which the transmission build hangs off.
INCREMENT_MIX_HEADING = "Technology mix of increment cells"

#: Page heading to section builder, in the order the dashboard shows them. A builder returns either
#: a plotly figure or ready-made html, and ``None`` where the run holds too little to draw.
SECTIONS = {
    INTENSITIES_HEADING: figures.figure_pathway_intensities,
    "Cost frontier": figures.figure_cost_frontier,
    "Cost against emissions intensity": figures.figure_cost_families,
    "Cost surface as heatmap": figures.figure_cost_heatmap,
    "Technology mix": figures.figure_tech_mix,
    INCREMENT_MIX_HEADING: figures.figure_increment_tech_mix,
    "Storage build": figures.figure_storage_build,
    "Cost pathway over time": figures.figure_cost_pathway,
    "Implied carbon price of each cap": figures.figure_implied_carbon_price,
    "Demand-marginal cost and intensity (step to the next demand trajectory)": figures.figure_demand_marginals,
    "Cost decomposition, central trajectory": figures.figure_cost_decomposition,
    "Premiums paid above AEMO's limits and baseline build rates": figures.figure_premiums_paid,
    "Summary measure matrix": figures.figure_summary_matrix,
    "Searched parameter grid": figures.html_search_grid,
}

#: Heading of the run-assumptions table, which the tests name.
ASSUMPTIONS_HEADING = "Assumptions"


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
#: The button is added by re-rendering each plot with plotly's own modebar hook. Each divider is
#: paired with its box by position, because plotly parks a hidden measuring svg in the body next to
#: the first plot, which leaves the first divider no box as a previous sibling.
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
  Plotly.react(plot, plot.data, plot.layout, {responsive: true, modeBarButtonsToAdd: [button]});
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
    frame: pd.DataFrame, layout: OutputLayout
) -> list[tuple[str, go.Figure | str | None]]:
    """Every section in page order, each run-directory section spliced under the one it follows."""
    branches = tidy_branches(layout.exports)
    fanned = partial(figures.figure_pathway_intensities, branches=branches)
    mixed = partial(figures.figure_increment_tech_mix, branches=branches)
    sections = {**SECTIONS, INTENSITIES_HEADING: fanned, INCREMENT_MIX_HEADING: mixed}
    drawn = []
    for heading, build_from_frame in sections.items():
        drawn.append((heading, build_from_frame(frame)))
        if heading in RUN_SECTIONS:
            title, build_from_run = RUN_SECTIONS[heading]
            drawn.append((title, build_from_run(layout)))
    return drawn


def _figure_input_costs(layout: OutputLayout) -> go.Figure | None:
    """The run's cost inputs, or nothing where the assemble stage found no templated inputs to read."""
    costs = layout.exports / "input_costs.csv"
    if not costs.exists():
        return None
    return figures.figure_input_costs(pd.read_csv(costs))


def _figure_transmission_limits(layout: OutputLayout) -> go.Figure | None:
    """The run's network build against its limits, or nothing where the run exported no link table.

    A ``None`` relaxation factor means the run was launched unrelaxed, so both ceilings coincide.
    """
    links = layout.exports / "transmission.csv"
    if not links.exists():
        return None
    assumptions = _assumptions(layout)
    return figures.figure_transmission_limits(
        pd.read_csv(links),
        assumptions.get("rez_limit_factor") or 1.0,
        assumptions.get("flow_path_limit_factor") or 1.0,
    )


def _figure_increment_surfaces(layout: OutputLayout) -> go.Figure | None:
    """The run's increment grid, or nothing where the campaign solved no branch cells."""
    increments = layout.exports / "increments.csv"
    if not increments.exists():
        return None
    return figures.figure_increment_surfaces(pd.read_csv(increments))


#: Solve flag naming the build-rate curve a run was launched with.
BUILD_RATE_FLAG = "--build-rate-premiums"


def _base_results(layout: OutputLayout) -> pd.DataFrame:
    """The campaign's base chain rows of ``results.csv``, one per cell and milestone year."""
    return base_rows(pd.read_csv(layout.exports / "results.csv"))


def _figure_build_cost_curves(layout: OutputLayout) -> go.Figure | None:
    """The build curves the run priced, or nothing where no base solve priced a tranche."""
    steps = [
        _tranche_steps(layout.run_dir(f"{row.cell}_{row.year}"))
        for row in _base_results(layout).itertuples()
    ]
    drawn = [frame for frame in [*steps, _build_rate_steps(layout)] if not frame.empty]
    if not drawn:
        return None
    return figures.figure_build_cost_curves(
        pd.concat(drawn).drop_duplicates(["curve", "group", "tranche"])
    )


def _tranche_steps(run: Path) -> pd.DataFrame:
    """One solve's priced capacity tranches and REZ relaxation tranches, as curve steps."""
    priced = run / "outputs" / "capacity_tranches.json"
    relax = run / "pypsa_friendly" / "custom_constraints_generators.csv"
    steps = [
        figures.tranche_curve_steps(pd.read_json(priced)) if priced.exists() else None,
        figures.relax_curve_steps(pd.read_csv(relax)) if relax.exists() else None,
    ]
    read = [frame for frame in steps if frame is not None]
    return pd.concat(read) if read else pd.DataFrame(columns=figures.CURVE_STEP_COLUMNS)


def _build_rate_steps(layout: OutputLayout) -> pd.DataFrame:
    """The build-rate curve the run was launched with, or nothing where its flags named none."""
    flags = (_assumptions(layout).get("solve_flags") or "").split()
    if BUILD_RATE_FLAG not in flags:
        return pd.DataFrame(columns=figures.CURVE_STEP_COLUMNS)
    named = Path(flags[flags.index(BUILD_RATE_FLAG) + 1]).name
    return figures.build_rate_curve_steps(pd.read_csv(MODEL_DATA / named))


def _figure_near_term_pipeline(layout: OutputLayout) -> go.Figure | None:
    """The pinned near-term fleet, or nothing where the base solve's templated inputs are gone."""
    base = _base_results(layout)
    pinned = base[base["year"].eq(figures.PIPELINE_YEAR)]
    rosters = [
        layout.run_dir(f"{cell}_{figures.PIPELINE_YEAR}") / "ispypsa_inputs"
        for cell in pinned["cell"]
    ]
    on_disk = [inputs for inputs in rosters if inputs.is_dir()]
    if not on_disk:
        return None
    return figures.figure_near_term_pipeline(
        _ecaa_roster(on_disk[0]), pinned, _allowances(layout)
    )


def _ecaa_roster(inputs: Path) -> pd.DataFrame:
    """The existing, committed and anticipated generators and batteries one solve was templated with."""
    rosters = [
        pd.read_csv(inputs / f"ecaa_{name}.csv") for name in ("generators", "batteries")
    ]
    return pd.concat(rosters, ignore_index=True)


def _allowances(layout: OutputLayout) -> dict[str, float]:
    """The new-entrant build allowances the run's near-term pin was launched with, in GW."""
    recorded = {**_plan(layout), **_assumptions(layout)}
    return {
        label: recorded[key] / 1e3
        for key, label in figures.ALLOWANCE_LABELS.items()
        if recorded.get(key)
    }


def _figure_duals(layout: OutputLayout) -> go.Figure | None:
    """The run's duals, or nothing where no base chain exported a constraint dual table."""
    exported = [
        path
        for cell in _base_results(layout)["cell"].unique()
        if (path := layout.exports / "per_chain" / f"duals_{cell}.csv").exists()
    ]
    if not exported:
        return None
    duals = pd.concat([pd.read_csv(path) for path in exported], ignore_index=True)
    return figures.figure_duals(pd.read_csv(layout.exports / "manifest.csv"), duals)


def _html_assumptions(layout: OutputLayout) -> str:
    """The assumptions the run was launched under, one row per assumption, styled like the searched grid."""
    rows = pd.DataFrame(_assumptions(layout).items(), columns=["assumption", "value"])
    return figures.GRID_STYLE + rows.to_html(index=False, classes="grid")


def _plan(layout: OutputLayout) -> dict[str, object]:
    """The demand plan the launch copied into the run, or nothing where it copied none."""
    plan = layout.campaign / "demand_plan.json"
    return json.loads(plan.read_text(encoding="utf-8")) if plan.exists() else {}


def _assumptions(layout: OutputLayout) -> dict[str, object]:
    """The run's recorded assumptions, or the inputs package it named instead, or neither."""
    recorded = layout.campaign / "assumptions.json"
    if recorded.exists():
        return json.loads(recorded.read_text(encoding="utf-8"))
    inputs = layout.campaign / "inputs.txt"
    named = inputs.read_text(encoding="utf-8").strip() if inputs.exists() else ""
    return {"inputs": named}


#: Sections built from the run directory rather than the tidy frame, each keyed on the ``SECTIONS``
#: heading it is shown under, and holding its own heading and builder.
RUN_SECTIONS = {
    INTENSITIES_HEADING: (
        f"Near-term pipeline: {figures.PIPELINE_YEAR} capacity by carrier",
        _figure_near_term_pipeline,
    ),
    "Cost surface as heatmap": ("Increment surfaces", _figure_increment_surfaces),
    "Implied carbon price of each cap": ("Duals", _figure_duals),
    "Cost decomposition, central trajectory": (
        "Technology cost inputs",
        _figure_input_costs,
    ),
    "Premiums paid above AEMO's limits and baseline build rates": (
        "Build cost curves (inputs)",
        _figure_build_cost_curves,
    ),
    INCREMENT_MIX_HEADING: (
        "REZ and corridor expansion against IASR and relaxed limits",
        _figure_transmission_limits,
    ),
    "Storage build": (ASSUMPTIONS_HEADING, _html_assumptions),
}


def _provenance(layout: OutputLayout) -> str:
    """Name the run directory and the source commit recorded by the run's solves."""
    records = (
        json.loads(path.read_text(encoding="utf-8"))
        for path in layout.records.glob("*.json")
    )
    commits = sorted({record.get("source_git_commit") for record in records} - {None})
    return (
        f"<h1>Campaign dashboard: {layout.root.name}</h1>"
        f"<p>Run directory: {layout.root}<br>Source commit: {', '.join(commits) or 'not recorded'}</p>"
    )


def main(run: Path, show: bool = False) -> Path:
    """Write ``<run>/dashboard.html`` from the run's exports.

    :param run: A stamped run directory holding an ``exports/`` sub-directory.
    :param show: Open the finished page in the default browser.
    :return: The path written.
    """
    layout = OutputLayout(run)
    frame = tidy_frame(layout.exports)
    sections = [_provenance(layout), f"<script>{get_plotlyjs()}</script>"]
    for heading, body in _drawn_sections(frame, layout):
        if body is None:
            continue
        sections.append(f"<h2>{heading}</h2>")
        sections.append(_section_box(body))
        sections.append(DIVIDER)
    sections.append(PAGE_SCRIPT)
    page = layout.root / "dashboard.html"
    page.write_text("\n".join(sections), encoding="utf-8")
    if show:
        webbrowser.open(page.as_uri())
    return page
