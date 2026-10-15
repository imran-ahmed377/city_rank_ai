"""Building blocks shared by every data source.

Contract for a source module
----------------------------
Each source exposes a ``SOURCE`` object (see the Source dataclass below) whose
``fetch(session, cities, store)`` function returns a DataFrame of tidy rows:

    city    metric               value   period
    toronto unemployment_rate    6.9     2026-09

The pipeline then adds ``source`` and ``fetched_at`` columns and saves the rows.
``store`` is passed in so a source can also write side files (history, charts data).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store

log = logging.getLogger(__name__)

# Signature every source's fetch function must have.
FetchFn = Callable[[requests.Session, Sequence[City], Store], pd.DataFrame]


@dataclass(frozen=True)
class Source:
    """A data source the pipeline can run.

    name      : file name under data/metrics/ and the label in run_status.json.
    ttl_hours : skip fetching if the stored data is younger than this (0 = always fetch).
    fetch     : function that downloads and returns tidy metric rows.
    title     : human-readable provider name for the dashboard's "Sources" table.
    url       : link to the provider's documentation/data page.
    """

    name: str
    ttl_hours: float
    fetch: FetchFn
    title: str
    url: str


def metric_row(city: City | str, metric: str, value: Any, period: str) -> dict[str, Any]:
    """Build one tidy row. ``city`` may be a City or a slug string."""
    slug = city.slug if isinstance(city, City) else city
    return {"city": slug, "metric": metric, "value": value, "period": period}


def rows_to_frame(rows: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """List of metric_row dicts -> DataFrame with the expected columns (even if empty).

    Rows whose value is missing (None/NaN) are dropped - "no data" is represented
    by the absence of a row, never by an empty value.
    """
    df = pd.DataFrame(list(rows), columns=["city", "metric", "value", "period"])
    return df.dropna(subset=["value"]).reset_index(drop=True)


def for_each_city(
    cities: Sequence[City],
    fn: Callable[[City], list[dict[str, Any]]],
    source_name: str,
) -> list[dict[str, Any]]:
    """Run ``fn(city)`` for every city, isolating failures.

    If one city's request fails, it is logged and skipped; the other cities
    still produce data. Raises only if *every* city failed, so the pipeline can
    report the whole source as failed.
    """
    rows: list[dict[str, Any]] = []
    failures = 0
    for city in cities:
        try:
            rows.extend(fn(city))
        except Exception as exc:  # noqa: BLE001 - we really do want to catch everything per city
            failures += 1
            log.warning("[%s] %s failed: %s", source_name, city.name, exc)
    if cities and failures == len(cities):
        raise RuntimeError(f"{source_name}: all {failures} cities failed")
    return rows
