"""Extract the production trajectory-sweep menu: one tidy row per (sweep_id, year).

Each chained-solve year emits a coordinate row with ONE primary cost column
and a year-t-incremental diagnostic alongside it:

  cost_per_mwh_excl_fuel_carbon   PRIMARY / Pass-2 contract. The full-fleet
                            intensity: year-t spend PLUS the annuitised capex+FOM
                            of every surviving prior vintage, re-attributed from
                            each prior year's solved NetCDF (original
                            capital_cost x p_nom_opt, filtered still-active by
                            build_year + lifetime > t), accumulated over ALL
                            surviving prior vintages (by 2050, up to four). Fuel
                            and carbon stripped; T&S retained. This is the only
                            column valid for cross-trajectory / cross-year cost
                            selection because it carries the operating cost of the
                            WHOLE fleet.

  diagnostic_cost_per_mwh_year_t_incremental   DIAGNOSTIC, not the intensity.
                            Carbon-and-fuel-stripped year-t LP spend; carried
                            brownfield rows entered the LP at capital_cost=0.0, so
                            their capex AND FOM are attributed to build-year. It
                            excludes the operating cost of the carried fleet
                            (~86% of capacity by 2050) and must NOT be read as the
                            cost of electricity. Retained for build-year-allocation
                            bookkeeping.

WHY THE PRIMARY IS THE FULL-FLEET NUMBER: ISPyPSA bundles FOM
into capital_cost at the source (translator/generators.py:
capital_cost = annuitised_capex + fom_$/kw/annum x 1000), and the pypsa-friendly
generators.csv exposes no separable FOM column. The recursive-dynamic write-back
zeroes capital_cost on carried rows by design (they must not re-bill capex inside
the next year's LP) -- which silently zeroes their FOM too. A year-t-incremental
column therefore omits the FOM of the entire carried fleet, so it cannot be the
contract intensity. Disaggregating capex from FOM is impossible with current
inputs (the IASR data does not carry the split) and is left as a known refinement
for a future IASR vintage that splits them.

The re-attribution reads the ORIGINAL capital_cost from each prior year's
solved network -- the tranche parquets cannot supply it because the write-back
zeroes capital_cost by design. Vintage-y rows are isolated in the year-y network
by (p_nom_extendable & build_year == y & p_nom_opt > 1 MW): carried rows in a
chained year-y network are non-extendable, so the filter never double-counts
earlier vintages. Note this re-attributes only the chain's OWN vintages
(2030..t-1), never ISPyPSA's native pre-2030 existing fleet (capital_cost=0,
genuinely sunk) -- a common constant across trajectories that cancels in any
cross-trajectory comparison.

Emissions and fuel intensities are physical quantities of the price-shaped
dispatch (CCS at residual = gross x (1 - capture_rate)) -- single column each,
no accounting ambiguity.

Compositions (capacity by carrier) are emitted to a SEPARATE diagnostics file
marked non-contract: at the certified tolerance the flat-objective face makes
individual-technology compositions soft (~30-70%); coordinates are the
certified quantity.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd
import pypsa

from analysis.env import OutputLayout
from analysis.sharp.method_years import _capital_rate, extract_method_year_row

log = logging.getLogger(__name__)

_P_NOM_OPT_THRESHOLD_MW = 1.0
_TOLERANCE = 3e-3
# Gurobi barrier (crossover off) reports absolute primal/dual infeasibility, not
# PDLP's relative gap. The dual-infeasibility is the reliable convergence
# discriminator for the production frontier: the largest (2050) LPs terminate
# dually-non-converged (dinf O(1)) with a corrupted objective field but a
# primal-sane solution, while 2030-2045 converge to dinf ~1e-4.
_GUROBI_DUAL_INF_TOL = 1e-2
# The inherited-fleet (ECAA) rosters: (PyPSA component, roster file, name column).
_ECAA_ROSTERS = (
    ("generators", "ecaa_generators.csv", "generator"),
    ("storage_units", "ecaa_batteries.csv", "storage_name"),
)
# The LP keeping charge and the roster FOM are two readings of the same physical
# quantity, so they agree to rounding when both are present. Anything wider means
# the two sources disagree and the row's retention charge is not trustworthy.
_RETENTION_RECONCILE_TOL = 0.01


def extract_frontier_point(
    sweep_id: str,
    year: int,
    prior_year_ncs: dict[int, Path],
    network_path: Path,
    pypsa_friendly_dir: Path,
    ispypsa_inputs_dir: Path,
    workbook_cache: Path,
    record_path: Path,
    carbon_price: float,
    tns_price: float,
) -> tuple[dict, pd.DataFrame]:
    """One (sweep_id, year) coordinate row + its composition diagnostic.

    prior_year_ncs maps each PRIOR chain year to its solved NetCDF -- the
    source of original vintage capex for the full-fleet re-attribution.
    ispypsa_inputs_dir supplies the ECAA roster (fom_$/kw/annum per existing
    unit) for the existing-fleet FOM re-attribution.
    """
    network = pypsa.Network(network_path)
    base = extract_method_year_row(
        network,
        pypsa_friendly_dir,
        workbook_cache,
        year,
        archetype_id=sweep_id,
        archetype_bounds={},
        carbon_price=carbon_price,
        tns_price=tns_price,
    )
    carried = _carried_vintage_capex(prior_year_ncs, at_year=year)
    existing_fom = _existing_fleet_fom(network, ispypsa_inputs_dir, at_year=year)
    diagnostics = _solve_diagnostics(record_path)
    row = _assemble_frontier_row(
        sweep_id,
        year,
        carbon_price,
        tns_price,
        base,
        carried,
        existing_fom,
        diagnostics,
    )
    composition = _composition_diagnostic(network, sweep_id, year)
    return row | _premiums_paid(network_path.parents[1]), composition


def _premiums_paid(run_root: Path) -> dict[str, float]:
    """Social-licence and build-rate premiums the solve paid, zero where the run priced neither."""
    tranches = run_root / "outputs" / "capacity_tranches.json"
    paid = (
        pd.read_json(tranches).groupby("kind")["premium_aud_per_yr"].sum()
        if tranches.exists()
        else pd.Series(dtype=float)
    )
    return {
        "social_licence_premium_aud_per_yr": float(paid.get("transmission", 0.0)),
        "build_rate_premium_aud_per_yr": float(paid.get("build_rate", 0.0)),
    }


def _existing_fleet_fom(
    network: pypsa.Network, ispypsa_inputs_dir: Path, at_year: int
) -> dict:
    """Annual FOM of the inherited (ECAA) fleet still active at at_year.

    ISPyPSA sets ECAA capital_cost=0 (sunk) at translation, which also zeroes the
    FOM that the new-entrant path bundles into capital_cost -- so the existing
    fleet's fixed O&M is absent from the LP objective AND from every cost column.
    Because ECAA capacity is non-extendable and retires on a deterministic
    closure_year (not an economic decision), zeroing its FOM left the solves
    physically correct, so this is a pure post-hoc re-attribution.

    The ECAA-roster name is the partition discriminator: carried tranches and
    current-year new-build are NOT in the roster, so this term never overlaps the
    carried-vintage capex (which already carries those vintages' FOM) or the
    year-t new-build capex. Only capacity still active at at_year
    (build_year + lifetime > at_year) is billed, matching the retirement filter
    the dispatch already respects.

    This roster figure is only ADDED to the cost when the LP itself charged
    nothing for keeping the fleet. A chain run with `--reducible-existing
    --existing-fom-keeping` sets each ECAA unit's `capital_cost` to its FOM, so
    the year-t LP spend already carries the retention charge and adding this term
    would bill it twice. `_assemble_frontier_row` decides using
    `_lp_keeping_charge_aud`; this function always reports the roster figure as a
    diagnostic regardless of which way that decision goes.
    """
    total_aud, active_mw = 0.0, 0.0
    for component, roster_file, name_col in _ECAA_ROSTERS:
        aud, mw = _roster_fom(
            network, component, ispypsa_inputs_dir / roster_file, name_col, at_year
        )
        total_aud += aud
        active_mw += mw
    return {
        "existing_fleet_fom_aud_per_yr": total_aud,
        "existing_fleet_active_gw": active_mw / 1000.0,
        "existing_fleet_lp_keeping_charge_aud_per_yr": _lp_keeping_charge_aud(
            network, _ecaa_roster_names(ispypsa_inputs_dir)
        ),
    }


def _ecaa_roster_names(ispypsa_inputs_dir: Path) -> set[str]:
    """Every inherited-fleet (ECAA) unit name, across the generator and battery
    rosters."""
    names: set[str] = set()
    for _, roster_file, name_col in _ECAA_ROSTERS:
        roster_path = ispypsa_inputs_dir / roster_file
        if roster_path.exists():
            names |= set(pd.read_csv(roster_path)[name_col].astype(str))
    return names


def _lp_keeping_charge_aud(network: pypsa.Network, ecaa_names: set[str]) -> float:
    """Retention charge the LP itself billed on the inherited fleet, AUD/yr.

    A chain run with `--reducible-existing --existing-fom-keeping` writes each
    ECAA unit's FOM into `capital_cost` (see benchmarks/retirement.py
    `make_existing_reducible`), so this is nonzero exactly when the year-t LP
    spend already carries the retained-fleet fixed cost. Without FOM keeping,
    ISPyPSA leaves ECAA `capital_cost` at 0 and this is zero.
    """
    total = 0.0
    for component, _, _ in _ECAA_ROSTERS:
        df = getattr(network, component)
        rows = df[df.index.astype(str).isin(ecaa_names)]
        total += float((rows["capital_cost"] * rows["p_nom_opt"]).sum())
    return total


def _roster_fom(
    network: pypsa.Network,
    component: str,
    roster_path: Path,
    name_col: str,
    at_year: int,
) -> tuple[float, float]:
    """Sum of fom_$/kw/annum x active MW x 1000 for one ECAA roster (gens or storage)."""
    if not roster_path.exists():
        return 0.0, 0.0
    fom = pd.read_csv(roster_path).set_index(name_col)["fom_$/kw/annum"]
    df = getattr(network, component)
    df = df[df.index.isin(fom.index)]  # ECAA-roster membership = the partition
    active = df[df["build_year"] + df["lifetime"] > at_year]
    rate = pd.to_numeric(fom.reindex(active.index), errors="coerce").fillna(0.0)
    cap_mw = active["p_nom_opt"] if "p_nom_opt" in active.columns else active["p_nom"]
    return float((rate * cap_mw * 1000.0).sum()), float(cap_mw.sum())


def _carried_vintage_capex(prior_year_ncs: dict[int, Path], at_year: int) -> dict:
    """Annualised capex of all surviving prior vintages, re-attributed from
    each prior year's solved network at its ORIGINAL capital_cost."""
    per_vintage: dict[int, float] = {}
    total_gw = 0.0
    for vintage_year in sorted(prior_year_ncs):
        capex, gw = _one_vintage_capex(
            prior_year_ncs[vintage_year], vintage_year, at_year
        )
        per_vintage[vintage_year] = capex
        total_gw += gw
    return {
        "carried_capex_aud_per_yr": sum(per_vintage.values()),
        "carried_capex_by_vintage": per_vintage,
        "carried_vintages": len(per_vintage),
        "carried_gw": total_gw,
    }


def _one_vintage_capex(
    nc_path: Path, vintage_year: int, at_year: int
) -> tuple[float, float]:
    """capital rate x p_nom_opt of vintage-year new builds still active at
    at_year, summed over generators and storage units."""
    network = pypsa.Network(nc_path)
    gen = _surviving_new_builds(network.generators, vintage_year, at_year)
    stor = _surviving_new_builds(network.storage_units, vintage_year, at_year)
    capex = float((_capital_rate(gen) * gen["p_nom_opt"]).sum()) + float(
        (_capital_rate(stor) * stor["p_nom_opt"]).sum()
    )
    gw = (float(gen["p_nom_opt"].sum()) + float(stor["p_nom_opt"].sum())) / 1000.0
    return capex, gw


def _surviving_new_builds(
    df: pd.DataFrame, vintage_year: int, at_year: int
) -> pd.DataFrame:
    """Vintage-year new-entrant rows still active at at_year. Extendable +
    build_year filters isolate the vintage; carried rows are non-extendable."""
    if df.empty:
        return df
    if "bus" in df.columns:
        df = df[df["bus"] != "bus_for_custom_constraint_gens"]
    mask = (
        df["p_nom_extendable"]
        & (df["build_year"] == vintage_year)
        & (df["p_nom_opt"] > _P_NOM_OPT_THRESHOLD_MW)
        & (df["build_year"] + df["lifetime"] > at_year)
    )
    return df.loc[mask]


def _solve_diagnostics(record_path: Path) -> dict:
    """Convergence metrics from the instrumented-runner record.

    Handles both PDLP records (`pdlp_final_*_rel`, relative metrics judged
    against `_TOLERANCE`) and Gurobi-barrier records (`ipm_final_*` absolute
    metrics + `gurobi_barrier_iterations`). For the Gurobi production frontier
    `tolerance_robust` is set from primal+dual infeasibility < `_GUROBI_DUAL_INF_TOL`
    -- this flags the 2050 LPs (dually-non-converged, corrupted objective field,
    primal-sane) as not-robust while passing 2030-2045. The `solve_*_rel` column
    names are retained across both solvers; for Gurobi they carry the barrier's
    absolute primal/dual infeasibility and complementarity gap.
    """
    rec = json.loads(record_path.read_text())
    # Branch on the metric itself: a Gurobi record whose log parse missed the iteration
    # count still carries ipm_final_pinf, and must not be judged by absent PDLP fields.
    if rec.get("ipm_final_pinf") is not None:
        gap, pinf, dinf = (
            rec.get("ipm_final_gap"),
            rec.get("ipm_final_pinf"),
            rec.get("ipm_final_dinf"),
        )
        iters = rec.get("gurobi_barrier_iterations")
        robust = (
            pinf is not None
            and dinf is not None
            and pinf < _GUROBI_DUAL_INF_TOL
            and dinf < _GUROBI_DUAL_INF_TOL
        )
    else:
        gap = rec.get("pdlp_final_gap_rel")
        pinf = rec.get("pdlp_final_pinf_rel")
        dinf = rec.get("pdlp_final_dinf_rel")
        iters = rec.get("pdlp_iterations")
        metrics = [m for m in (gap, pinf, dinf) if m is not None]
        robust = bool(metrics) and all(m <= _TOLERANCE for m in metrics)
    return {
        "solve_gap_rel": gap,
        "solve_pinf_rel": pinf,
        "solve_dinf_rel": dinf,
        "solve_iterations": iters,
        "solve_wall_s": rec.get("solve_s"),
        "solve_model_status": rec.get("model_status"),
        "tolerance_robust": robust,
    }


def _assemble_frontier_row(
    sweep_id: str,
    year: int,
    carbon_price: float,
    tns_price: float,
    base: dict,
    carried: dict,
    existing_fom: dict,
    diagnostics: dict,
) -> dict:
    """Tidy frontier row: the contract cost column first, diagnostics after.

    PRIMARY CONTRACT COLUMN -- `cost_per_mwh_excl_fuel_carbon`. This is the
    full-fleet intensity: year-t spend PLUS the annuitised capex+FOM of every
    surviving prior vintage, re-attributed from each vintage's original
    capital_cost (which bundles capex+FOM at the source -- see
    translator/generators.py: capital_cost = annuitised_capex + fomx1000), with
    fuel and carbon stripped, T&S retained. It is the only column valid for the
    menu's actual use (cross-trajectory and cross-year selection) because it
    carries the operating cost of the WHOLE fleet, not just year-t's new build.

    DIAGNOSTIC -- `cost_per_mwh_year_t_incremental`. The carbon-and-fuel-stripped
    year-t LP spend: carried brownfield rows entered the year-t LP at
    capital_cost=0.0, so their capex AND FOM are attributed to their build-year,
    not billed here. Useful trajectory-internal bookkeeping if simple-msm ever
    wants the build-year allocation; it is NOT the cost intensity, because it
    excludes the operating cost of the carried fleet (~86% of capacity by 2050).

    INHERITED-FLEET FOM -- added to the primary only when the LP charged nothing
    for keeping the inherited (ECAA) fleet. A FOM-keeping run writes each ECAA
    unit's FOM into `capital_cost`, so the year-t incremental already carries the
    retention charge and re-adding the roster figure would bill the whole
    inherited fleet twice. `retention_charge_counted_once` reports the outcome of
    that reconciliation per row.
    """
    annual_mwh = base["diagnostic_annual_mwh_delivered"]
    year_t_incremental = base["diagnostic_cost_per_unit_excl_fuel_and_carbon"]
    roster_fom_aud = existing_fom["existing_fleet_fom_aud_per_yr"]
    lp_keeping_aud = existing_fom["existing_fleet_lp_keeping_charge_aud_per_yr"]
    # Full-fleet = year-t spend + carried-vintage capex+FOM + existing-fleet FOM.
    # The last term is added only when the LP charged nothing for keeping the
    # inherited fleet: a FOM-keeping run puts that same charge in ECAA
    # `capital_cost`, where the year-t LP spend already picks it up.
    fleet_fixed_aud = carried["carried_capex_aud_per_yr"] + (
        0.0 if lp_keeping_aud > 0 else roster_fom_aud
    )
    excl_fuel_carbon = year_t_incremental + (
        fleet_fixed_aud / annual_mwh if annual_mwh > 0 else 0.0
    )
    emissions = base["energy_emissions_by_pollutant"]
    fuel_cols = {
        f"gj_per_mwh_{commodity}": coeff
        for commodity, coeff in zip(
            base["input_commodities"], base["input_coefficients"]
        )
    }
    return {
        "sweep_id": sweep_id,
        "carbon_price_aud_per_tco2e": carbon_price,
        "tns_price_aud_per_tco2": tns_price,
        "year": year,
        "cost_per_mwh_excl_fuel_carbon": excl_fuel_carbon,
        "co2_t_per_mwh": emissions["CO2"],
        "co2e_total_t_per_mwh": emissions["total_CO2e"],
        **fuel_cols,
        "annual_generation_twh": annual_mwh / 1e6,
        **diagnostics,
        "carried_capex_aud_per_yr": carried["carried_capex_aud_per_yr"],
        "carried_vintages": carried["carried_vintages"],
        "carried_gw": carried["carried_gw"],
        "existing_fleet_fom_aud_per_yr": roster_fom_aud,
        "existing_fleet_lp_keeping_charge_aud_per_yr": lp_keeping_aud,
        "retention_charge_counted_once": _retention_charge_counted_once(
            lp_keeping_aud, roster_fom_aud
        ),
        "existing_fleet_active_gw": existing_fom["existing_fleet_active_gw"],
        "renewable_share_pct_bulk_grid": base["renewable_share_pct"],
        "diagnostic_cost_per_mwh_year_t_incremental": year_t_incremental,
        "diagnostic_bundled_cost_per_mwh": base["diagnostic_bundled_cost_per_unit"],
        "diagnostic_fuel_cost_per_mwh": base["diagnostic_fuel_cost_per_unit"],
        "diagnostic_carbon_cost_per_mwh": base["diagnostic_carbon_cost_per_unit"],
    }


def _retention_charge_counted_once(
    lp_keeping_aud: float, roster_fom_aud: float
) -> bool:
    """Whether the inherited fleet's retention charge is billed exactly once.

    True when the LP charged nothing (so the roster FOM supplies the only copy)
    or when the LP charge reconciles with the roster FOM to within
    `_RETENTION_RECONCILE_TOL` (so dropping the roster copy loses nothing). False
    flags a row where the two readings of the retention charge disagree.
    """
    if lp_keeping_aud == 0.0:
        return True
    gap = abs(lp_keeping_aud - roster_fom_aud)
    return gap <= _RETENTION_RECONCILE_TOL * roster_fom_aud


def _composition_diagnostic(
    network: pypsa.Network, sweep_id: str, year: int
) -> pd.DataFrame:
    """Capacity by carrier (GW) -- NON-CONTRACT diagnostic. Compositions are
    within-margin soft at the certified tolerance; coordinates are the
    certified quantity."""
    gens = network.generators
    gens = gens[gens["bus"] != "bus_for_custom_constraint_gens"]
    gens = gens[gens["carrier"] != "Unserved Energy"]
    active = gens[gens["build_year"] + gens["lifetime"] > year]
    by_carrier = active["p_nom_opt"].fillna(0).groupby(active["carrier"]).sum() / 1000.0
    out = by_carrier.reset_index()
    out.columns = ["carrier", "capacity_gw"]
    out.insert(0, "year", year)
    out.insert(0, "sweep_id", sweep_id)
    return out


# ---------- chain-level orchestration ----------


def extract_chain(
    sweep_id: str,
    run_id: str,
    years: list[int],
    carbon_price: float,
    tns_price: float,
    layout: OutputLayout,
    workbook_cache: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """All frontier rows + composition diagnostics for one chained sweep.

    Every path follows the `msm solve` naming convention through `layout`: one run
    directory and one solver record per `{run_id}_{year}`.
    """
    rows, compositions = [], []
    for year in years:
        run_root = layout.run_dir(f"{run_id}_{year}")
        prior_ncs = {y: layout.network(f"{run_id}_{y}") for y in years if y < year}
        row, composition = extract_frontier_point(
            sweep_id,
            year,
            prior_ncs,
            network_path=run_root / "outputs" / "capacity_expansion.nc",
            pypsa_friendly_dir=run_root / "pypsa_friendly",
            ispypsa_inputs_dir=run_root / "ispypsa_inputs",
            workbook_cache=workbook_cache,
            record_path=layout.record(f"{run_id}_{year}"),
            carbon_price=carbon_price,
            tns_price=tns_price,
        )
        rows.append(row)
        compositions.append(composition)
    return pd.DataFrame(rows), pd.concat(compositions, ignore_index=True)
