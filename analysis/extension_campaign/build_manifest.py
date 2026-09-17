"""Build the Slurm manifest for the demand x carbon-pressure extension campaign.

The campaign is a grid of recursive-dynamic chains, one chain per (demand
trajectory, pressure setting). Every chain is solved by
``analysis/benchmarks/run_myopic.py`` over the milestones 2030/2040/2050/2060,
and differs from its neighbours only in the pressure flag this script writes:
either ``--carbon-price N`` or ``--co2-cap-t-schedule YEAR:TONNES ...``.

The pressure ladder is fixed campaign data, declared at module level:

* Every trajectory gets the uncapped A$0 chain (``c0``), the incumbent family.
* Every trajectory gets the six cap schedules, named by their 2050 target
  intensity on the customer-delivered basis: 0.02 / 0.01 / 0.005 / 0.002 /
  0.001 / 0.0005 t CO2e per MWh. Each schedule holds 2030 at 0.12 t/MWh, sets
  2040 to the geometric mean of 0.12 and the target, and holds 2060 at the
  target -- except the deepest schedule, whose 2060 rung tightens to 0.0001
  t/MWh on the SOURCE basis.
* Only ``iasr_central`` and ``iasr_stress`` get the price calibration chains
  ``c150``/``c300``/``c550``, which bracket the cap duals.

Caps are always written into the solver as absolute annual tonnes:
``cap_t = delivery_fraction x intensity_delivered x Q_source_TWh x 1e6``, where
``Q_source`` is the trajectory's source NEM load for that year. A rung already
quoted on the source basis skips the delivery factor. Every manifest row
records its basis so no cap is ever quoted without one.

Naming:

* Run ids are ``ext_<trajectory without the "iasr_" prefix>_<chain key>``, e.g.
  ``ext_central_c0``, ``ext_central_c150``, ``ext_stress_cap0005``.
* A cap schedule's key is ``cap`` plus the 2050 target written as a decimal
  with the point removed: 0.02 -> ``cap002``, 0.005 -> ``cap0005``, 0.0005 ->
  ``cap00005``. The retained leading zero keeps every key the same shape, so
  the six read as one family in run ids, log names and Slurm job listings.

Outputs under ``--out`` (default ``outputs/campaign``):

* ``caps.csv`` -- one row per (trajectory, cap schedule, milestone year) with
  the intensity, its basis, the source load and the absolute tonnage.
* ``chains.tsv`` -- headerless ``run_id<TAB>trajectory<TAB>args``, one line per
  chain. The line number is the Slurm array index, so the order is part of the
  contract: the uncapped chains first, then the price calibration chains, then
  the cap chains shallow to deep with the trajectories grouped inside each
  schedule.
* ``chains_index.csv`` -- the same chains with their array row, chain key and
  campaign stage (``2a`` for price chains, ``2b`` for cap chains), for picking
  array ranges by hand.

Usage:
    uv run python analysis/extension_campaign/build_manifest.py
"""

import argparse
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DEFAULT_PLAN = Path("analysis/extension_campaign/next-sweep-demand-plan.json")
DEFAULT_OUT = Path("outputs/campaign")

DELIVERED_BASIS = "delivered"
SOURCE_BASIS = "source"

PRICE_STAGE = "2a"
CAP_STAGE = "2b"

CAP_ANCHOR_2030 = 0.12

CAPS_COLUMNS = [
    "run_id",
    "trajectory",
    "cap_key",
    "target_2050_t_per_mwh_delivered",
    "year",
    "intensity",
    "intensity_basis",
    "source_twh",
    "cap_t",
    "plan_version",
    "git_commit",
]

CHAINS_COLUMNS = ["row", "run_id", "trajectory", "chain", "stage", "args"]


@dataclass(frozen=True)
class Rung:
    """One milestone's cap intensity in t CO2e/MWh, with the basis it is quoted on."""

    intensity: float
    basis: str


@dataclass(frozen=True)
class CapSchedule:
    """One rung of the pressure ladder, named by its 2050 target intensity.

    ``rung_2060`` overrides the default "hold the 2050 target through 2060"
    behaviour; only the deepest schedule carries one.
    """

    key: str
    target_2050: float
    rung_2060: Rung | None = None


@dataclass(frozen=True)
class PriceChain:
    """A carbon-price chain, priced at a constant A$/t along the whole chain."""

    key: str
    carbon_price: int


CAP_LADDER = (
    CapSchedule("cap002", 0.02),
    CapSchedule("cap001", 0.01),
    CapSchedule("cap0005", 0.005),
    CapSchedule("cap0002", 0.002),
    CapSchedule("cap0001", 0.001),
    CapSchedule("cap00005", 0.0005, rung_2060=Rung(0.0001, SOURCE_BASIS)),
)

UNCAPPED_CHAIN = PriceChain("c0", 0)

PRICE_CALIBRATION_CHAINS = (
    PriceChain("c150", 150),
    PriceChain("c300", 300),
    PriceChain("c550", 550),
)

PRICE_CALIBRATION_TRAJECTORIES = ("iasr_central", "iasr_stress")


def _read_git_commit() -> str:
    """Short commit of the working tree, or ``unknown`` when git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def _run_id(trajectory: str, chain_key: str) -> str:
    """Campaign run id, e.g. ``iasr_stress`` + ``cap0005`` -> ``ext_stress_cap0005``."""
    return f"ext_{trajectory.removeprefix('iasr_')}_{chain_key}"


def _cap_rungs(schedule: CapSchedule) -> dict[int, Rung]:
    """Milestone intensities for one cap schedule, in milestone order.

    2030 is held at the anchor, 2040 is the geometric mean of the anchor and the
    2050 target, and 2060 holds the target unless the schedule overrides it.
    """
    target = Rung(schedule.target_2050, DELIVERED_BASIS)
    geometric_mean = math.sqrt(CAP_ANCHOR_2030 * schedule.target_2050)
    return {
        2030: Rung(CAP_ANCHOR_2030, DELIVERED_BASIS),
        2040: Rung(geometric_mean, DELIVERED_BASIS),
        2050: target,
        2060: schedule.rung_2060 or target,
    }


def _cap_tonnes(rung: Rung, source_twh: float, delivery_fraction: float) -> int:
    """Absolute annual CO2e cap in tonnes for one rung at one year's source load.

    A delivered-basis intensity is converted to the source boundary by the
    delivery fraction; a source-basis rung is applied to the source load as-is.
    """
    delivery = delivery_fraction if rung.basis == DELIVERED_BASIS else 1.0
    return round(delivery * rung.intensity * source_twh * 1e6)


def _cap_row(
    plan: dict,
    git_commit: str,
    trajectory: str,
    schedule: CapSchedule,
    year: int,
    rung: Rung,
) -> dict:
    """Assemble one ``caps.csv`` row from a trajectory's source load for that year."""
    source_twh = plan["demand_paths_source_twh"][trajectory][str(year)]
    return {
        "run_id": _run_id(trajectory, schedule.key),
        "trajectory": trajectory,
        "cap_key": schedule.key,
        "target_2050_t_per_mwh_delivered": schedule.target_2050,
        "year": year,
        "intensity": rung.intensity,
        "intensity_basis": rung.basis,
        "source_twh": source_twh,
        "cap_t": _cap_tonnes(rung, source_twh, plan["delivery_fraction"]),
        "plan_version": plan["version"],
        "git_commit": git_commit,
    }


def build_caps_table(plan: dict, git_commit: str) -> pd.DataFrame:
    """Every cap rung of the campaign, one row per (trajectory, schedule, year)."""
    rows = [
        _cap_row(plan, git_commit, trajectory, schedule, year, rung)
        for trajectory in plan["demand_paths_source_twh"]
        for schedule in CAP_LADDER
        for year, rung in _cap_rungs(schedule).items()
    ]
    return pd.DataFrame(rows, columns=CAPS_COLUMNS)


def _price_chain_row(trajectory: str, chain: PriceChain) -> dict:
    """One price chain: a constant carbon adder held across every milestone."""
    return {
        "run_id": _run_id(trajectory, chain.key),
        "trajectory": trajectory,
        "chain": chain.key,
        "stage": PRICE_STAGE,
        "args": f"--carbon-price {chain.carbon_price}",
    }


def _uncapped_chain_rows(plan: dict) -> list[dict]:
    """The A$0 chain every trajectory gets, the uncapped incumbent family."""
    return [
        _price_chain_row(trajectory, UNCAPPED_CHAIN)
        for trajectory in plan["demand_paths_source_twh"]
    ]


def _price_calibration_rows(plan: dict) -> list[dict]:
    """The A$150/300/550 chains, run only on the central and stress trajectories."""
    return [
        _price_chain_row(trajectory, chain)
        for trajectory in PRICE_CALIBRATION_TRAJECTORIES
        for chain in PRICE_CALIBRATION_CHAINS
    ]


def _cap_chain_row(plan: dict, caps: pd.DataFrame, trajectory: str, key: str) -> dict:
    """One cap chain, whose tonnages are read back out of the caps table."""
    rungs = caps[(caps["trajectory"] == trajectory) & (caps["cap_key"] == key)]
    tonnes = dict(zip(rungs["year"], rungs["cap_t"]))
    schedule = " ".join(f"{year}:{tonnes[year]}" for year in plan["milestone_years"])
    return {
        "run_id": _run_id(trajectory, key),
        "trajectory": trajectory,
        "chain": key,
        "stage": CAP_STAGE,
        "args": f"--co2-cap-t-schedule {schedule}",
    }


def _cap_chain_rows(plan: dict, caps: pd.DataFrame) -> list[dict]:
    """Cap chains shallow to deep, with the trajectories grouped inside a schedule."""
    return [
        _cap_chain_row(plan, caps, trajectory, schedule.key)
        for schedule in CAP_LADDER
        for trajectory in plan["demand_paths_source_twh"]
    ]


def build_chain_table(plan: dict, caps: pd.DataFrame) -> pd.DataFrame:
    """Every chain of the campaign in Slurm array order, numbered from zero."""
    rows = (
        _uncapped_chain_rows(plan)
        + _price_calibration_rows(plan)
        + _cap_chain_rows(plan, caps)
    )
    chains = pd.DataFrame(rows)
    chains.insert(0, "row", range(len(chains)))
    return chains[CHAINS_COLUMNS]


def write_manifest(caps: pd.DataFrame, chains: pd.DataFrame, out_dir: Path) -> None:
    """Write the three manifest files with LF endings, as the Slurm jobs read them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    caps.to_csv(out_dir / "caps.csv", index=False, lineterminator="\n")
    chains[["run_id", "trajectory", "args"]].to_csv(
        out_dir / "chains.tsv", sep="\t", header=False, index=False, lineterminator="\n"
    )
    chains[["row", "run_id", "trajectory", "chain", "stage"]].to_csv(
        out_dir / "chains_index.csv", index=False, lineterminator="\n"
    )


def _caps_in_mt(caps: pd.DataFrame) -> pd.DataFrame:
    """Caps as Mt CO2e, one row per (trajectory, schedule) and one column per year."""
    in_mt = caps.assign(cap_mt=caps["cap_t"] / 1e6)
    return in_mt.pivot_table(
        index=["trajectory", "cap_key"], columns="year", values="cap_mt", sort=False
    ).round(3)


def _trajectories_without_tracedirs(plan: dict, tracedirs_dir: Path) -> list[str]:
    """Trajectories with no ``<trajectory>.txt``; chain.sbatch cats these at submit."""
    return sorted(
        trajectory
        for trajectory in plan["demand_paths_source_twh"]
        if not (tracedirs_dir / f"{trajectory}.txt").exists()
    )


def _print_summary(
    plan: dict, caps: pd.DataFrame, chains: pd.DataFrame, args: argparse.Namespace
) -> None:
    """Report the chain count, the cap tonnages in Mt and any missing trace dirs."""
    print(f"plan version: {plan['version']}")
    print(f"chains: {len(chains)} (array 0-{len(chains) - 1})")
    print(f"manifest written to {args.out}")
    print("\ncap schedules (Mt CO2e per year):")
    print(_caps_in_mt(caps).to_string())
    missing = _trajectories_without_tracedirs(plan, args.tracedirs_dir)
    if missing:
        print(f"\nno trace directory file in {args.tracedirs_dir} for: {missing}")


def _parse_args() -> argparse.Namespace:
    """Command line for the manifest builder."""
    ap = argparse.ArgumentParser(description="Build the extension campaign manifest.")
    ap.add_argument("--plan", type=Path, default=DEFAULT_PLAN, help="Demand plan JSON.")
    ap.add_argument(
        "--out", type=Path, default=DEFAULT_OUT, help="Manifest output directory."
    )
    ap.add_argument(
        "--tracedirs-dir",
        type=Path,
        default=None,
        help="Directory of <trajectory>.txt per-milestone trace directory tokens "
        "(default <out>/tracedirs).",
    )
    args = ap.parse_args()
    if args.tracedirs_dir is None:
        args.tracedirs_dir = args.out / "tracedirs"
    return args


def main() -> None:
    args = _parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    caps = build_caps_table(plan, _read_git_commit())
    chains = build_chain_table(plan, caps)
    write_manifest(caps, chains, args.out)
    _print_summary(plan, caps, chains, args)


if __name__ == "__main__":
    main()
