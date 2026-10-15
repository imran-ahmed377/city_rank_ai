"""Tests for file storage in city_rank/store.py."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from city_rank.store import format_ts
from tests.conftest import make_metrics


def test_save_metrics_merges_and_keeps_unrefreshed_cities(store):
    store.save_metrics("crime", make_metrics([("toronto", "crime_severity_index", 50),
                                               ("montreal", "crime_severity_index", 60)]))
    # Second fetch only returned Toronto (Montréal's request failed).
    merged = store.save_metrics("crime", make_metrics([("toronto", "crime_severity_index", 55)]))
    values = dict(zip(merged["city"], merged["value"]))
    assert values == {"montreal": 60, "toronto": 55}  # new value wins, old Montréal kept


def test_is_fresh_respects_ttl(store):
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    rows = make_metrics([("toronto", "rent_2br", 2000)])
    rows["fetched_at"] = format_ts(now - timedelta(hours=5))
    store.save_metrics("housing", rows)

    assert store.is_fresh("housing", ttl_hours=6, now=now)
    assert not store.is_fresh("housing", ttl_hours=4, now=now)
    assert not store.is_fresh("housing", ttl_hours=0, now=now)      # 0 = always refetch
    assert not store.is_fresh("missing_source", ttl_hours=99, now=now)


def test_cities_missing(store):
    store.save_metrics("crime", make_metrics([("toronto", "crime_severity_index", 50)]))
    assert store.cities_missing("crime", ["toronto", "oshawa"]) == ["oshawa"]


def test_append_history_dedupes_and_prunes(store):
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    old = pd.DataFrame({"t": [format_ts(now - timedelta(days=200))], "city": ["toronto"], "v": [1]})
    store.append_history("samples", old, key=["t", "city"])

    new = pd.DataFrame({"t": [format_ts(now)] * 2, "city": ["toronto", "toronto"], "v": [2, 3]})
    result = store.append_history("samples", new, key=["t", "city"], time_column="t", keep_days=120, now=now)

    # The 200-day-old row is pruned; of the two duplicates the last one is kept.
    assert result["v"].tolist() == [3]


def test_load_all_metrics_empty(store):
    assert store.load_all_metrics().empty
