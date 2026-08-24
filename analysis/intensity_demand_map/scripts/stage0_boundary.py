"""Stage 0.2 boundary reconciliation for the intensity x demand map.

The parsed traces the model serves are Step Change / POE50 / OPSO_MODELLING
(grid-served operational demand, sent-out basis): 251.925 TWh FY2050. The
colleague's pathway anchor is ~330.77 TWh FY2050 on a "NEM source generation"
boundary. This script decomposes the gap from AEMO's own raw 2026 ISP Final
trace set, which carries three demand-side series per sub-region:

  OPSO_MODELLING         operational sent-out demand, distributed PV netted out
                         (what ISPyPSA serves with grid generation)
  OPSO_MODELLING_PVLITE  operational sent-out under the PV-lite counterfactual
                         (reported as a diagnostic only)
  PV_TOT                 total distributed PV generation (self-consumed +
                         exported), the component OPSO nets out

Reconciliation reported per milestone year:

  anchor  =  OPSO  +  PV_TOT  +  residual

with the residual explicitly quantified — candidate content: generator auxiliary
load (source generation vs sent-out), storage recycle if the anchor counts gross
generation, and any bridge error in the colleague's beta = 1.3 national-to-NEM
factor. Whatever cannot be decomposed from data on disk stays in the residual.

Usage:
    uv run python analysis/intensity_demand_map/scripts/stage0_boundary.py
"""

from pathlib import Path

import pandas as pd

RAW = Path("iasr inputs/2026 ISP Final")
SUBREGIONS = [
    "CNSW", "CQ", "CSA", "GG", "MEL", "NNSW", "NQ", "NSA",
    "SESA", "SEV", "SNSW", "SNW", "SQ", "TAS", "WNV",
]
SCENARIO = "Step Change"
TAG = "STEP_CHANGE"
REF_YEAR = 2018
HALF_HOUR_COLS = [f"{i:02d}" for i in range(1, 49)]
YEARS = [2030, 2040, 2050]

ANCHOR_QUANTITY_TWH = {2030: 211.54, 2040: 292.31, 2050: 330.77}

OUT = Path("analysis/intensity_demand_map")


def _folder(subregion: str) -> Path:
    return (
        RAW
        / f"ISP Demand Traces {subregion} {SCENARIO}"
        / f"demand_{subregion}_{SCENARIO}"
    )


def _trace_paths(subregion: str, series: str) -> list[Path]:
    """All POE50/RefYear-2018 files for one series in one sub-region.

    PV_TOT ships both per-area files (`*_Area1_*`) and, in some sub-regions, an
    additional no-area file. To avoid double counting, prefer the area files
    when they exist and fall back to the no-area file otherwise; the choice is
    validated in main() by printing both bases for one sub-region.
    """
    folder = _folder(subregion)
    pattern = f"*_{subregion}_*RefYear_{REF_YEAR}_{TAG}_POE50_{series}.csv"
    matches = sorted(folder.glob(pattern))
    area = [p for p in matches if "_Area" in p.name]
    no_area = [p for p in matches if "_Area" not in p.name]
    if series == "PV_TOT" and area:
        return area
    assert no_area, f"{subregion}/{series}: nothing matched {pattern}"
    return no_area


def _financial_year_energy_twh(path: Path) -> pd.Series:
    df = pd.read_csv(path)
    fy = df["Year"] + (df["Month"] > 6).astype(int)
    mwh = df[HALF_HOUR_COLS].sum(axis=1) * 0.5
    return mwh.groupby(fy).sum() / 1e6


def _nem_series(series: str) -> pd.Series:
    parts = []
    for subregion in SUBREGIONS:
        for path in _trace_paths(subregion, series):
            parts.append(_financial_year_energy_twh(path))
    return pd.concat(parts, axis=1).sum(axis=1)


def main() -> None:
    # Validate the area-vs-no-area PV_TOT choice on one sub-region.
    folder = _folder("CNSW")
    area = sorted(folder.glob(f"*_CNSW_Area*_RefYear_{REF_YEAR}_{TAG}_POE50_PV_TOT.csv"))
    no_area = sorted(
        p for p in folder.glob(f"*_CNSW_RefYear_{REF_YEAR}_{TAG}_POE50_PV_TOT.csv")
    )
    area_twh = sum(_financial_year_energy_twh(p).loc[2050] for p in area) if area else None
    no_area_twh = (
        _financial_year_energy_twh(no_area[0]).loc[2050] if no_area else None
    )
    print(
        f"PV_TOT basis check (CNSW FY2050): {len(area)} area files = {area_twh}, "
        f"no-area file = {no_area_twh}"
    )

    opso = _nem_series("OPSO_MODELLING")
    pvlite = _nem_series("OPSO_MODELLING_PVLITE")
    pv_tot = _nem_series("PV_TOT")

    rows = []
    for year in YEARS:
        anchor = ANCHOR_QUANTITY_TWH[year]
        opso_y, pv_y = float(opso.loc[year]), float(pv_tot.loc[year])
        residual = anchor - opso_y - pv_y
        rows.append(
            {
                "year": year,
                "anchor_source_generation_twh": anchor,
                "opso_modelling_twh": opso_y,
                "pv_tot_twh": pv_y,
                "opso_plus_pv_twh": opso_y + pv_y,
                "residual_twh": residual,
                "residual_pct_of_anchor": residual / anchor * 100,
                "diag_opso_pvlite_twh": float(pvlite.loc[year]),
            }
        )
    frame = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "stage0_boundary.csv", index=False)
    print("\n=== Boundary reconciliation: anchor = OPSO + PV_TOT + residual ===")
    print(frame.round(3).to_string(index=False))
    print("\nwrote", OUT / "stage0_boundary.csv")


if __name__ == "__main__":
    main()
