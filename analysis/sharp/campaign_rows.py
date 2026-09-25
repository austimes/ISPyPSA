"""Tell a campaign's base-chain rows from its increment-grid branch rows, without loading PyPSA."""

import pandas as pd

#: Increment-grid columns of ``chains_index.csv``, carried onto the frontier and manifest frames.
#: A campaign without an increment grid has none of them, and every row of it is a base row.
BRANCH_COLUMNS = ["base_cell", "branch_year", "demand_level", "intensity_level"]


def base_rows(results: pd.DataFrame) -> pd.DataFrame:
    """The campaign's base chains. A run with no increment grid is all base rows."""
    if "base_cell" not in results:
        return results
    return results[results["base_cell"].isna()]
