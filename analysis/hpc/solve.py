"""Solve one chain: a sequence of single-period ISPyPSA capacity-expansion solves.

Each milestone year is solved on its own, in order. With ``--recursive-dynamic`` the
new-build tranche of a solve is extracted afterwards and injected into every later
solve, so the chain accumulates vintages and retirement follows from PyPSA's
active-assets check (``build_year + lifetime > period``). With ``--reducible-existing``
the existing fleet becomes a downward-only capacity decision each period, and the
retained level carries forward as a monotone non-increasing floor.

Per-period settings that vary along a chain are given as ``YEAR:VALUE`` schedules, one
entry per period::

    --co2-cap-t-schedule 2030:19984000 2040:2672000
    --parsed-traces-directory-schedule 2030:/traces/central_2030 2040:/traces/central_2040

Input stores (workbook, parsed workbook cache, traces) come from ``IO_DIR`` through
:class:`analysis.env.Env`. Every product of the chain -- generated configs, solver logs,
JSON records and solved networks -- is written under the stamped run directory given as
``--output-root``, laid out by :class:`analysis.env.OutputLayout`.

Usage::

    msm solve --run-id ext_central_c0 --output-root "$RUN_DIR" \\
        --periods 2030 2040 2050 2060 --recursive-dynamic --reducible-existing
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Annotated, TypeVar

import pandas as pd
import psutil
from cyclopts import Parameter

from analysis.env import MODEL_DATA, REPO_ROOT, Env, OutputLayout
from analysis.model import ARCHETYPE

T = TypeVar("T")

# List flags consume every following token, so ``--periods 2030 2040`` is one flag with
# two values rather than a value and a stray argument.
Years = Annotated[list[int], Parameter(consume_multiple=True)]
OptionalYears = Annotated[list[int] | None, Parameter(consume_multiple=True)]
OptionalSchedule = Annotated[list[str] | None, Parameter(consume_multiple=True)]


def _parse_year_schedule(tokens: list[str], cast: Callable[[str], T]) -> dict[int, T]:
    """Parse ``YEAR:VALUE`` tokens into a per-year mapping.

    ``["2030:1.5", "2040:2"]`` with ``cast=float`` gives ``{2030: 1.5, 2040: 2.0}``.
    Each year may appear once; a malformed token raises ``ValueError``.
    """
    schedule: dict[int, T] = {}
    for token in tokens:
        year_text, sep, value_text = token.partition(":")
        if not sep or not year_text.isdigit():
            raise ValueError(f"Schedule entry must look like YEAR:VALUE, got {token!r}")
        year = int(year_text)
        if year in schedule:
            raise ValueError(f"Year {year} appears twice in schedule {tokens}")
        schedule[year] = cast(value_text)
    return schedule


def _require_schedule_covers_periods(
    schedule: dict[int, T], periods: list[int], flag: str
) -> None:
    """Raise early if a schedule leaves any period of the chain unspecified."""
    missing = sorted(set(periods) - set(schedule))
    if missing:
        raise ValueError(f"{flag} has no entry for periods {missing}")


def _schedule(
    tokens: list[str] | None,
    cast: Callable[[str], T],
    periods: list[int],
    flag: str,
) -> dict[int, T]:
    """Parse a ``YEAR:VALUE`` schedule flag and require an entry for every period."""
    if not tokens:
        return {}
    schedule = _parse_year_schedule(tokens, cast)
    _require_schedule_covers_periods(schedule, periods, flag)
    return schedule


def _curve_or_none(curve_csv: str) -> str | None:
    """Map the ``"none"`` sentinel to ``None``, opting out of a supply curve."""
    return None if curve_csv.lower() == "none" else curve_csv


def _hold_curve_to_years(curve: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Append the last published year's rows relabelled to each missing later year.

    Years already inside the published span are left untouched, so the held copy is
    identical to the source wherever the source has data.
    """
    last_year = int(curve["financial_year"].max())
    held_rows = [
        curve[curve["financial_year"] == last_year].assign(financial_year=year)
        for year in sorted(year for year in years if year > last_year)
    ]
    return pd.concat([curve, *held_rows], ignore_index=True)


def _held_curve_csv(
    curve_csv: str | None, periods: list[int], configs_dir: Path
) -> str | None:
    """Extend a supply curve CSV to cover every period, holding its last published year.

    Returns the original path when the curve already spans the periods, otherwise the
    path of a held copy written beside the generated configs.
    """
    if curve_csv is None:
        return None
    curve = pd.read_csv(curve_csv)
    last_year = int(curve["financial_year"].max())
    beyond = sorted(year for year in periods if year > last_year)
    if not beyond:
        return curve_csv
    logging.warning(
        f"Supply curve {Path(curve_csv).name} held at FY{last_year} for investment "
        f"periods beyond the published data: {beyond}"
    )
    held_path = configs_dir / f"{Path(curve_csv).stem}_held.csv"
    held_path.parent.mkdir(parents=True, exist_ok=True)
    _hold_curve_to_years(curve, periods).to_csv(
        held_path, index=False, lineterminator="\n"
    )
    return str(held_path)


def _chain_state_dir(
    layout: OutputLayout, run_id: str, name: str, resume: bool
) -> Path:
    """Create a per-chain state directory, wiping stale state unless resuming.

    A fresh chain starts clean so a rerun never inherits carried tranches or retained
    levels from a different configuration; ``--resume`` keeps them so a requeued job
    continues where it stopped.
    """
    path = layout.chain_dir(run_id) / name
    if path.exists() and not resume:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_period_config(
    run_id: str,
    year: int,
    layout: OutputLayout,
    workbook: Path,
    workbook_cache: Path,
    parsed_traces_directory: str,
    regions: list[str] | None,
    rep_weeks: list[int] | None,
    named_weeks: bool,
    carbon_price: float,
    tns_price: float,
    gas_supply_curve_csv: str | None,
    gas_unblended: bool,
    biomass_supply_curve_csv: str | None,
    ccs_sink_tranches_csv: str | None,
    ccs_transport_csv: str | None,
) -> Path:
    """Synthesise a single-period ISPyPSA config for this milestone year.

    :param run_id: Sub-run id that already carries the year suffix; the year is never
        appended again, because the doubled suffix pushed generated timeseries paths
        past Windows' 260-character path limit.
    :param layout: Run products layout; the config lands in its ``configs`` directory.
    :param workbook: IASR workbook to template from.
    :param workbook_cache: Parsed workbook tables matching that workbook.
    :param parsed_traces_directory: Trace store base directory for this period.
    :param regions: NEM regions to filter to, or ``None`` for the full NEM.
    :param rep_weeks: Numbered representative weeks, or ``None`` for the default single
        spring-shoulder week.
    :param named_weeks: Whether to add the two named stress weeks to the sample.
    :return: Path of the written config.
    """
    cfg_path = layout.config(run_id)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    filter_line = f"filter_by_nem_regions: {regions}\n" if regions else "# Full NEM\n"
    cfg_text = f"""# Auto-generated single-period config for {run_id} year {year}
paths:
  run_directory: "{layout.runs.as_posix()}"
  ispypsa_run_name: {run_id}
  parsed_traces_directory: "{Path(parsed_traces_directory).as_posix()}"
  workbook_path: "{workbook.as_posix()}"
  parsed_workbook_cache: "{workbook_cache.as_posix()}"
trace_data:
  dataset_type: example
  dataset_year: 2026
iasr_workbook_version: "7.8"
scenario: Step Change
wacc: 0.07
discount_rate: 0.05
unserved_energy:
  cost: 10000.0
  max_per_node: 100000.0
{filter_line}network:
  transmission_expansion: True
  rez_transmission_expansion: True
  annuitisation_lifetime: 30
  nodes:
    regional_granularity: sub_regions
    rezs: discrete_nodes
  rez_to_sub_region_transmission_default_limit: 1e5
temporal:
  year_type: fy
  range:
    start_year: {year}
    end_year: {year}
  capacity_expansion:
    resolution_min: 30
    reference_year_cycle: [2018]
    investment_periods: [{year}]
    aggregation:
      representative_weeks: {rep_weeks if rep_weeks is not None else [42]}
      named_representative_weeks: {"[residual-peak-demand, peak-demand]" if named_weeks else "~"}
  operational:
    resolution_min: 30
    reference_year_cycle: [2018]
    horizon: 336
    overlap: 48
    aggregation:
      representative_weeks: ~
      named_representative_weeks: [residual-peak-demand]
solver: highs
create_plots: False
carbon_pricing:
  carbon_price: {carbon_price}
  tns_price: {tns_price}
"""
    if gas_unblended:
        cfg_text += "fuel_pricing:\n  blend_biomethane_into_gas: false\n"
    if gas_supply_curve_csv is not None:
        cfg_text += (
            f"gas_supply_curve:\n"
            f'  curve_csv: "{Path(gas_supply_curve_csv).as_posix()}"\n'
        )
    if biomass_supply_curve_csv is not None:
        cfg_text += (
            f"biomass_supply_curve:\n"
            f'  curve_csv: "{Path(biomass_supply_curve_csv).as_posix()}"\n'
        )
    if ccs_sink_tranches_csv is not None:
        cfg_text += (
            f"ccs_supply_curve:\n"
            f'  sink_tranches_csv: "{Path(ccs_sink_tranches_csv).as_posix()}"\n'
            f'  transport_csv: "{Path(ccs_transport_csv).as_posix()}"\n'
        )
    cfg_path.write_text(cfg_text)
    return cfg_path


def _runner_flags(**flags: object) -> list[str]:
    """Render optional runner flags: ``None`` and ``False`` drop out, ``True`` is a switch.

    ``_runner_flags(use_pdlp=True, highs_threads=64, co2_cap_t=None)`` gives
    ``["--use-pdlp", "--highs-threads", "64"]``.
    """
    tokens: list[str] = []
    for name, value in flags.items():
        if value is None or value is False:
            continue
        tokens.append("--" + name.replace("_", "-"))
        if value is not True:
            tokens.append(str(value))
    return tokens


def _process_tree_rss(process: psutil.Process) -> int:
    """Resident memory of the runner plus every process it spawned, in bytes."""
    rss = process.memory_info().rss
    for child in process.children(recursive=True):
        rss += child.memory_info().rss
    return rss


def _kill_process_tree(process: psutil.Process) -> None:
    """Kill the runner and its children, ignoring any that have already exited."""
    for child in process.children(recursive=True):
        with suppress(psutil.Error, OSError):
            child.kill()
    process.kill()


def _run_one_period(
    cfg: Path,
    run_id: str,
    budget_min: float,
    layout: OutputLayout,
    runner_flags: list[str],
) -> dict:
    """Run a single period through the instrumented runner and return its record.

    Stale log and record files are removed first, so a record on disk afterwards
    always belongs to this attempt. A solve that outlives ``budget_min`` is killed and
    reported as ``timed_out``.
    """
    log_path = layout.log(run_id)
    record_path = layout.record(run_id)
    record_path.unlink(missing_ok=True)
    log_path.unlink(missing_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        "-u",
        "-m",
        "analysis.hpc.instrumented_runner",
        "--config",
        str(cfg),
        "--run-id",
        run_id,
        "--output-root",
        layout.root.as_posix(),
        *runner_flags,
    ]
    started = time.time()
    peak_rss = 0
    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        psproc = psutil.Process(proc.pid)
        while proc.poll() is None:
            with suppress(psutil.Error, OSError):
                peak_rss = max(peak_rss, _process_tree_rss(psproc))
            if time.time() - started > budget_min * 60:
                _kill_process_tree(psproc)
                proc.wait(timeout=30)
                return {
                    "status": "timed_out",
                    "wall_clock_s": time.time() - started,
                    "peak_rss_gib": peak_rss / (1024**3),
                }
            time.sleep(5)

    if record_path.exists():
        record = json.loads(record_path.read_text())
        record["peak_rss_gib"] = peak_rss / (1024**3)
        return record
    return {
        "status": "failed",
        "wall_clock_s": time.time() - started,
        "peak_rss_gib": peak_rss / (1024**3),
    }


def _completed_record(layout: OutputLayout, run_id: str, archetype: str) -> dict | None:
    """The saved record for a period that already solved, or None if it must be run.

    Used by ``--resume`` so a requeued chain skips periods whose record reports
    ``completed`` and whose solved network is on disk.
    """
    record_path = layout.record(run_id)
    if not record_path.exists() or not layout.network(run_id, archetype).exists():
        return None
    record = json.loads(record_path.read_text())
    return record if record.get("status") == "completed" else None


def _save_new_built_tranche(
    layout: OutputLayout, run_id: str, year: int, tranches_dir: Path
) -> dict:
    """Extract this period's new-build tranche and save it for later periods.

    A failure here must stop the chain rather than be recorded: the next period would
    otherwise carry no floor and solve as a greenfield year, so the exception is left
    to propagate. Imported inside the function so the CLI does not pay for pypsa.
    """
    from analysis.model.recursive_dynamic import (
        extract_new_built_tranche,
        save_tranche,
    )

    tranche = extract_new_built_tranche(layout.network(run_id, ARCHETYPE), year)
    save_tranche(tranche, tranches_dir, year)
    return {
        "generators_rows": int(len(tranche["generators"])),
        "batteries_rows": int(len(tranche["batteries"])),
        "generator_mw": float(tranche["generators"]["p_nom"].sum()),
        "battery_mw": float(tranche["batteries"]["p_nom"].sum()),
    }


def _save_retention_floor(
    layout: OutputLayout, run_id: str, year: int, retention_dir: Path
) -> dict:
    """Record the retained existing capacity as the next period's monotone floor.

    As with the tranche, a failure propagates: losing the floor would let a retired
    unit come back in the next period.
    """
    from analysis.model.retirement import (
        extract_retained_existing,
        save_retention_floor,
    )

    floor = extract_retained_existing(layout.run_dir(run_id, ARCHETYPE), year)
    save_retention_floor(floor, retention_dir, year)
    return {
        "existing_units": int(len(floor)),
        "retained_mw": float(sum(floor.values())),
    }


def main(
    *,
    run_id: str,
    output_root: Path,
    periods: Years,
    recursive_dynamic: bool = False,
    reducible_existing: bool = False,
    existing_fom_keeping: bool = False,
    parsed_traces_directory_schedule: OptionalSchedule = None,
    rep_weeks: OptionalYears = None,
    named_weeks: bool = True,
    carbon_price: float = 0.0,
    co2_cap_t_schedule: OptionalSchedule = None,
    tns_price: float = 0.0,
    gas_unblended: bool = False,
    gas_supply_curve: str = str(
        MODEL_DATA / "gas_supply_curve_central_held_to_2060.csv"
    ),
    biomass_supply_curve: str = str(
        MODEL_DATA / "biomass_supply_curve_central_held_to_2060.csv"
    ),
    ccs_supply_curve: str = str(MODEL_DATA / "ccs_sink_tranches_conservative.csv"),
    ccs_transport_adders: str = str(MODEL_DATA / "ccs_transport_adders.csv"),
    region_filter: Annotated[str | None, Parameter(name="--filter")] = None,
    use_gurobi: bool = False,
    gurobi_method: int | None = None,
    gurobi_bar_conv_tol: float | None = None,
    gurobi_threads: int | None = None,
    use_pdlp: bool = False,
    pdlp_tolerance: float | None = None,
    highs_threads: int | None = None,
    budget_min: float = 720,
    resume: bool = False,
) -> None:
    """Solve one chain of single-period ISPyPSA runs, one per milestone year.

    :param run_id: Chain id; each period's sub-run is ``<run_id>_<year>``.
    :param output_root: Stamped run directory every product is written under.
    :param periods: Milestone years to solve, in order.
    :param recursive_dynamic: Carry each period's new build forward into later periods.
    :param reducible_existing: Let the existing fleet retire economically, with the
        retained level carried forward as a monotone non-increasing floor.
    :param existing_fom_keeping: Charge each existing unit its own fixed operating and
        maintenance cost for being kept, instead of keeping it for free.
    :param parsed_traces_directory_schedule: ``YEAR:DIR`` trace store per period, one
        entry per period; defaults to the single trace store under ``IO_DIR``.
    :param rep_weeks: Numbered representative weeks sampled in each solve.
    :param named_weeks: Add the two named stress weeks to the sample; pass
        ``--no-named-weeks`` for an evenly sampled design, because the numbered and
        named sets are unioned and the stress weeks would otherwise be overweighted.
    :param carbon_price: AUD/tCO2e adder on residual emissions in every period.
    :param co2_cap_t_schedule: ``YEAR:TONNES`` absolute annual CO2e cap per period, one
        entry per period; the cap's dual is recorded.
    :param tns_price: AUD/tCO2 transport and storage cost on tonnes captured by CCS.
    :param gas_unblended: Price gas from the IASR gas table alone, leaving out AEMO's
        mandated biomethane blend.
    :param gas_supply_curve: Gas supply curve CSV (tranche, financial_year, cap_pj,
        adder_$/gj) pricing gas above each tranche boundary; ``none`` for unlimited gas
        at IASR prices.
    :param biomass_supply_curve: Biomass feedstock supply curve CSV in the same shape;
        ``none`` for flat re-priced feedstock with unlimited volume.
    :param ccs_supply_curve: CO2 sink injectivity tranche CSV (sink, financial_year,
        cap_kt, storage_$/t) capping and pricing annual injection per sink; ``none`` for
        free unlimited disposal, which is AEMO's own ISP treatment.
    :param ccs_transport_adders: CO2 transport adder CSV (isp_sub_region_id, sink,
        distance_km, transport_$/t) pricing each sub-region's pipeline to its sink.
    :param region_filter: Single NEM region to solve, e.g. ``NSW``; omit for the full NEM.
    :param use_gurobi: Solve with Gurobi instead of HiGHS.
    :param gurobi_method: Gurobi ``Method`` (2 is barrier).
    :param gurobi_bar_conv_tol: Gurobi ``BarConvTol``; pin it, because Gurobi's own
        default is tighter than intended here and materially slower.
    :param gurobi_threads: Gurobi ``Threads``; pin to the job's core allocation.
    :param use_pdlp: Solve with HiGHS PDLP instead of the default simplex.
    :param pdlp_tolerance: PDLP optimality plus primal and dual feasibility tolerances.
    :param highs_threads: HiGHS ``threads``; pin to the job's core allocation.
    :param budget_min: Per-period wall-clock budget in minutes; a longer solve is killed.
    :param resume: Keep carried state and skip periods that already solved, so a
        requeued job continues from the first unsolved period.
    """
    env = Env.from_env()
    layout = OutputLayout(output_root)
    cap_schedule = _schedule(co2_cap_t_schedule, float, periods, "--co2-cap-t-schedule")
    traces_schedule = _schedule(
        parsed_traces_directory_schedule,
        str,
        periods,
        "--parsed-traces-directory-schedule",
    )
    gas_curve = _held_curve_csv(
        _curve_or_none(gas_supply_curve), periods, layout.configs
    )
    biomass_curve = _held_curve_csv(
        _curve_or_none(biomass_supply_curve), periods, layout.configs
    )
    ccs_curve = _curve_or_none(ccs_supply_curve)
    regions = [region_filter] if region_filter else None
    tranches_dir = (
        _chain_state_dir(layout, run_id, "tranches", resume)
        if recursive_dynamic
        else None
    )
    retention_dir = (
        _chain_state_dir(layout, run_id, "retention", resume)
        if reducible_existing
        else None
    )
    chain_flags = _runner_flags(
        highs_threads=highs_threads,
        use_pdlp=use_pdlp,
        pdlp_tolerance=pdlp_tolerance,
        use_gurobi=use_gurobi,
        gurobi_method=gurobi_method,
        gurobi_bar_conv_tol=gurobi_bar_conv_tol,
        gurobi_threads=gurobi_threads,
        carried_tranches_dir=tranches_dir,
        reducible_existing=reducible_existing,
        existing_fom_keeping=existing_fom_keeping,
        retention_floor_dir=retention_dir,
    )

    layout.records.mkdir(parents=True, exist_ok=True)
    chain_record = {
        "run_id": run_id,
        "kind": "recursive_dynamic_chain",
        "archetype": ARCHETYPE,
        "regions_filter": regions,
        "periods": periods,
        "recursive_dynamic": recursive_dynamic,
        "tranches_dir": str(tranches_dir) if tranches_dir else None,
        "output_root": str(layout.root),
        "carbon_price": carbon_price,
        "co2_cap_t_schedule": cap_schedule or None,
        "parsed_traces_directory_schedule": traces_schedule or None,
        "tns_price": tns_price,
        "gas_supply_curve": gas_curve,
        "gas_unblended": gas_unblended,
        "biomass_supply_curve": biomass_curve,
        "ccs_supply_curve": ccs_curve,
        "started_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "per_period": {},
        "cumulative_wall_clock_s": 0.0,
        "peak_rss_gib_observed": 0.0,
    }

    chain_started = time.time()
    for year in periods:
        sub_run_id = f"{run_id}_{year}"
        print(f"\n=== Period {year} ({sub_run_id}) ===")
        cfg = _write_period_config(
            sub_run_id,
            year,
            layout,
            workbook=env.iasr_workbook,
            workbook_cache=env.workbook_cache,
            # ISPyPSA appends isp_<dataset_year> to this path, so the shared store's
            # parent is what a config takes.
            parsed_traces_directory=traces_schedule.get(year, str(env.traces.parent)),
            regions=regions,
            rep_weeks=rep_weeks,
            named_weeks=named_weeks,
            carbon_price=carbon_price,
            tns_price=tns_price,
            gas_supply_curve_csv=gas_curve,
            gas_unblended=gas_unblended,
            biomass_supply_curve_csv=biomass_curve,
            ccs_sink_tranches_csv=ccs_curve,
            ccs_transport_csv=ccs_transport_adders,
        )
        period_started = time.time()
        already_solved = (
            _completed_record(layout, sub_run_id, ARCHETYPE) if resume else None
        )
        if already_solved is not None:
            print(f"  Period {year} already completed; skipping solve (--resume)")
        record = already_solved or _run_one_period(
            cfg,
            sub_run_id,
            budget_min,
            layout,
            [
                *chain_flags,
                *_runner_flags(current_year=year, co2_cap_t=cap_schedule.get(year)),
            ],
        )
        record["per_period_wall_s"] = time.time() - period_started
        record["per_period_peak_gib"] = record.get("peak_rss_gib", 0)
        if record.get("status") == "completed" and tranches_dir is not None:
            record["tranche_extracted"] = _save_new_built_tranche(
                layout, sub_run_id, year, tranches_dir
            )
        if record.get("status") == "completed" and retention_dir is not None:
            record["retention_floor"] = _save_retention_floor(
                layout, sub_run_id, year, retention_dir
            )
        chain_record["per_period"][year] = record
        chain_record["cumulative_wall_clock_s"] = time.time() - chain_started
        chain_record["peak_rss_gib_observed"] = max(
            chain_record["peak_rss_gib_observed"], record.get("peak_rss_gib", 0)
        )
        # Saved after every period so a job that dies mid-chain still leaves a record.
        layout.record(run_id).write_text(
            json.dumps(chain_record, indent=2, default=str)
        )
        if record.get("status") != "completed":
            print(f"  Period {year} status: {record.get('status')}; aborting chain")
            break

    chain_record["ended_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    chain_record["cumulative_wall_clock_s"] = time.time() - chain_started
    layout.record(run_id).write_text(json.dumps(chain_record, indent=2, default=str))
    print(
        f"\n=== Done. Cumulative wall: "
        f"{chain_record['cumulative_wall_clock_s']:.0f}s ==="
    )
