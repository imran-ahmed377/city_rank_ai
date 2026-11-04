"""Shared pytest fixtures.

Tests never touch the network or the real data/ and docs/ folders: they build
small synthetic inputs and use pytest's tmp_path for any files.
"""

from __future__ import annotations

import pandas as pd
import pytest

from city_rank.cities import CITIES_BY_SLUG
from city_rank.store import Store


@pytest.fixture
def store(tmp_path) -> Store:
    """A Store rooted in a fresh temporary folder."""
    return Store(tmp_path / "data")


@pytest.fixture
def three_cities():
    """Toronto, Montréal and Vancouver, in that order (picked by slug, not position)."""
    return tuple(CITIES_BY_SLUG[slug] for slug in ("toronto", "montreal", "vancouver"))


def make_metrics(rows: list[tuple[str, str, float]], period: str = "2025") -> pd.DataFrame:
    """Build tidy metric rows from (city, metric, value) tuples."""
    return pd.DataFrame(
        [{"city": c, "metric": m, "value": v, "period": period, "source": "test", "fetched_at": "2026-01-01T00:00:00Z"}
         for c, m, v in rows]
    )
