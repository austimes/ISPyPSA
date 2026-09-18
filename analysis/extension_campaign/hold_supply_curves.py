"""Extend a fuel supply curve CSV to later investment periods by holding its last year.

The gas and biomass supply curves (tranche, financial_year, cap_pj, adder_$/gj) end at
FY2055, but the extension campaign solves a 2060 milestone. The campaign brief holds every
trajectory-valued input at its last published year beyond the data, so the held copy
repeats the final year's tranche rows for each requested later year. The output is an
authored extension and is written beside the campaign scripts so the provenance is visible.

Usage:
    uv run isp hold-curves \\
        --curve analysis/gas_market/gas_supply_curve_central.csv \\
        --out analysis/extension_campaign/gas_supply_curve_central_held_to_2060.csv \\
        --years 2060
"""

import logging
from pathlib import Path

import pandas as pd


def hold_curve_to_years(curve: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Append the last published year's rows relabelled to each missing later year.

    Years already present in the curve are left untouched, so the held copy is
    identical to the source over the published span.
    """
    last_year = int(curve["financial_year"].max())
    missing = sorted(year for year in years if year > last_year)
    held_rows = [
        curve[curve["financial_year"] == last_year].assign(financial_year=year)
        for year in missing
    ]
    if missing:
        logging.warning(
            f"Supply curve held at FY{last_year} for investment periods beyond the "
            f"published data: {missing}"
        )
    return pd.concat([curve, *held_rows], ignore_index=True)


def main(curve: Path, out: Path, years: list[int]) -> None:
    """Write a held copy of a supply curve CSV covering the requested later years.

    :param curve: Source curve CSV.
    :param out: Held copy to write.
    :param years: Years the copy must cover.
    """
    held = hold_curve_to_years(pd.read_csv(curve), years)
    held.to_csv(out, index=False, lineterminator="\n")
    print(f"wrote {out} ({len(held)} rows, to FY{held['financial_year'].max()})")
