"""Fixtures for the campaign tooling tests, kept self-contained so ``analysis/`` and its tests can
move to another repository together."""

import io

import pandas as pd
import pytest


@pytest.fixture
def csv_str_to_df():
    """Build a DataFrame from an indented CSV string; ``__`` stands for a literal space."""

    def func(csv_str, **kwargs):
        csv_str = csv_str.replace("__", " ")
        return pd.read_csv(
            io.StringIO(csv_str), sep=r"\s*,\s*", engine="python", **kwargs
        )

    return func
