"""Stage 1 analysis: reproduction check, cap behaviour, dual-vs-chordal gate.

1. Reproduction: the uncapped conditioned cell (idm_d100_u_2040, Gurobi) against
   the conditioning chain's own solve (sweep_c0_d100_2040, PDLP 3e-3) — same LP,
   same carried state, different solver. Reports generation shares, delivered
   energy, emissions, objective.
2. Cap behaviour: i100 (cap at the conditioned realised intensity) and i050
   (0.5x): binding status, dual finiteness and sign, implied carbon price.
3. Dual-vs-chordal: chordal marginal between i100 and i050 on both the LP
   objective and the rebuilt total cost, against the tighter cell's (i050) dual.
   DECISION RULE: difference beyond 25% stops the stage.

Usage:
    uv run python analysis/intensity_demand_map/scripts/pilot_analysis.py
"""

import json
import sys
from pathlib import Path

import pandas as pd
import pypsa

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from analysis.intensity_demand_map.scripts.extract_cell import extract_cell  # noqa: E402

RECORDS = Path("analysis/benchmarks/records")
RUNS = Path("analysis/benchmarks/runs_myopic")
DUAL_CHORDAL_TOLERANCE = 0.25


def _chain_reference() -> dict:
    """The conditioning chain's own 2040 solve, on the same measures."""
    root = RUNS / "sweep_c0_d100_2040__cost_optimal"
    network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")
    pf = pd.read_csv(root / "pypsa_friendly" / "generators.csv").set_index("name")
    weights = network.snapshot_weightings["generators"]
    energy = network.generators_t.p.clip(lower=0).mul(weights, axis=0).sum()
    gens = network.generators
    real = (gens["bus"] != "bus_for_custom_constraint_gens") & (
        gens["carrier"] != "Unserved Energy"
    )
    by_carrier = energy[real[energy.index]].groupby(
        gens.loc[real, "carrier"]
    ).sum() / 1e6
    resid = pd.to_numeric(pf["isp_residual_co2_t_per_mwh"], errors="coerce").fillna(0.0)
    record = json.loads((RECORDS / "sweep_c0_d100_2040.json").read_text())
    return {
        "by_carrier_twh": by_carrier,
        "delivered_twh": float(network.loads_t.p_set.sum(axis=1).mul(weights).sum()) / 1e6,
        "residual_co2e_t": float((energy * resid.reindex(energy.index).fillna(0.0)).sum()),
        "objective": record.get("objective_value"),
        "solver": "PDLP 3e-3",
    }


def main() -> None:
    reference = _chain_reference()
    cells = {key: extract_cell(f"idm_d100_{key}_2040") for key in ("u", "i100", "i050")}

    print("=== 1. Reproduction: uncapped conditioned cell vs conditioning chain ===")
    u = cells["u"]
    print(f"{'quantity':<28}{'chain (PDLP 3e-3)':>20}{'map u-cell (Gurobi)':>22}{'delta':>12}")
    ref_total = float(reference["by_carrier_twh"].sum())
    for carrier, twh in reference["by_carrier_twh"].items():
        key = carrier.lower().replace(" ", "_")
        # u-cell reports gas split; recombine for the carrier comparison
        if carrier == "Gas":
            map_twh = u.get("twh_gas_unabated", 0.0) + u.get("twh_gas_ccs", 0.0)
        else:
            map_twh = u.get(f"twh_{key}", 0.0)
        ref_share = twh / ref_total * 100
        map_share = map_twh / u["generation_twh"] * 100
        print(f"{carrier:<28}{ref_share:>19.3f}%{map_share:>21.3f}%"
              f"{map_share - ref_share:>11.3f}pp")
    print(f"{'delivered TWh':<28}{reference['delivered_twh']:>20.3f}"
          f"{u['delivered_twh']:>22.3f}"
          f"{(u['delivered_twh'] / reference['delivered_twh'] - 1) * 100:>11.3f}%")
    print(f"{'residual CO2e Mt':<28}{reference['residual_co2e_t'] / 1e6:>20.3f}"
          f"{u['residual_co2e_t'] / 1e6:>22.3f}"
          f"{(u['residual_co2e_t'] / reference['residual_co2e_t'] - 1) * 100:>11.3f}%")
    if reference["objective"] and u.get("rec_objective_value"):
        print(f"{'LP objective':<28}{reference['objective']:>20.4g}"
              f"{u['rec_objective_value']:>22.4g}"
              f"{(u['rec_objective_value'] / reference['objective'] - 1) * 100:>11.4f}%")

    print("\n=== 2. Cap behaviour ===")
    for key in ("i100", "i050"):
        cell = cells[key]
        cap = cell["rec_co2_cap_annual_t"]
        print(f"{key}: cap {cap / 1e6:.3f} Mt, realised {cell['residual_co2e_t'] / 1e6:.3f} Mt "
              f"(ratio {cell['residual_co2e_t'] / cap:.6f}), "
              f"dual_raw {cell.get('co2_cap_dual_raw')}, "
              f"implied A$/t {cell.get('implied_carbon_price_aud_per_t')}, "
              f"status {cell.get('rec_model_status')}, "
              f"USE {cell['use_mwh']:.3f} MWh, "
              f"solve {cell.get('rec_solve_s', 0) / 60:.1f} min")

    print("\n=== 3. Dual-vs-chordal (gate: 25%) ===")
    a, b = cells["i050"], cells["i100"]  # tight, loose
    d_t = b["residual_co2e_t"] - a["residual_co2e_t"]
    chordal_obj = -(b["rec_objective_value"] - a["rec_objective_value"]) / d_t
    dual_tight = a.get("implied_carbon_price_aud_per_t")
    ratio = dual_tight / chordal_obj if chordal_obj else float("nan")
    print(f"delta emissions: {d_t / 1e6:.3f} Mt")
    print(f"chordal (LP objective): {chordal_obj:.2f} AUD/t")
    print(f"dual (tight cell i050): {dual_tight:.2f} AUD/t")
    print(f"dual / chordal: {ratio:.4f}")
    verdict = abs(ratio - 1) <= DUAL_CHORDAL_TOLERANCE
    print(f"GATE {'PASS' if verdict else 'FAIL — STOP AND REPORT'} "
          f"(|ratio-1| = {abs(ratio - 1):.4f} vs {DUAL_CHORDAL_TOLERANCE})")
    print("\nNote: a convex surface puts the chordal between the two endpoint "
          "duals; exact equality is not expected. The loose cell's dual "
          f"({b.get('implied_carbon_price_aud_per_t')}) brackets from below.")


if __name__ == "__main__":
    main()
