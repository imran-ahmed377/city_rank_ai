"""Smoke tests for the static-site renderer and the pipeline orchestration."""

from __future__ import annotations

import pandas as pd

from city_rank.cities import CITIES
from city_rank.dashboard import refresh_label, render_site
from city_rank.pipeline import run_sources
from city_rank.scoring import build_rankings
from city_rank.sources.base import Source
from tests.conftest import make_metrics


def _sample_result():
    rows = []
    for i, city in enumerate(CITIES):
        rows += [(city.slug, "rent_2br", 1500 + 50 * i), (city.slug, "unemployment_rate", 5 + i * 0.2)]
    return build_rankings(make_metrics(rows), CITIES)


def test_render_site_writes_index_and_city_pages(tmp_path, store):
    docs = tmp_path / "docs"
    run_status = {"sources": [{"source": "housing", "title": "CMHC", "url": "https://example.org", "state": "updated"}]}
    render_site(_sample_result(), store, run_status, docs, generated_at=pd.Timestamp("2026-10-14T22:00Z").to_pydatetime())

    index = (docs / "index.html").read_text(encoding="utf-8")
    assert "Toronto" in index and "rank-data" in index
    assert (docs / "assets" / "rankings.js").exists()
    assert len(list((docs / "city").glob("*.html"))) == len(CITIES)
    toronto = (docs / "city" / "toronto.html").read_text(encoding="utf-8")
    assert "Average 2-bedroom rent" in toronto


def test_refresh_label():
    assert refresh_label(0) == "every run"
    assert refresh_label(12) == "every 12 hours"
    assert refresh_label(24) == "daily"
    assert refresh_label(168) == "every 7 days"


def test_run_sources_isolates_failures(store, three_cities):
    def good(session, cities, store):
        return pd.DataFrame([{"city": c.slug, "metric": "rent_2br", "value": 1000, "period": "2025"} for c in cities])

    def broken(session, cities, store):
        raise RuntimeError("API down")

    sources = [Source("good", 0, good, "Good", ""), Source("broken", 0, broken, "Broken", "")]
    statuses = {s["source"]: s for s in run_sources(store, sources, three_cities)}

    assert statuses["good"]["state"] == "updated"
    assert statuses["broken"]["state"] == "failed" and "API down" in statuses["broken"]["error"]
    assert len(store.load_metrics("good")) == 3


def test_run_sources_retries_only_missing_cities(store, three_cities):
    asked: list[list[str]] = []

    def fetch(session, cities, store):
        asked.append([c.slug for c in cities])
        return pd.DataFrame([{"city": c.slug, "metric": "rent_2br", "value": 1, "period": "x"} for c in cities])

    source = Source("housing_test", 24, fetch, "T", "")
    run_sources(store, [source], three_cities[:2])   # first run: two cities
    run_sources(store, [source], three_cities)       # fresh, but Vancouver missing
    run_sources(store, [source], three_cities)       # fresh and complete -> cached
    assert asked == [["toronto", "montreal"], ["vancouver"]]
