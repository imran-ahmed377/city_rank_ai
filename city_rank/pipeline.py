"""The end-to-end run: fetch -> score -> record history -> render website.

Run it with:  python -m city_rank            (normal run, respects refresh intervals)
              python -m city_rank --force    (refetch every source now)
              python -m city_rank --no-fetch (only re-score and re-render from data/)
              python -m city_rank --only crime,jobs
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from typing import Any, Sequence

import pandas as pd

from . import config
from .cities import CITIES, City
from .dashboard import render_site
from .http import build_session
from .scoring import RankingResult, build_rankings
from .sources import ALL_SOURCES, SOURCES_BY_NAME
from .sources.base import Source
from .store import Store, format_ts, utc_now

log = logging.getLogger("city_rank")

RUN_STATUS_FILE = "run_status.json"


def run_sources(
    store: Store,
    sources: Sequence[Source],
    cities: Sequence[City],
    force: bool = False,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Run each source once, isolating failures, and return a status per source.

    Status values:
      updated - fetched and saved new data
      cached  - stored data is still fresh (within ttl_hours); only cities with no
                data at all were retried
      empty   - ran fine but returned no rows (e.g. traffic with no key and no history)
      failed  - raised an error; previously stored data (if any) is kept
    """
    now = now or utc_now()
    session = build_session()
    statuses: list[dict[str, Any]] = []

    for source in sources:
        started = time.monotonic()
        status: dict[str, Any] = {"source": source.name, "title": source.title, "url": source.url}

        # Decide which cities to fetch:
        #  - stale (or forced) source        -> all cities
        #  - fresh source, some cities empty -> only those cities (e.g. a city whose
        #    request timed out last time gets retried without refetching everyone)
        #  - fresh and complete              -> nothing, use stored data
        targets = list(cities)
        if not force and store.is_fresh(source.name, source.ttl_hours, now):
            missing = set(store.cities_missing(source.name, [c.slug for c in cities]))
            targets = [c for c in cities if c.slug in missing]
            if not targets:
                fetched = store.last_fetched(source.name)
                status.update(state="cached", fetched_at=format_ts(fetched) if fetched else None)
                log.info("%-12s cached (fetched %s)", source.name, status["fetched_at"])
                statuses.append(status)
                continue
            log.info("%-12s fresh, retrying %d missing cities", source.name, len(targets))

        partial_retry = len(targets) < len(cities)
        try:
            rows = source.fetch(session, targets, store)
            if rows.empty:
                # A retry that still finds nothing (e.g. Oshawa has no crime index) is not an error.
                status.update(state="cached" if partial_retry else "empty", rows=0)
            else:
                # Stamp provenance columns, then merge into data/metrics/<source>.csv.
                rows = rows.assign(source=source.name, fetched_at=format_ts(now))
                store.save_metrics(source.name, rows)
                status.update(state="updated", rows=len(rows), cities=int(rows["city"].nunique()))
        except Exception as exc:  # noqa: BLE001 - one broken API must not stop the run
            log.exception("%s failed", source.name)
            # A failed retry of a few missing cities leaves the rest of the data intact.
            status.update(state="cached" if partial_retry else "failed", error=str(exc)[:300])

        last = store.last_fetched(source.name)
        status["fetched_at"] = format_ts(last) if last else None
        status["seconds"] = round(time.monotonic() - started, 1)
        log.info("%-12s %s %s", source.name, status["state"], {k: status.get(k) for k in ("rows", "cities", "error") if k in status})
        statuses.append(status)

    return statuses


def record_rankings(store: Store, result: RankingResult, now: datetime) -> pd.DataFrame:
    """Append today's overall score and rank per city to history/rankings.csv.

    One row per city per UTC date; later runs on the same day overwrite earlier ones.
    """
    today = now.strftime("%Y-%m-%d")
    rows = result.overall.reset_index()[["city", "overall", "rank"]].dropna(subset=["overall"])
    rows = rows.assign(date=today, overall=rows["overall"].round(2))[["date", "city", "overall", "rank"]]
    return store.append_history("rankings", rows, key=["date", "city"])


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m city_rank", description="Build the City Rank dataset and dashboard.")
    parser.add_argument("--force", action="store_true", help="ignore refresh intervals and refetch every source")
    parser.add_argument("--no-fetch", action="store_true", help="skip all API calls; re-score and re-render from stored data")
    parser.add_argument("--only", default="", help="comma-separated source names to run (others use stored data)")
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING ...")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code (0 = success)."""
    args = parse_args(argv)
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    now = utc_now()
    store = Store(config.DATA_DIR)

    # 1) Fetch ------------------------------------------------------------------
    if not args.no_fetch:
        selected = list(ALL_SOURCES)
        if args.only:
            names = [n.strip() for n in args.only.split(",") if n.strip()]
            unknown = [n for n in names if n not in SOURCES_BY_NAME]
            if unknown:
                log.error("unknown source(s): %s (choose from %s)", unknown, sorted(SOURCES_BY_NAME))
                return 2
            selected = [SOURCES_BY_NAME[n] for n in names]
        statuses = run_sources(store, selected, CITIES, force=args.force or bool(args.only), now=now)
        if not args.only:
            # Only a full run defines the "last run" status shown on the dashboard.
            store.write_json(RUN_STATUS_FILE, {"generated_at": format_ts(now), "sources": statuses})

    # 2) Score ------------------------------------------------------------------
    result = build_rankings(store.load_all_metrics(), CITIES)
    if result.overall["overall"].notna().sum() == 0:
        log.error("no city could be scored - every source is empty; not rendering the site")
        return 1

    # 3) History + 4) Render ----------------------------------------------------
    if not args.no_fetch:
        record_rankings(store, result, now)
    run_status = store.read_json(RUN_STATUS_FILE, default={"generated_at": format_ts(now), "sources": []})
    render_site(result, store, run_status, config.DOCS_DIR, generated_at=now)

    failed = [s["source"] for s in run_status.get("sources", []) if s.get("state") == "failed"]
    if failed:
        log.warning("finished with failed sources (stored data used instead): %s", ", ".join(failed))
    log.info("site written to %s", config.DOCS_DIR)
    return 0
