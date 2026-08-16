"""Builds the CO2 transport-and-storage supply curve CSVs for CCS-gas.

Emits three CSVs in this directory (full derivation and citations in
CCS_SUPPLY_CURVE.md):

- ccs_sink_tranches_conservative.csv : one row per sink per financial year,
  every cap 0. The production default. No NEM-reachable power-sector injection
  is operating or sanctioned through 2050, so captured tonnes are constrained
  to zero.
- ccs_sink_tranches_optimistic.csv : the same shape at the optimistic upper
  edge, i.e. every live proposal realised at its proponent's stated nameplate
  and schedule, with a 50% power-available share.
- ccs_transport_adders.csv : one row per ISP sub-region, giving the nearest
  *permitted* sink, the pipeline distance and the resulting per-tonne transport
  cost. This file carries both the price adder and the bus-to-sink assignment.

Cost basis, real ~2025 AUD, from GHD (2025) for AEMO s3.11 via CCS_TNS_SOURCING.md:
storage A$18.5/tCO2 (range 12-25, onshore depleted gas reservoir), transport
A$0.1096/tCO2/km (onshore pipeline).

Quantity basis from CCS_CAP_AND_DECISION.md §2.2/§2.4. Sinks in the Queensland
Great Artesian Basin (Surat, Denison, Bowen) are excluded outright: greenhouse-gas
storage there is prohibited by the Mineral and Energy Resources and Other
Legislation Amendment Act 2024 (Qld), assented 18 June 2024. The Darling Basin
(no published injection rate, no proponent), the Sydney Basin (ruled out by the
NSW CO2 Storage Assessment Program), the Bass Basin (acreage only) and Arckaringa
(no published nameplate) are excluded for want of a number rather than by law.
ExxonMobil's SEA CCS (Bream, Gippsland) is excluded because it was withdrawn in
March 2025; the decision memo carried it in its optimistic case with a flag, so
this curve's 2050 optimistic total is 13.1 Mt/yr rather than the memo's 14.1.
"""

from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import pandas as pd

FIRST_FY = 2025
LAST_FY = 2055

# GHD (2025) for AEMO, s3.11 CCGT table p.95. Real 2025 AUD, AACE Class 5
# (-50%/+100%). Onshore pipeline; injection into a depleted natural gas reservoir.
STORAGE_AUD_PER_T = 18.5
TRANSPORT_AUD_PER_T_KM = 0.1096

# Great-circle distance is a floor on pipeline length. Real CO2 trunklines follow
# terrain, tenure and existing corridors. 1.25 sits inside the 1.2-1.3 band the
# brief allows and is applied uniformly to every pair, so no route is flattered
# relative to another. Declared, not sourced: no route study exists for any of
# these pairs.
ROUTING_FACTOR = 1.25

# Approximate WGS84 positions of the ISP sub-region reference nodes named in
# sub_regions.csv, to ~0.05 deg. Public substation locations. These set pipeline
# *distance* only; they are not used for anything else.
REFERENCE_NODES = {
    "NQ": ("Ross", -19.33, 146.75),
    "CQ": ("Broadsound", -22.15, 148.85),
    "GG": ("Calliope River", -23.88, 151.14),
    "SQ": ("South Pine", -27.33, 152.98),
    "NNSW": ("Armidale", -30.51, 151.67),
    "CNSW": ("Wellington", -32.55, 148.94),
    "SNSW": ("Canberra", -35.31, 149.20),
    "SNW": ("Sydney West", -33.80, 150.87),
    "WNV": ("Moorabool", -37.86, 144.22),
    "SEV": ("Hazelwood", -38.27, 146.39),
    "MEL": ("Thomastown", -37.68, 145.01),
    "NSA": ("Davenport", -32.50, 137.78),
    "CSA": ("Torrens Island", -34.81, 138.54),
    "SESA": ("South East", -37.72, 140.80),
    "TAS": ("George Town", -41.11, 146.83),
}

# Injection areas of the three sinks that are neither prohibited nor without a
# published rate. Positions to ~0.05 deg.
SINKS = {
    "cooper_hub": ("Cooper Basin, Moomba SA", -28.10, 140.20),
    "carbonnet": ("Gippsland, Pelican offshore VIC", -38.40, 147.10),
    "otway_hub": ("Otway Basin, onshore VIC", -38.55, 143.00),
}

# (sink, {fy: physical Mt/yr anchor}) before the power-available haircut.
# Cooper hub: Santos/JX/ENEOS partner pathway 5 (2030) / 10 (2035) / 20 (2040).
#   Moomba Phase 1's demonstrated ~1.3 Mt/yr is *not* included: it is fully
#   committed to Santos's own Cooper raw-gas CO2 and earns ACCUs on that basis.
# CarbonNet: Pelican "up to 6 Mt/yr", proponent states operational late 2030s,
#   so 2040 is the first milestone year consistent with its own schedule.
# Otway hub: Beach Energy pre-feasibility ~0.2 Mt/yr, timing undeclared, placed
#   at 2030 as the earliest milestone.
OPTIMISTIC_PHYSICAL_MT = {
    "cooper_hub": {2025: 0.0, 2029: 0.0, 2030: 5.0, 2035: 10.0, 2040: 20.0},
    "carbonnet": {2025: 0.0, 2039: 0.0, 2040: 6.0},
    "otway_hub": {2025: 0.0, 2029: 0.0, 2030: 0.2},
}

# Share of physical injection available to NEM power generation. The decision
# memo carries 0-50%; the optimistic variant takes the upper edge. The haircut is
# load-bearing: the Cooper hub pathway is explicitly for imported Japanese CO2 in
# Santos's own documents, CarbonNet's intended anchor customers are Latrobe
# industry and hydrogen, and reservoir CO2 is far cheaper to capture than CCGT
# flue gas, so power is the marginal claimant on any shared hub.
POWER_AVAILABLE_SHARE = 0.50

_EARTH_RADIUS_KM = 6371.0


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine great-circle distance in km between two WGS84 points."""
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * asin(sqrt(a))


def _nearest_sink(lat: float, lon: float) -> tuple[str, float]:
    """The permitted sink closest to a reference node, and the routed distance."""
    distances = {
        sink: _great_circle_km(lat, lon, sink_lat, sink_lon) * ROUTING_FACTOR
        for sink, (_, sink_lat, sink_lon) in SINKS.items()
    }
    nearest = min(distances, key=distances.get)
    return nearest, distances[nearest]


def build_transport_adders() -> pd.DataFrame:
    """One row per sub-region: its nearest permitted sink and the transport cost."""
    rows = []
    for sub_region, (node, lat, lon) in REFERENCE_NODES.items():
        sink, distance_km = _nearest_sink(lat, lon)
        rows.append(
            {
                "isp_sub_region_id": sub_region,
                "reference_node": node,
                "sink": sink,
                "distance_km": round(distance_km, -1),
                "transport_$/t": round(round(distance_km, -1) * TRANSPORT_AUD_PER_T_KM, 2),
            }
        )
    return pd.DataFrame(rows).sort_values("isp_sub_region_id").reset_index(drop=True)


def _interpolate_caps(anchors: dict[int, float]) -> pd.Series:
    """Linear interpolation between proponent anchors, held flat after the last."""
    years = pd.Index(range(FIRST_FY, LAST_FY + 1), name="financial_year")
    return pd.Series(anchors, index=years).interpolate(method="index").ffill()


def build_sink_tranches(power_available_share: float) -> pd.DataFrame:
    """One row per sink per financial year, in kt/yr of injection available to power."""
    rows = []
    for sink, anchors in OPTIMISTIC_PHYSICAL_MT.items():
        caps = _interpolate_caps(anchors)
        for financial_year, cap_mt in caps.items():
            rows.append(
                {
                    "sink": sink,
                    "financial_year": financial_year,
                    "cap_kt": round(cap_mt * power_available_share * 1000.0, 1),
                    "storage_$/t": STORAGE_AUD_PER_T,
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["financial_year", "sink"])
        .reset_index(drop=True)
    )


if __name__ == "__main__":
    here = Path(__file__).parent

    adders = build_transport_adders()
    adders.to_csv(here / "ccs_transport_adders.csv", index=False)
    print(f"Wrote {len(adders)} transport adder rows")
    print(adders.to_string(index=False))

    optimistic = build_sink_tranches(POWER_AVAILABLE_SHARE)
    optimistic.to_csv(here / "ccs_sink_tranches_optimistic.csv", index=False)

    conservative = build_sink_tranches(0.0)
    conservative.to_csv(here / "ccs_sink_tranches_conservative.csv", index=False)
    print(f"\nWrote {len(optimistic)} tranche rows per variant")

    milestones = [2030, 2035, 2040, 2045, 2050]
    pivot = (
        optimistic[optimistic["financial_year"].isin(milestones)]
        .pivot(index="financial_year", columns="sink", values="cap_kt")
        .assign(total_kt=lambda df: df.sum(axis=1))
    )
    print("\nOptimistic power-available injection, kt/yr:")
    print(pivot.to_string())
