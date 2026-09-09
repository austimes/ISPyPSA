"""Per-cell retained-fleet cost export for the ShARP translation.

The sweep's solved networks (~18 GB) are not in the repository, so this script
exports the retained-fleet quantities the ShARP agent needs to QUANTIFY the
retained-fleet cost correction rather than estimate it. One row per Dataset B
cell-year, read directly from the solved network plus its ispypsa_inputs:

  existing_installed_mw     p_nom_max over the reducible ECAA fleet (the cap
                            make_existing_reducible set: installed, or the
                            prior period's monotone retention floor)
  existing_retained_mw      p_nom_opt over the same units (the endogenous
                            retirement decision; retained < installed is
                            economic retirement)
  existing_keeping_cost_aud sum(capital_cost x p_nom_opt) over those units —
                            the per-unit AEMO FOM keeping-cost actually paid
                            on RETAINED capacity in the LP objective
  retained_mw_<carrier>     the retained capacity split by carrier
  carried_capex_aud_per_yr  joined from the committed results.csv (the prior
  existing_fleet_fom_aud    vintages' re-attributed annualised capex, and the
                            extractor's own existing-fleet FOM figure — the
                            keeping-cost column above should reconcile with it;
                            any gap is reported, not smoothed)

Usage:
    uv run python analysis/intensity_demand_map/scripts/export_retained_fleet.py
"""

from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
OUT = Path("analysis/intensity_demand_map")
CARBON_PRICES = [0, 150, 300, 550]
DEMAND_LEVELS = ["d087", "d100", "d110", "d123"]
YEARS = [2030, 2040, 2050]


def _cell_row(carbon_price: int, level: str, year: int) -> dict:
    cell = f"sweep_c{carbon_price}_{level}"
    root = RUNS / f"{cell}_{year}__cost_optimal"
    network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")
    ecaa_names = set(
        pd.read_csv(root / "ispypsa_inputs" / "ecaa_generators.csv")["generator"]
        .astype(str)
    )
    gens = network.generators
    existing = gens.index.astype(str).isin(ecaa_names)

    row = {
        "cell": cell,
        "carbon_price": carbon_price,
        "demand_level": level,
        "year": year,
        "existing_units": int(existing.sum()),
        "existing_installed_mw": float(gens.loc[existing, "p_nom_max"].sum()),
        "existing_retained_mw": float(gens.loc[existing, "p_nom_opt"].sum()),
        "existing_keeping_cost_aud_per_yr": float(
            (gens.loc[existing, "capital_cost"] * gens.loc[existing, "p_nom_opt"]).sum()
        ),
    }
    row["existing_retired_mw"] = (
        row["existing_installed_mw"] - row["existing_retained_mw"]
    )
    retained_by_carrier = (
        gens.loc[existing].groupby("carrier")["p_nom_opt"].sum()
    )
    for carrier, mw in retained_by_carrier.items():
        key = carrier.lower().replace(" ", "_")
        row[f"retained_mw_{key}"] = float(mw)
    return row


def main() -> None:
    rows = []
    for carbon_price in CARBON_PRICES:
        for level in DEMAND_LEVELS:
            for year in YEARS:
                rows.append(_cell_row(carbon_price, level, year))
                print(f"  {rows[-1]['cell']}_{year}: retained "
                      f"{rows[-1]['existing_retained_mw']:.0f} of "
                      f"{rows[-1]['existing_installed_mw']:.0f} MW, keeping cost "
                      f"{rows[-1]['existing_keeping_cost_aud_per_yr'] / 1e6:.1f} $m/yr")
    frame = pd.DataFrame(rows).fillna(0.0)

    results = pd.read_csv("analysis/demand_carbon_sweep/results.csv")
    frame = frame.merge(
        results[["cell", "year", "carried_capex_aud_per_yr",
                 "existing_fleet_fom_aud_per_yr", "carried_gw",
                 "cost_per_mwh_excl_fuel_carbon", "avg_cost_aud_per_mwh",
                 "delivered_twh"]],
        on=["cell", "year"], how="left",
    )
    # Reconciliation column: the extractor's existing-fleet FOM vs the keeping
    # cost read from the LP. A nonzero gap is reported for the reader to judge.
    frame["keeping_vs_extractor_fom_ratio"] = (
        frame["existing_keeping_cost_aud_per_yr"]
        / frame["existing_fleet_fom_aud_per_yr"]
    )
    out_path = OUT / "sweep_retained_fleet_costs.csv"
    frame.to_csv(out_path, index=False)
    print(f"\nwrote {out_path} ({len(frame)} rows)")
    print("\nreconciliation (keeping cost / extractor FOM):")
    print(frame["keeping_vs_extractor_fom_ratio"].describe().round(4).to_string())


if __name__ == "__main__":
    main()
