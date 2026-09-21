"""Assemble the extension campaign's deliverables from the solved chains.

Same six tables as the demand x carbon sweep, over the campaign's grid of five demand
trajectories by ten pressure settings, at the milestones 2030/2040/2050/2060:

  results.csv          generation mix (TWh and shares, storage discharge included as
                       its own carriers), capacity builds (1 MW reporting floor), total
                       and average system cost, absolute emissions and intensity,
                       renewable fraction, load shedding
  storage.csv          storage build by duration class
  marginals.csv        finite-difference marginal cost and marginal emissions
                       intensity of demand between adjacent trajectories, plus the
                       thermal/renewable split of the marginal generation
  manifest.csv         run id, pressure setting, cap tonnage and shadow price, solver
                       settings, termination status, residuals, wall time, paths
  acceptance_*.csv     the campaign's acceptance tests, per cell-period and per grid

A seventh table, input_costs.csv, reports the cost inputs the solves were templated from rather
than anything they produced: new-entrant build cost per technology, fuel price per fuel, and the
supply-curve tranche adders, each against the financial year it applies to.

Two rules the sweep did not need.

  Load shedding. Deep caps can leave demand unserved at the A$10,000/MWh emergency
  price. A cell shedding more than `BOUNDARY_USE_PCT` of its demand is a BOUNDARY: it
  marks where the pressure setting stops being feasible on this fleet, so it is
  reported but never treated as a menu member, and it is dropped before the marginals
  are differenced. The unserved-energy generators carry no capital cost and are
  excluded from dispatch, marginal cost and capex everywhere in the post-processor, so
  the A$10,000/MWh penalty never enters a cost column.

  Implied carbon price. A cap chain prices carbon at zero and exerts its pressure
  through the constraint, so its price signal is the cap's shadow price, read from the
  solve's constraint_duals.json and negated. A price chain's implied price is the
  price it was run at.

Cost basis is the sweep's: per-MWh costs come from analysis/sharp/frontier_points.py,
whose `cost_per_mwh_excl_fuel_carbon` is the full-fleet intensity, and total system
cost is rebuilt component-by-component as (excl_fuel_carbon + fuel + carbon) x
delivered MWh so no term is plugged.

The extract stage is one chain per process so the 41 chains can run concurrently; the
assemble stage reads the per-chain CSVs back and needs no networks.

Usage:
    uv run msm extract --run <run dir> --only ext_low_c0 --stage extract
    uv run msm extract --run <run dir> --stage assemble
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Literal

import pandas as pd
import pypsa
import yaml

from analysis.env import MODEL_DATA, Env, OutputLayout
from analysis.hpc.campaign_grid import (
    CAP_KIND,
    Pressure,
    Trajectory,
    order_pressures,
    parse_pressure,
    split_chain_id,
    trajectories_from_plan,
)
from analysis.hpc.launch import submit
from analysis.sharp.frontier_points import extract_chain

REPORTING_FLOOR_MW = 1.0
RENEWABLE_CARRIERS = {"Wind", "Solar", "Water", "Biomass"}
THERMAL_CARRIERS = {"Gas", "Black Coal", "Brown Coal", "Liquid Fuel"}
# Flat transport-and-storage adder on captured CO2, common to every chain.
TNS_PRICE_AUD_PER_TCO2 = 89.93
# Above this share of demand left unserved, a cell is a boundary rather than a menu
# member. A tenth of a percent is far above the rounding noise of a converged solve
# and far below any shedding that would change the reported mix.
BOUNDARY_USE_PCT = 0.1
# Shed energy is not a generation technology; leaving it in the mix would show up as a
# carrier share and contaminate the renewable fraction of every deep-cap cell.
EXCLUDED_MIX_CARRIERS = frozenset({"Unserved Energy"})
# Carriers that burn a priced fuel, used to detect a milestone the IASR price tables do
# not reach.
FUEL_BURNING_CARRIERS = ["Gas", "Black Coal", "Brown Coal", "Liquid Fuel", "Biomass"]
# Below this share of generation, a zero fuel cost is the honest answer rather than a
# missing price.
FUEL_BURNING_FLOOR_PCT = 0.5
# Pumped hydro units carry the carrier "Water", the same carrier the conventional hydro
# generators carry, so the storage half of the mix is renamed to keep the two apart.
STORAGE_MIX_LABELS = {"Water": "Pumped hydro"}


# --------------------------------------------------------------- per-chain networks


def _network(cell: str, year: int, layout: OutputLayout) -> pypsa.Network:
    """Solved network for one cell-year, named the way `msm solve` names it."""
    return pypsa.Network(layout.network(f"{cell}_{year}"))


def _annual_mwh(network: pypsa.Network) -> pd.Series:
    """Annual dispatch per generator, snapshot weightings applied."""
    return network.generators_t.p.mul(
        network.snapshot_weightings["generators"], axis=0
    ).sum()


def _storage_discharge_twh(network: pypsa.Network) -> pd.Series:
    """Annual storage discharge per carrier, charging dropped, snapshot weightings applied."""
    discharge = (
        network.storage_units_t.p.clip(lower=0)
        .mul(network.snapshot_weightings["generators"], axis=0)
        .sum()
    )
    carriers = network.storage_units.carrier.replace(STORAGE_MIX_LABELS)
    return discharge.groupby(carriers).sum() / 1e6


def _mix_row(
    cell: str,
    year: int,
    layout: OutputLayout,
    excluded_carriers: frozenset[str] = frozenset(),
) -> dict:
    """Generation mix and built capacity for one cell-year.

    `excluded_carriers` drops carriers from the mix and capacity columns before the
    shares are taken. A run that sheds load needs "Unserved Energy" excluded, or the
    shed energy lands in the mix as if it were a generation technology; `use_mwh` is
    still reported from that carrier regardless.

    Storage discharge is reported per storage carrier against the same generator-output
    denominator, so a storage share reads as the share of generation storage re-delivers
    and every generator share means what it did without them.
    """
    network = _network(cell, year, layout)
    energy = _annual_mwh(network)
    carriers = network.generators.carrier
    kept = ~carriers.isin(excluded_carriers)
    by_carrier = energy[kept].groupby(carriers[kept]).sum() / 1e6
    total = by_carrier.sum()
    row = {"cell": cell, "year": year, "total_twh": total}
    for carrier, twh in by_carrier.items():
        if not carrier:
            continue
        row[f"twh_{carrier}"] = twh
        row[f"share_{carrier}"] = twh / total * 100 if total else 0.0
    for carrier, twh in _storage_discharge_twh(network).items():
        row[f"twh_{carrier}"] = twh
        row[f"share_{carrier}"] = twh / total * 100 if total else 0.0
    renewable = sum(by_carrier.get(c, 0.0) for c in RENEWABLE_CARRIERS)
    row["renewable_fraction_pct"] = renewable / total * 100 if total else 0.0
    row["use_mwh"] = float(energy[carriers == "Unserved Energy"].sum())

    generators = network.generators[kept]
    built = generators[generators.p_nom_opt > REPORTING_FLOOR_MW]
    for carrier, gw in (built.groupby("carrier")["p_nom_opt"].sum() / 1e3).items():
        if carrier:
            row[f"gw_{carrier}"] = gw
    return row


def _duration_class(hours: float) -> str:
    """Bin a storage duration. ECAA units carry derived, non-round durations (1.06 h,
    1.89 h, ...), so raw max_hours grouping yields dozens of near-duplicate rows."""
    if hours < 2:
        return "1_under_2h"
    if hours < 4:
        return "2_2to4h"
    if hours < 8:
        return "3_4to8h"
    if hours <= 8:
        return "4_8h"
    if hours <= 24:
        return "5_over8to24h"
    return "6_over24h"


def _storage_rows(cell: str, year: int, layout: OutputLayout) -> list[dict]:
    """Storage build by duration class for one cell-year."""
    network = _network(cell, year, layout)
    units = network.storage_units
    built = units[units.p_nom_opt > REPORTING_FLOOR_MW].copy()
    built["duration_class"] = built["max_hours"].map(_duration_class)
    grouped = built.groupby(["carrier", "duration_class"]).apply(
        lambda g: pd.Series(
            {
                "power_gw": g["p_nom_opt"].sum() / 1e3,
                "energy_gwh": (g["p_nom_opt"] * g["max_hours"]).sum() / 1e3,
                "units": len(g),
            }
        ),
        include_groups=False,
    )
    return [
        {
            "cell": cell,
            "year": year,
            "carrier": carrier,
            "duration_class": duration_class,
            **row,
        }
        for (carrier, duration_class), row in grouped.iterrows()
    ]


def _marginals(
    results: pd.DataFrame,
    level_order: list[str],
    periods: list[int],
    series_column: str,
    level_column: str,
) -> pd.DataFrame:
    """Finite differences between adjacent demand levels within each series value.

    A series value is whatever holds constant across the difference -- the pressure
    setting for the extension campaign -- and is carried through to the output under
    `series_column`. Levels absent from `results` are skipped rather than bridged, so
    dropping a cell drops its two arcs instead of silently widening a neighbouring one.

    Both cells' totals are carried alongside the difference, so every marginal is
    auditable against its two endpoints rather than presented as a bare number.
    """
    rows = []
    for series_value in sorted(results[series_column].unique()):
        for year in periods:
            for low, high in zip(level_order, level_order[1:]):
                pair = results[
                    (results[series_column] == series_value) & (results.year == year)
                ].set_index(level_column)
                if low not in pair.index or high not in pair.index:
                    continue
                a, b = pair.loc[low], pair.loc[high]
                d_mwh = (b["delivered_twh"] - a["delivered_twh"]) * 1e6
                if d_mwh == 0:
                    continue
                d_cost = b["total_cost_aud_per_yr"] - a["total_cost_aud_per_yr"]
                d_co2e = (b["co2e_total_kt_per_yr"] - a["co2e_total_kt_per_yr"]) * 1e3
                thermal = sum(
                    b.get(f"twh_{c}", 0.0) - a.get(f"twh_{c}", 0.0)
                    for c in THERMAL_CARRIERS
                )
                renewable = sum(
                    b.get(f"twh_{c}", 0.0) - a.get(f"twh_{c}", 0.0)
                    for c in RENEWABLE_CARRIERS
                )
                rows.append(
                    {
                        series_column: series_value,
                        "year": year,
                        "from_level": low,
                        "to_level": high,
                        "from_delivered_twh": a["delivered_twh"],
                        "to_delivered_twh": b["delivered_twh"],
                        "delta_delivered_twh": d_mwh / 1e6,
                        "from_total_cost_aud_per_yr": a["total_cost_aud_per_yr"],
                        "to_total_cost_aud_per_yr": b["total_cost_aud_per_yr"],
                        "marginal_cost_aud_per_mwh": d_cost / d_mwh,
                        "from_co2e_kt_per_yr": a["co2e_total_kt_per_yr"],
                        "to_co2e_kt_per_yr": b["co2e_total_kt_per_yr"],
                        "marginal_co2e_t_per_mwh": d_co2e / d_mwh,
                        "marginal_thermal_twh": thermal,
                        "marginal_renewable_twh": renewable,
                        # Per marginal MWh *delivered*. These two sum above 100 %
                        # because marginal generation exceeds marginal demand: storage
                        # round-trip and network losses have to be generated too.
                        "marginal_thermal_per_delivered_pct": thermal
                        / (d_mwh / 1e6)
                        * 100,
                        "marginal_renewable_per_delivered_pct": renewable
                        / (d_mwh / 1e6)
                        * 100,
                        # Per marginal MWh *generated*, so the pair sums to 100 %. This is
                        # the technology identity of the marginal MWh.
                        "marginal_thermal_pct_of_generation": thermal
                        / (thermal + renewable)
                        * 100,
                        "marginal_renewable_pct_of_generation": renewable
                        / (thermal + renewable)
                        * 100,
                    }
                )
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ chain products


def _solved_years(layout: OutputLayout, run_id: str, years: list[int]) -> list[int]:
    """Milestones of one chain that have both a solver record and a solved network.

    A campaign chain still in flight has its later milestones missing; those years are
    dropped rather than failing the extraction, so the deliverables can be built while
    the last chains finish.
    """
    return [
        year
        for year in years
        if layout.record(f"{run_id}_{year}").exists()
        and layout.network(f"{run_id}_{year}").exists()
    ]


def _frontier_frame(
    run_id: str,
    pressure: Pressure,
    trajectory: str,
    years: list[int],
    layout: OutputLayout,
    workbook_cache: Path,
) -> pd.DataFrame:
    """Frontier coordinates for one chain, with the campaign's axis columns attached."""
    frame, _ = extract_chain(
        sweep_id=run_id,
        run_id=run_id,
        years=years,
        carbon_price=pressure.carbon_price,
        tns_price=TNS_PRICE_AUD_PER_TCO2,
        layout=layout,
        workbook_cache=workbook_cache,
    )
    frame.insert(0, "cell", run_id)
    frame["pressure"] = pressure.key
    frame["trajectory"] = trajectory
    # The extractor strips fuel and carbon from its primary column; both are costs the
    # system genuinely pays, so the reported average rebuilds them.
    frame["avg_cost_aud_per_mwh"] = (
        frame["cost_per_mwh_excl_fuel_carbon"]
        + frame["diagnostic_fuel_cost_per_mwh"]
        + frame["diagnostic_carbon_cost_per_mwh"]
    )
    frame["delivered_twh"] = frame["annual_generation_twh"]
    frame["total_cost_aud_per_yr"] = (
        frame["avg_cost_aud_per_mwh"] * frame["delivered_twh"] * 1e6
    )
    frame["co2e_total_kt_per_yr"] = (
        frame["co2e_total_t_per_mwh"] * frame["delivered_twh"] * 1e3
    )
    return frame


def _cap_shadow_price(layout: OutputLayout, run_id: str, year: int) -> float | None:
    """Implied carbon price of a cap, A$/t, from the solve's constraint duals.

    The dual of a tightening cap is negative, so the price the cap implies is its
    negation. A solve with no cap constraint writes no duals file.
    """
    duals_path = (
        layout.run_dir(f"{run_id}_{year}") / "outputs" / "constraint_duals.json"
    )
    if not duals_path.exists():
        return None
    return -json.loads(duals_path.read_text())["co2_cap_annual_t_dual"]


def _implied_carbon_price(
    layout: OutputLayout, run_id: str, year: int, pressure: Pressure
) -> float | None:
    """The price signal the cell actually faced: the cap's shadow price, or the price."""
    if pressure.kind == CAP_KIND:
        return _cap_shadow_price(layout, run_id, year)
    return pressure.value


def _manifest_row(
    run_id: str,
    pressure: Pressure,
    trajectory: Trajectory,
    year: int,
    layout: OutputLayout,
) -> dict:
    """Provenance and solver diagnostics for one solved milestone."""
    record = json.loads(layout.record(f"{run_id}_{year}").read_text())
    return {
        "cell": run_id,
        "run_id": f"{run_id}_{year}",
        "pressure": pressure.key,
        "trajectory": trajectory.key,
        "year": year,
        "source_twh": trajectory.source_twh.get(year),
        "carbon_price": pressure.carbon_price,
        "tns_price": TNS_PRICE_AUD_PER_TCO2,
        "co2_cap_annual_t": record.get("co2_cap_annual_t"),
        "annual_residual_co2e_t": record.get("annual_residual_co2e_t"),
        "implied_carbon_price_aud_per_t": _implied_carbon_price(
            layout, run_id, year, pressure
        ),
        "solver_options": json.dumps(record.get("solver_options")),
        "model_status": record.get("model_status"),
        # Gurobi barrier reports absolute primal/dual infeasibility and a
        # complementarity gap, not PDLP's relative metrics.
        "ipm_final_gap": record.get("ipm_final_gap"),
        "ipm_final_pinf": record.get("ipm_final_pinf"),
        "ipm_final_dinf": record.get("ipm_final_dinf"),
        "barrier_iterations": record.get("gurobi_barrier_iterations"),
        "objective_value": record.get("objective_value"),
        "lp_rows": record.get("lp_rows"),
        "solve_s": record.get("solve_s"),
        "wall_clock_s": record.get("wall_clock_s"),
        "peak_rss_gib": record.get("peak_rss_gib"),
        "network_path": str(layout.network(f"{run_id}_{year}")),
        "record_path": str(layout.record(f"{run_id}_{year}")),
    }


def extract_chain_products(
    run_id: str,
    trajectory: Trajectory,
    pressure: Pressure,
    years: list[int],
    layout: OutputLayout,
    workbook_cache: Path,
    per_chain_dir: Path,
) -> list[int]:
    """Write one chain's frontier, mix, storage and manifest CSVs.

    This is the parallel unit of the pipeline: it opens every network the chain needs
    and writes only small CSVs, so the assemble stage never touches a network.

    :return: The milestone years actually extracted.
    """
    solved = _solved_years(layout, run_id, years)
    if not solved:
        return []
    per_chain_dir.mkdir(parents=True, exist_ok=True)
    frontier = _frontier_frame(
        run_id, pressure, trajectory.key, solved, layout, workbook_cache
    )
    mix = pd.DataFrame(
        [_mix_row(run_id, year, layout, EXCLUDED_MIX_CARRIERS) for year in solved]
    )
    storage = pd.DataFrame(
        [row for year in solved for row in _storage_rows(run_id, year, layout)]
    )
    manifest = pd.DataFrame(
        [_manifest_row(run_id, pressure, trajectory, year, layout) for year in solved]
    )
    for name, frame in [
        ("frontier", frontier),
        ("mix", mix),
        ("storage", storage),
        ("manifest", manifest),
    ]:
        frame.to_csv(per_chain_dir / f"{name}_{run_id}.csv", index=False)
    return solved


# -------------------------------------------------------------------- cost inputs

#: Long-form columns of ``input_costs.csv``.
INPUT_COST_COLUMNS = ["category", "name", "year", "value", "unit", "source_table"]

#: Templated fuel-price tables, as the page names each fuel. Coal and gas are priced per generator,
#: so a table's mean across its generators is the fuel's price; the other four price one fuel each.
FUEL_PRICE_TABLES = {
    "coal_prices": "Coal",
    "gas_prices": "Gas",
    "biomass_prices": "Biomass",
    "liquid_fuel_prices": "Liquid Fuel",
    "hydrogen_prices": "Hydrogen",
    "biomethane_prices": "Biomethane",
}


def _melt_financial_years(
    table: pd.DataFrame, category: str, unit: str, source_table: str
) -> pd.DataFrame:
    """One templated cost table, indexed by name with a column per financial year, in long form.

    A templated year column is named ``2029_30_$/mw``, and ISPyPSA refers to a financial year by the
    calendar year it ends in, so that column is 2030.
    """
    years = {name: int(name[:4]) + 1 for name in table.columns if name[:4].isdigit()}
    long = table[list(years)].rename(columns=years).rename_axis("name")
    return (
        long.melt(ignore_index=False, var_name="year", value_name="value")
        .reset_index()
        .assign(category=category, unit=unit, source_table=source_table)
    )


def _templated_cost_rows(inputs: Path) -> pd.DataFrame:
    """New-entrant build cost and fuel price from one solve's templated ``ispypsa_inputs``."""
    builds = pd.read_csv(inputs / "new_entrant_build_costs.csv").set_index("technology")
    fuels = [
        _melt_financial_years(
            pd.read_csv(inputs / f"{stem}.csv")
            .mean(numeric_only=True)
            .to_frame(fuel)
            .T,
            "fuel_price",
            "A$/GJ",
            stem,
        )
        for stem, fuel in FUEL_PRICE_TABLES.items()
    ]
    build_cost = _melt_financial_years(
        builds, "build_cost", "A$/MW", "new_entrant_build_costs"
    )
    return pd.concat([build_cost, *fuels], ignore_index=True)


def _tranche_adder_rows(config: Path) -> pd.DataFrame:
    """Supply-curve tranche adders: what each tranche charges above the IASR fuel price, A$/GJ.

    A solve's config names its curves by absolute path on the host that solved it, so each curve is
    resolved by file name against the authored curves this package versions.
    """
    settings = yaml.safe_load(config.read_text(encoding="utf-8"))
    rows = []
    for fuel in ("gas", "biomass"):
        named = settings.get(f"{fuel}_supply_curve", {}).get("curve_csv")
        curve = pd.read_csv(MODEL_DATA / Path(named).name) if named else None
        if curve is not None:
            rows.append(
                curve.rename(
                    columns={"financial_year": "year", "adder_$/gj": "value"}
                ).assign(
                    category="fuel_adder",
                    name=f"{fuel} " + curve["tranche"],
                    unit="A$/GJ adder",
                    source_table=Path(named).name,
                )
            )
    if not rows:
        return pd.DataFrame(columns=INPUT_COST_COLUMNS)
    return pd.concat(rows, ignore_index=True)


def _write_input_costs(layout: OutputLayout, chain: str, years: list[int]) -> None:
    """Write the cost inputs one chain's solves were templated from, as ``input_costs.csv``.

    Every milestone of a chain is templated from the same IASR tables, so the first milestone whose
    templated inputs are still on disk carries the whole series. A campaign whose run directories
    live elsewhere, or have been cleared away, exports no cost inputs at all.
    """
    on_disk = [
        year
        for year in years
        if (layout.run_dir(f"{chain}_{year}") / "ispypsa_inputs").is_dir()
    ]
    if not on_disk:
        logging.info(
            f"No templated inputs under {layout.runs} for {chain}: no input_costs.csv"
        )
        return
    run_id = f"{chain}_{on_disk[0]}"
    rows = pd.concat(
        [
            _templated_cost_rows(layout.run_dir(run_id) / "ispypsa_inputs"),
            _tranche_adder_rows(layout.config(run_id)),
        ],
        ignore_index=True,
    )[INPUT_COST_COLUMNS]
    rows.to_csv(layout.exports / "input_costs.csv", index=False)
    print(f"  wrote input_costs.csv  ({len(rows)} rows, templated from {run_id})")


# ---------------------------------------------------------------------- assembly


def _read_per_chain(per_chain_dir: Path, name: str) -> pd.DataFrame:
    """Concatenate one per-chain CSV family back into a single frame."""
    frames = [pd.read_csv(path) for path in sorted(per_chain_dir.glob(f"{name}_*.csv"))]
    return pd.concat(frames, ignore_index=True)


def _merge_results(frontier: pd.DataFrame, mix: pd.DataFrame) -> pd.DataFrame:
    """Join the mix onto the frontier coordinates and zero the absent carriers.

    A carrier absent from one cell-year (no Brown Coal left by 2050, say) leaves NaN
    rather than the zero it means, which would poison the marginal differences.
    """
    results = frontier.merge(
        mix, on=["cell", "year"], how="left", suffixes=("", "_mix")
    )
    absent = [c for c in results.columns if c.startswith(("twh_", "share_", "gw_"))]
    results[absent] = results[absent].fillna(0.0)
    return results


def _add_load_shedding(results: pd.DataFrame) -> pd.DataFrame:
    """Flag the cells where the pressure setting outran the fleet.

    Shedding is measured against demand, not generation, because demand is the
    denominator every cost and emissions intensity on the page is quoted per.
    """
    results = results.copy()
    results["use_pct_of_demand"] = (
        results["use_mwh"] / (results["delivered_twh"] * 1e6) * 100
    )
    results["served_twh"] = results["delivered_twh"] - results["use_mwh"] / 1e6
    results["boundary"] = results["use_pct_of_demand"] > BOUNDARY_USE_PCT
    return results


def _add_pressure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Expand the pressure key into its family and value.

    Derived here rather than in the per-chain extraction so the exported tables have
    one authoritative source for what a pressure key means.
    """
    parsed = frame["pressure"].map(parse_pressure)
    return frame.assign(
        pressure_kind=parsed.map(lambda p: p.kind),
        pressure_value=parsed.map(lambda p: p.value),
    )


def _add_unpriced_fuel(results: pd.DataFrame) -> pd.DataFrame:
    """Flag cells charged nothing for fuel while fuel-burning plant ran.

    The IASR fuel-price tables end at financial year 2054-55, so the campaign's 2060
    milestone finds no price column and the post-processor's lookup returns zero. A
    cell that burns fuel but pays nothing for it understates its average cost by the
    whole fuel term, which is tens of AUD/MWh wherever gas still runs, so it is marked
    rather than quietly reported.
    """
    results = results.copy()
    burning = sum(results.get(f"share_{c}", 0.0) for c in FUEL_BURNING_CARRIERS)
    results["fuel_unpriced"] = (results["diagnostic_fuel_cost_per_mwh"] <= 0) & (
        burning > FUEL_BURNING_FLOOR_PCT
    )
    return results


def _acceptance_per_cell(results: pd.DataFrame) -> pd.DataFrame:
    """Per cell-period: did it serve its demand, and did the solver certify it?

    Termination reuses the frontier extractor's own `tolerance_robust` verdict, so the
    acceptance table and the cost coordinates are judged against one convergence rule.
    """
    return pd.DataFrame(
        {
            "cell": results["cell"],
            "year": results["year"],
            "test1_serves_demand": ~results["boundary"],
            "use_mwh": results["use_mwh"],
            "use_pct_of_demand": results["use_pct_of_demand"],
            "test4_termination": results["tolerance_robust"],
            "model_status": results["solve_model_status"],
            "solve_gap": results["solve_gap_rel"],
            "solve_pinf": results["solve_pinf_rel"],
            "solve_dinf": results["solve_dinf_rel"],
        }
    )


def _cost_monotone_rows(
    results: pd.DataFrame, years: list[int], pressures: list[Pressure], order: list[str]
) -> list[dict]:
    """Does total system cost rise with demand, at each (year, pressure)?

    Pass served cells only. A boundary cell's total is the cost of a system that did
    not meet its demand, so comparing it against a neighbour that did tests nothing.
    `trajectories_compared` records how much of the ladder each verdict rests on.
    """
    rows = []
    for year in years:
        for pressure in pressures:
            block = results[(results.year == year) & (results.pressure == pressure.key)]
            costs = block.set_index("trajectory").reindex(order).dropna(how="all")
            rows.append(
                {
                    "year": year,
                    "pressure": pressure.key,
                    "test3_cost_monotone_in_demand": bool(
                        (costs["total_cost_aud_per_yr"].diff().dropna() >= 0).all()
                    ),
                    "trajectories_compared": len(costs),
                }
            )
    return rows


def _intensity_monotone_rows(
    results: pd.DataFrame, years: list[int], caps: list[Pressure], order: list[str]
) -> list[dict]:
    """Does emissions intensity fall as the cap deepens, at each (year, trajectory)?

    Only the cap family is tested. Cap and price chains are not commensurable, so a
    ladder mixing them has no expected direction.
    """
    cap_keys = [pressure.key for pressure in caps]
    rows = []
    for year in years:
        for trajectory in order:
            block = results[(results.year == year) & (results.trajectory == trajectory)]
            block = block.set_index("pressure").reindex(cap_keys).dropna(how="all")
            rows.append(
                {
                    "year": year,
                    "trajectory": trajectory,
                    "test2_intensity_monotone_in_cap": bool(
                        (block["co2e_total_t_per_mwh"].diff().dropna() <= 0).all()
                    ),
                }
            )
    return rows


def assemble(
    per_chain_dir: Path,
    years: list[int],
    trajectories: list[Trajectory],
) -> dict[str, pd.DataFrame]:
    """Read the per-chain CSVs back and build the six campaign deliverables."""
    merged = _merge_results(
        _read_per_chain(per_chain_dir, "frontier"),
        _read_per_chain(per_chain_dir, "mix"),
    )
    results = _add_pressure_columns(_add_unpriced_fuel(_add_load_shedding(merged)))
    pressures = order_pressures(list(results["pressure"]))
    order = [trajectory.key for trajectory in trajectories]
    # A boundary cell's cost is quoted per MWh of demand it did not fully serve, so
    # differencing it against a neighbour would price the shortfall as if it were supply.
    marginals = _marginals(
        results[~results["boundary"]],
        level_order=order,
        periods=years,
        series_column="pressure",
        level_column="trajectory",
    )
    per_grid = pd.DataFrame(
        _cost_monotone_rows(results[~results["boundary"]], years, pressures, order)
        + _intensity_monotone_rows(
            results, years, [p for p in pressures if p.kind == CAP_KIND], order
        )
    )
    return {
        "results.csv": results,
        "storage.csv": _read_per_chain(per_chain_dir, "storage"),
        "marginals.csv": marginals,
        "manifest.csv": _add_pressure_columns(
            _read_per_chain(per_chain_dir, "manifest")
        ),
        "acceptance_per_cell.csv": _acceptance_per_cell(results),
        "acceptance_per_grid.csv": per_grid,
    }


# --------------------------------------------------------------------------- cli


def _chain_ids(chains_path: Path) -> list[str]:
    """Run ids of the campaign, in manifest order, from the Slurm chains table."""
    chains = pd.read_csv(
        chains_path, sep="\t", header=None, names=["run_id", "traces", "args"]
    )
    return list(chains["run_id"])


def _run_extract(
    layout: OutputLayout,
    plan: dict,
    run_ids: list[str],
    workbook_cache: Path,
    exports: Path,
) -> None:
    """Extract one chain's products, or every chain's in sequence."""
    trajectories = {t.key: t for t in trajectories_from_plan(plan)}
    years = plan["milestone_years"]
    for run_id in run_ids:
        trajectory_key, pressure_key = split_chain_id(run_id)
        solved = extract_chain_products(
            run_id,
            trajectories[trajectory_key],
            parse_pressure(pressure_key),
            years,
            layout,
            workbook_cache,
            exports / "per_chain",
        )
        print(f"  extracted {run_id}  ({len(solved)} milestones: {solved})")


def _run_assemble(plan: dict, layout: OutputLayout, chain: str) -> None:
    """Build and write the deliverable tables, and the cost inputs ``chain`` was templated from."""
    exports = layout.exports
    tables = assemble(
        exports / "per_chain",
        plan["milestone_years"],
        trajectories_from_plan(plan),
    )
    exports.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_csv(exports / name, index=False)
        print(f"  wrote {name}  ({len(frame)} rows)")
    results = tables["results.csv"]
    print(
        f"  boundary cells (load shedding above {BOUNDARY_USE_PCT}% of demand): "
        f"{results['boundary'].sum()}"
    )
    print(
        "  cells with unpriced fuel (milestone beyond the IASR price tables): "
        f"{results['fuel_unpriced'].sum()}"
    )
    _write_input_costs(layout, chain, plan["milestone_years"])


def _submit_extract(layout: OutputLayout, n_chains: int, assemble_after: bool) -> None:
    """Read the networks on compute nodes: one array task per chain, then one assemble task.

    The assemble task is submitted only when this invocation owns both stages; a
    ``--stage extract`` run leaves assembly to a later ``--stage assemble`` call.
    """
    env = Env.from_env()
    script = Path(__file__).resolve().parents[1] / "hpc" / "slurm" / "extract.sbatch"
    array_job = submit(script, f"0-{n_chains - 1}", {"STAGE": "extract"}, layout, env)
    if assemble_after:
        submit(script, "0", {"STAGE": "assemble"}, layout, env, f"afterok:{array_job}")


def main(
    run: Path,
    only: str | None = None,
    stage: Literal["extract", "assemble", "all"] = "all",
    local: bool = False,
) -> None:
    """Build the extension campaign deliverables for one stamped run directory.

    :param run: Stamped run directory, ``$IO_DIR/outputs/<stamp>_<run_set>``.
    :param only: Extract just this chain, for parallel extraction. A single chain is
        always read in-process: it is the unit one array task already covers.
    :param stage: Which half to run: per-chain extraction, assembly, or both.
    :param local: Read solved networks in-process even when Slurm is available.
        Otherwise, when the extraction stage needs to run and Slurm is present,
        it is submitted as an array job rather than reading networks here.
    """
    layout = OutputLayout(run)
    chains = layout.campaign / "chains.tsv"
    plan_data = json.loads(
        (layout.campaign / "demand_plan.json").read_text(encoding="utf-8")
    )
    needs_networks = stage in ("extract", "all")
    if needs_networks and not only and not local and shutil.which("sbatch"):
        _submit_extract(layout, len(_chain_ids(chains)), assemble_after=stage == "all")
        return
    if needs_networks:
        workbook_cache = Env.from_env().workbook_cache
        run_ids = [only] if only else _chain_ids(chains)
        _run_extract(layout, plan_data, run_ids, workbook_cache, layout.exports)
    if stage in ("assemble", "all"):
        _run_assemble(plan_data, layout, _chain_ids(chains)[0])
