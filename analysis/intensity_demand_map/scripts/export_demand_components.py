"""Demand-component export for the ShARP boundary conversion.

Two tables, covering everything derivable from data on disk:

  demand_components_traces.csv   per (year, sub-region): annual OPSO_MODELLING
                                 and PV_TOT energy (Step Change, POE50,
                                 RefYear 2018) from AEMO's raw 2026 ISP Final
                                 traces, plus NEM totals. The model's load is
                                 OPSO x the cell's demand scalar, exactly.
  demand_components_balance.csv  per Dataset B cell-year, measured from the
                                 solved network: generation, served load,
                                 storage charge/discharge and round-trip loss,
                                 and the balance residual.

What is NOT here, verified rather than assumed:

- Transmission/interconnector losses INSIDE the model are zero by
  construction: the networks carry links only (no lines), all at
  efficiency 1.0. generation - load = storage round-trip loss to numerical
  tolerance. There is no in-model loss component to convert.
- Whatever losses AEMO removes upstream of OPSO_MODELLING (to the
  connection-point boundary) are embedded in the trace construction and are
  not recoverable from this dataset.
- The raw 2026 ISP Final demand-trace set carries exactly three series per
  sub-region (OPSO_MODELLING, OPSO_MODELLING_PVLITE, PV_TOT). PV_TOT is TOTAL
  distributed PV; the rooftop vs other-embedded (PVNSG) split does not exist
  in this data and must come from AEMO's demand-component forecasts (ESOO /
  forecasting portal), as must distribution loss factors for a
  customer-delivered quantity.

Usage:
    uv run python analysis/intensity_demand_map/scripts/export_demand_components.py
"""

from pathlib import Path

import pandas as pd
import pypsa

RAW = Path("iasr inputs/2026 ISP Final")
RUNS = Path("analysis/benchmarks/runs_myopic")
OUT = Path("analysis/intensity_demand_map")
SUBREGIONS = ["CNSW", "CQ", "CSA", "GG", "MEL", "NNSW", "NQ", "NSA",
              "SESA", "SEV", "SNSW", "SNW", "SQ", "TAS", "WNV"]
SCENARIO, TAG, REF_YEAR = "Step Change", "STEP_CHANGE", 2018
HALF_HOUR_COLS = [f"{i:02d}" for i in range(1, 49)]
YEARS = [2030, 2040, 2050]
CARBON_PRICES = [0, 150, 300, 550]
DEMAND_LEVELS = {"d087": 0.869546, "d100": 1.0, "d110": 1.1, "d123": 1.234752}


def _fy_energy_twh(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    fy = df["Year"] + (df["Month"] > 6).astype(int)
    return (df[HALF_HOUR_COLS].sum(axis=1) * 0.5).groupby(fy).sum() / 1e6


def _series_paths(subregion: str, series: str) -> list[Path]:
    folder = RAW / f"ISP Demand Traces {subregion} {SCENARIO}" / f"demand_{subregion}_{SCENARIO}"
    matches = sorted(folder.glob(
        f"*_{subregion}_*RefYear_{REF_YEAR}_{TAG}_POE50_{series}.csv"))
    area = [p for p in matches if "_Area" in p.name]
    if series == "PV_TOT" and area:
        return area
    return [p for p in matches if "_Area" not in p.name]


def trace_components() -> pd.DataFrame:
    rows = []
    for subregion in SUBREGIONS:
        opso = sum(_fy_energy_twh(p) for p in _series_paths(subregion, "OPSO_MODELLING"))
        pv = sum(_fy_energy_twh(p) for p in _series_paths(subregion, "PV_TOT"))
        for year in YEARS:
            rows.append({"year": year, "sub_region": subregion,
                         "opso_twh": float(opso.loc[year]),
                         "pv_tot_twh": float(pv.loc[year])})
    frame = pd.DataFrame(rows)
    nem = frame.groupby("year", as_index=False)[["opso_twh", "pv_tot_twh"]].sum()
    nem["sub_region"] = "NEM"
    return pd.concat([frame, nem], ignore_index=True)


def cell_balance(cell: str, year: int) -> dict:
    root = RUNS / f"{cell}_{year}__cost_optimal"
    network = pypsa.Network(root / "outputs" / "capacity_expansion.nc")
    weights = network.snapshot_weightings["generators"]
    generation = float(
        network.generators_t.p.clip(lower=0).mul(weights, axis=0).sum().sum())
    load = float(network.loads_t.p_set.sum(axis=1).mul(weights).sum())
    storage = network.storage_units_t.p
    charge = float((-storage.clip(upper=0)).mul(weights, axis=0).sum().sum())
    discharge = float(storage.clip(lower=0).mul(weights, axis=0).sum().sum())
    return {
        "cell": cell, "year": year,
        "generation_twh": generation / 1e6,
        "served_load_twh": load / 1e6,
        "storage_charge_twh": charge / 1e6,
        "storage_discharge_twh": discharge / 1e6,
        "storage_roundtrip_loss_twh": (charge - discharge) / 1e6,
        # links all at efficiency 1.0, no lines — verified in the script header
        "transmission_loss_twh": 0.0,
        "balance_residual_twh": (generation - load - (charge - discharge)) / 1e6,
    }


def main() -> None:
    traces = trace_components()
    traces.to_csv(OUT / "demand_components_traces.csv", index=False)
    print(traces[traces.sub_region == "NEM"].round(3).to_string(index=False))

    rows = []
    for price in CARBON_PRICES:
        for level in DEMAND_LEVELS:
            for year in YEARS:
                rows.append(cell_balance(f"sweep_c{price}_{level}", year))
                print(f"  {rows[-1]['cell']}_{year}: gen {rows[-1]['generation_twh']:.2f}"
                      f" load {rows[-1]['served_load_twh']:.2f}"
                      f" storloss {rows[-1]['storage_roundtrip_loss_twh']:.2f}")
    balance = pd.DataFrame(rows)
    balance.to_csv(OUT / "demand_components_balance.csv", index=False)
    print(f"\nwrote demand_components_traces.csv ({len(traces)} rows) and "
          f"demand_components_balance.csv ({len(balance)} rows)")
    print(f"max |balance residual|: {balance.balance_residual_twh.abs().max():.4f} TWh")


if __name__ == "__main__":
    main()
