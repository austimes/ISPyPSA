import logging

import numpy as np
import pandas as pd


def scale_sampled_vre_trace(
    name: str,
    trace: pd.DataFrame,
    snapshots: pd.DataFrame,
    full_year_snapshots: pd.DataFrame,
) -> pd.DataFrame:
    """Scale a VRE trace at the sampled snapshots so each investment period keeps its full-year capacity factor.

    Follows the AEMO ISP Methodology (June 2025, p. 41): the snapshot-weighted mean of
    the sampled `p_max_pu` in each investment period is matched to the mean of the same
    trace over every snapshot of that period, with availability capped at 1.

    Args:
        name: Generator name, used in the log message when the cap stops the target being met.
        trace: Full trace with columns "snapshots" and "p_max_pu" (other columns are kept).
        snapshots: Sampled snapshots with columns "snapshots", "investment_periods" and
            "generators" (the generator snapshot weighting).
        full_year_snapshots: Unsampled snapshots with columns "snapshots" and "investment_periods".

    Returns:
        pd.DataFrame with the trace's columns, holding only the sampled snapshots, with
        `p_max_pu` scaled.
    """
    targets = _full_year_mean_by_period(trace, full_year_snapshots)
    sampled = pd.merge(
        trace,
        snapshots.loc[:, ["snapshots", "investment_periods", "generators"]],
        on="snapshots",
    )
    sampled["p_max_pu"] = pd.concat(
        _scale_to_weighted_mean(
            period["p_max_pu"], period["generators"], targets[investment_period]
        )
        for investment_period, period in sampled.groupby("investment_periods")
    )
    _log_unmet_targets(name, sampled, targets)
    return sampled.loc[:, trace.columns]


def _full_year_mean_by_period(
    trace: pd.DataFrame, full_year_snapshots: pd.DataFrame
) -> pd.Series:
    """Mean `p_max_pu` of the trace over all snapshots in each investment period."""
    full_year = pd.merge(trace, full_year_snapshots, on="snapshots")
    return full_year.groupby("investment_periods")["p_max_pu"].mean()


def _scale_to_weighted_mean(
    values: pd.Series, weights: pd.Series, target: float, max_iterations: int = 20
) -> pd.Series:
    """Scale values so their weighted mean equals target, capping at 1 and spreading the capped-off energy over
    uncapped values in proportion to their size. An all-zero series is returned unchanged.
    """
    mean = np.average(values, weights=weights)
    if mean == 0:
        return values
    scaled = (values * target / mean).clip(upper=1)
    for _ in range(max_iterations):
        shortfall = target - np.average(scaled, weights=weights)
        uncapped_mean = np.average(scaled.where(scaled < 1, 0), weights=weights)
        if np.isclose(shortfall, 0) or uncapped_mean == 0:
            break
        scaled = (scaled * (1 + shortfall / uncapped_mean)).clip(upper=1)
    return scaled


def _log_unmet_targets(name: str, sampled: pd.DataFrame, targets: pd.Series) -> None:
    """Log the investment periods where the availability cap stopped the sampled mean reaching its target."""
    means = sampled.groupby("investment_periods")[["p_max_pu", "generators"]].apply(
        lambda period: np.average(period["p_max_pu"], weights=period["generators"])
    )
    unmet = means.index[~np.isclose(means, targets[means.index])]
    if len(unmet) > 0:
        logging.info(
            f"Sampled availability of {name} is capped at 1 and stays below its full-year mean "
            f"in investment periods: {sorted(unmet.tolist())}"
        )
