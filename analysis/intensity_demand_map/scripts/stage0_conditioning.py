"""Stage 0 audit for the intensity x demand map.

Runs entirely against the previous sweep's solved conditioning chain
(`sweep_c0_d100`, the $0/t carbon price at Step Change demand — the model's own
current-policy state) and answers, from solved networks rather than commit
subjects or memos:

  0.R  the four gas-share repairs, re-confirmed functionally in this working state
  0.1  the fleet state each milestone-year map solve will be conditioned on, and
       its gap to the colleague's current-policy pathway anchors (quantity and share)
  0.5  the renewable-share definitions: how the previous sweep computed
       `renewable_fraction_pct`, the postprocess `renewable_share_pct_bulk_grid`,
       and the colleague's convention (r_total / r_VRE) side by side
  plus the conditioned pathway's realised intensity (iota_planned) per year on the
  same per-generator residual-CO2e basis the map's emissions cap will use, and the
  abated/unabated gas split (the Stage 0.4 reporting fix, demonstrated).

Writes `analysis/intensity_demand_map/stage0_conditioning.csv` and prints the report.

Usage:
    uv run python analysis/intensity_demand_map/scripts/stage0_conditioning.py
"""

from pathlib import Path

import pandas as pd
import pypsa

RUNS = Path("analysis/benchmarks/runs_myopic")
OUT = Path("analysis/intensity_demand_map")
CHAIN = "sweep_c0_d100"
YEARS = [2030, 2040, 2050]

RENEWABLE_CARRIERS = {"Wind", "Solar", "Water", "Biomass"}
VRE_CARRIERS = {"Wind", "Solar"}
SLACK_BUS = "bus_for_custom_constraint_gens"

# The colleague's current-policy pathway anchors: planned quantity P_y/1.3 on the
# NEM source-generation boundary (TWh) and planned renewable share.
ANCHOR_QUANTITY_TWH = {2030: 211.54, 2040: 292.31, 2050: 330.77}
ANCHOR_RENEWABLE_SHARE = {2030: 0.796, 2040: 0.940, 2050: 0.974}


def _run_root(year: int) -> Path:
    return RUNS / f"{CHAIN}_{year}__cost_optimal"


def _annual_mwh_per_generator(network: pypsa.Network) -> pd.Series:
    weights = network.snapshot_weightings["generators"]
    return network.generators_t.p.clip(lower=0).mul(weights, axis=0).sum()


def _delivered_mwh(network: pypsa.Network) -> float:
    weights = network.snapshot_weightings["generators"]
    return float(network.loads_t.p_set.sum(axis=1).mul(weights).sum())


def _share_definitions(network: pypsa.Network, energy: pd.Series) -> dict:
    """The three renewable-share definitions, computed from one dispatch vector."""
    gens = network.generators
    by_carrier_all = energy.groupby(gens["carrier"]).sum()

    real = (gens["bus"] != SLACK_BUS) & (gens["carrier"] != "Unserved Energy")
    energy_real = energy[real[energy.index]]
    by_carrier_real = energy_real.groupby(gens.loc[energy_real.index, "carrier"]).sum()

    total_all = by_carrier_all.sum()
    total_real = by_carrier_real.sum()
    renewable_all = sum(by_carrier_all.get(c, 0.0) for c in RENEWABLE_CARRIERS)
    renewable_real = sum(by_carrier_real.get(c, 0.0) for c in RENEWABLE_CARRIERS)
    vre_real = sum(by_carrier_real.get(c, 0.0) for c in VRE_CARRIERS)
    slack_mwh = float(energy[gens["bus"] == SLACK_BUS].sum())
    return {
        # build_deliverables.py `_mix_row`: ALL generators in the denominator,
        # including the custom-constraint slack generators and unserved energy.
        "prev_renewable_fraction_pct": renewable_all / total_all * 100,
        # extract_method_years.py `_renewable_share_pct`: real generators only.
        "bulk_grid_renewable_pct": renewable_real / total_real * 100,
        # Colleague's convention. Grid source generation: rooftop PV is outside
        # the topology (OPSO demand), battery discharge and pumped-hydro output
        # are StorageUnit components and never in generators_t.p, so on this
        # network r_total is renewable real generation over real generation.
        "r_total_pct": renewable_real / total_real * 100,
        "r_vre_pct": vre_real / total_real * 100,
        "generation_real_twh": total_real / 1e6,
        "generation_all_twh": total_all / 1e6,
        "slack_generator_mwh": slack_mwh,
        "unserved_mwh": float(energy[gens["carrier"] == "Unserved Energy"].sum()),
    }


def _emissions(run_root: Path, network: pypsa.Network, energy: pd.Series) -> dict:
    """Residual-CO2e emissions on exactly the coefficients the map's cap will use."""
    pf = pd.read_csv(run_root / "pypsa_friendly" / "generators.csv").set_index("name")
    resid = pd.to_numeric(
        pf["isp_residual_co2_t_per_mwh"], errors="coerce"
    ).fillna(0.0)
    captured = pd.to_numeric(
        pf["isp_captured_co2_t_per_mwh"], errors="coerce"
    ).fillna(0.0)
    resid_t = float((energy * resid.reindex(energy.index).fillna(0.0)).sum())
    captured_t = float((energy * captured.reindex(energy.index).fillna(0.0)).sum())
    return {"residual_co2e_t": resid_t, "captured_co2_t": captured_t}


def _gas_split(run_root: Path, network: pypsa.Network, energy: pd.Series) -> dict:
    """Abated vs unabated gas, by isp_technology_type joined from pypsa_friendly."""
    pf = pd.read_csv(run_root / "pypsa_friendly" / "generators.csv").set_index("name")
    tech = pf["isp_technology_type"].reindex(network.generators.index)
    gas = network.generators["carrier"] == "Gas"
    abated = gas & (tech == "CCGT with CCS")
    unabated = gas & (tech != "CCGT with CCS")
    p_nom = network.generators["p_nom_opt"]
    return {
        "gas_abated_twh": float(energy[abated[energy.index]].sum()) / 1e6,
        "gas_unabated_twh": float(energy[unabated[energy.index]].sum()) / 1e6,
        "gas_abated_gw": float(p_nom[abated].sum()) / 1e3,
        "gas_unabated_gw": float(p_nom[unabated].sum()) / 1e3,
    }


def _repair_checks() -> None:
    print("=== Repairs, functionally re-confirmed in this working state ===")

    from ispypsa.templater.helpers import _strip_all_text_after_numeric_value

    vectors = pd.Series(["1660", "2131000", "1,660 some note", "550 MW"])
    stripped = _strip_all_text_after_numeric_value(vectors)
    print(f"regex 7f12fd4: {vectors.tolist()} -> {stripped.tolist()}")
    assert stripped.tolist() == ["1660", "2131000", "1,660", "550"], "regex REGRESSED"

    root = _run_root(2050)
    network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")

    water = network.storage_units[network.storage_units["carrier"] == "Water"]
    durations = sorted(water["max_hours"].round(0).unique())
    built_phes_gw = water.loc[water["p_nom_opt"] > 1.0, "p_nom_opt"].sum() / 1e3
    print(
        f"PHES 7d4acbe: {len(water)} Water storage rows, durations (h) {durations}, "
        f"built {built_phes_gw:.3f} GW"
    )
    assert len(durations) > 3, "PHES menu MISSING (storage repair regressed)"

    pf = pd.read_csv(root / "pypsa_friendly" / "generators.csv").set_index("name")
    tech = pf["isp_technology_type"].reindex(network.generators.index).fillna("")
    offshore = tech.str.contains("offshore")
    offshore_gw = network.generators.loc[offshore, "p_nom_opt"].sum() / 1e3
    print(f"offshore 36ab6c6: built {offshore_gw:.3f} GW across {int(offshore.sum())} rows")
    assert offshore_gw > 0.5, "offshore wind pinned near zero (repair regressed)"

    ecaa = pd.read_csv(root / "ispypsa_inputs" / "ecaa_generators.csv")
    fom_nan = int(ecaa["fom_$/kw/annum"].isna().sum())
    print(f"ECAA FOM 78267c3: {fom_nan} of {len(ecaa)} FOM values NaN")
    assert fom_nan == 0, "ECAA FOM NaN (repair regressed)"
    print()


def main() -> None:
    _repair_checks()

    rows = []
    for year in YEARS:
        root = _run_root(year)
        network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")
        energy = _annual_mwh_per_generator(network)
        delivered_mwh = _delivered_mwh(network)

        row = {"year": year, "delivered_twh": delivered_mwh / 1e6}
        row.update(_share_definitions(network, energy))
        row.update(_emissions(root, network, energy))
        row.update(_gas_split(root, network, energy))

        row["iota_delivered_t_per_mwh"] = row["residual_co2e_t"] / delivered_mwh
        row["iota_generated_t_per_mwh"] = (
            row["residual_co2e_t"] / (row["generation_real_twh"] * 1e6)
        )
        row["anchor_quantity_twh"] = ANCHOR_QUANTITY_TWH[year]
        row["anchor_renewable_share_pct"] = ANCHOR_RENEWABLE_SHARE[year] * 100
        row["quantity_gap_twh"] = row["generation_real_twh"] - row["anchor_quantity_twh"]
        row["quantity_gap_pct"] = row["quantity_gap_twh"] / row["anchor_quantity_twh"] * 100
        row["share_gap_pp"] = row["r_total_pct"] - row["anchor_renewable_share_pct"]
        rows.append(row)

    frame = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "stage0_conditioning.csv", index=False)

    cols = [
        "year", "delivered_twh", "generation_real_twh",
        "anchor_quantity_twh", "quantity_gap_pct",
        "r_total_pct", "r_vre_pct", "anchor_renewable_share_pct", "share_gap_pp",
        "prev_renewable_fraction_pct", "bulk_grid_renewable_pct",
        "iota_delivered_t_per_mwh", "iota_generated_t_per_mwh",
        "gas_abated_twh", "gas_unabated_twh", "gas_abated_gw", "gas_unabated_gw",
        "slack_generator_mwh", "unserved_mwh",
    ]
    print("=== Conditioning state (sweep_c0_d100 chain) vs pathway anchors ===")
    print(frame[cols].to_string(index=False))
    print("\nwrote", OUT / "stage0_conditioning.csv")


if __name__ == "__main__":
    main()
