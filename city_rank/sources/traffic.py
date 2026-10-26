"""Rush-hour congestion from the TomTom Traffic Flow API (free tier, API key).

How it works
------------
1. Around each city's downtown we pick SAMPLE_POINTS (the centre plus 8 compass
   points SAMPLE_RADIUS_KM away). TomTom snaps each point to the nearest major
   road segment and reports its current speed and its free-flow speed.
2. A city is only sampled when it is currently in its *local* weekday rush hour
   (07-10 or 16-19). The workflow runs every hour (GitHub often delays scheduled
   runs by hours, so fixed times would miss rush hour), and each run samples
   whichever cities are in rush hour at that moment.
3. Every sample is appended to history/traffic_samples.csv (kept 120 days).
4. The ranked metric is the 30-day average of
       congestion % = (1 - current_speed / free_flow_speed) * 100
   i.e. "traffic moves X% slower than when roads are empty".

Request budget: a city is in rush hour for 6 hours per weekday, so at most
20 cities x 6 runs x 9 points ≈ 1,080 requests/day - inside TomTom's free 2,500/day.

The key is read from the TOMTOM_API_KEY environment variable (a GitHub secret in
CI). Without a key, no new samples are taken but metrics are still computed from
any stored history. Set TRAFFIC_FORCE=1 to sample regardless of the time of day
(handy for testing; those samples are then also counted).

Docs: https://developer.tomtom.com/traffic-api/documentation/traffic-flow/flow-segment-data
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timedelta
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from ..cities import City
from ..config import HTTP_TIMEOUT
from ..store import Store, format_ts, utc_now
from .base import Source, metric_row, rows_to_frame

log = logging.getLogger(__name__)

FLOW_API = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
SAMPLE_RADIUS_KM = 4.0
COMPASS_BEARINGS = (0, 45, 90, 135, 180, 225, 270, 315)  # N, NE, E, ... NW
RUSH_HOURS = (range(7, 10), range(16, 19))               # local hours 07-09 and 16-18 (inclusive)
AVERAGE_WINDOW_DAYS = 30
KEEP_SAMPLE_DAYS = 120
MIN_CONFIDENCE = 0.5                                     # ignore low-confidence TomTom readings
HISTORY_NAME = "traffic_samples"


def sample_points(city: City) -> list[tuple[float, float]]:
    """Centre + 8 points on a circle of SAMPLE_RADIUS_KM around downtown.

    1 degree of latitude ≈ 111 km; a degree of longitude shrinks with cos(latitude).
    """
    points = [(city.latitude, city.longitude)]
    for bearing in COMPASS_BEARINGS:
        rad = math.radians(bearing)
        dlat = (SAMPLE_RADIUS_KM * math.cos(rad)) / 111.0
        dlon = (SAMPLE_RADIUS_KM * math.sin(rad)) / (111.0 * math.cos(math.radians(city.latitude)))
        points.append((round(city.latitude + dlat, 5), round(city.longitude + dlon, 5)))
    return points


def in_rush_hour(city: City, moment: datetime) -> bool:
    """True if ``moment`` falls in a weekday rush hour in the city's local time."""
    local = moment.astimezone(ZoneInfo(city.timezone))
    if local.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return any(local.hour in hours for hours in RUSH_HOURS)


def fetch_point(session: requests.Session, api_key: str, lat: float, lon: float) -> dict[str, Any]:
    """Query TomTom for the road segment nearest to (lat, lon)."""
    params = {"point": f"{lat},{lon}", "unit": "KMPH", "key": api_key}
    response = session.get(FLOW_API, params=params, timeout=HTTP_TIMEOUT)
    if not response.ok:
        # Raise our own error: requests' default message includes the full URL,
        # which would leak the API key into logs.
        raise RuntimeError(f"TomTom HTTP {response.status_code}")
    return response.json().get("flowSegmentData") or {}


def take_samples(session: requests.Session, api_key: str, cities: Sequence[City], now: datetime, force: bool) -> pd.DataFrame:
    """Sample every city that is in rush hour (or all cities when ``force``)."""
    rows: list[dict[str, Any]] = []
    stamp = format_ts(now)
    for city in cities:
        if not force and not in_rush_hour(city, now):
            continue
        for index, (lat, lon) in enumerate(sample_points(city)):
            try:
                data = fetch_point(session, api_key, lat, lon)
            except Exception as exc:  # noqa: BLE001 - one bad point shouldn't stop the run
                log.warning("[traffic] %s point %d failed: %s", city.name, index, exc)
                continue
            rows.append(
                {
                    "sampled_at_utc": stamp,
                    "city": city.slug,
                    "point": index,
                    "current_speed_kmh": data.get("currentSpeed"),
                    "free_flow_speed_kmh": data.get("freeFlowSpeed"),
                    "confidence": data.get("confidence"),
                    "road_closure": bool(data.get("roadClosure", False)),
                }
            )
    return pd.DataFrame(rows)


def valid_readings(samples: pd.DataFrame) -> pd.DataFrame:
    """Filter samples to trustworthy readings and add a ``congestion_pct`` column.

    Dropped: closed roads, low-confidence readings, and rows without a free-flow speed.
    Congestion is clipped at 0 (a road can briefly be faster than its "free flow").
    """
    if samples.empty:
        return samples.assign(congestion_pct=pd.Series(dtype=float))
    df = samples.copy()
    df = df[
        (~df["road_closure"].astype(str).str.lower().eq("true"))
        & (pd.to_numeric(df["confidence"], errors="coerce") >= MIN_CONFIDENCE)
        & (pd.to_numeric(df["free_flow_speed_kmh"], errors="coerce") > 0)
    ]
    ratio = pd.to_numeric(df["current_speed_kmh"]) / pd.to_numeric(df["free_flow_speed_kmh"])
    return df.assign(congestion_pct=((1 - ratio) * 100).clip(lower=0))


def congestion_by_city(samples: pd.DataFrame, now: datetime, window_days: int = AVERAGE_WINDOW_DAYS) -> pd.DataFrame:
    """Average congestion % per city over the last ``window_days`` days.

    Returns columns: city, congestion_pct, samples, first, last.
    """
    columns = ["city", "congestion_pct", "samples", "first", "last"]
    if samples.empty:
        return pd.DataFrame(columns=columns)

    # Keep only the averaging window, then only trustworthy readings.
    cutoff = format_ts(now - timedelta(days=window_days))
    df = valid_readings(samples[samples["sampled_at_utc"].astype(str) >= cutoff])
    if df.empty:
        return pd.DataFrame(columns=columns)

    grouped = df.groupby("city").agg(
        congestion_pct=("congestion_pct", "mean"),
        samples=("congestion_pct", "size"),
        first=("sampled_at_utc", "min"),
        last=("sampled_at_utc", "max"),
    )
    return grouped.reset_index()[columns]


def daily_congestion(samples: pd.DataFrame) -> pd.DataFrame:
    """Mean congestion % per city per UTC day - used for the city-page chart."""
    df = valid_readings(samples)
    if df.empty:
        return pd.DataFrame(columns=["city", "date", "congestion_pct"])
    df = df.assign(date=df["sampled_at_utc"].astype(str).str[:10])
    return df.groupby(["city", "date"], as_index=False)["congestion_pct"].mean()


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Pipeline entry point: maybe sample now, then compute 30-day averages."""
    now = utc_now()
    api_key = os.getenv("TOMTOM_API_KEY", "").strip()
    force = os.getenv("TRAFFIC_FORCE", "") == "1"

    # Step 1 - take new samples (only possible with an API key).
    if api_key:
        new_samples = take_samples(session, api_key, cities, now, force)
        if not new_samples.empty:
            store.append_history(
                HISTORY_NAME, new_samples, key=["sampled_at_utc", "city", "point"],
                time_column="sampled_at_utc", keep_days=KEEP_SAMPLE_DAYS, now=now,
            )
        log.info("[traffic] took %d samples", len(new_samples))
    else:
        log.warning("[traffic] TOMTOM_API_KEY not set - no new samples; using stored history only")

    # Step 2 - compute metrics from the full (stored) history.
    summary = congestion_by_city(store.load_history(HISTORY_NAME), now)
    rows: list[dict[str, Any]] = []
    for record in summary.itertuples(index=False):
        period = f"{str(record.first)[:10]} to {str(record.last)[:10]}"
        rows.append(metric_row(record.city, "congestion_pct", round(float(record.congestion_pct), 1), period))
        rows.append(metric_row(record.city, "traffic_samples", int(record.samples), period))
    return rows_to_frame(rows)


SOURCE = Source(
    name="traffic",
    ttl_hours=0,
    fetch=fetch,
    title="TomTom Traffic Flow API",
    url="https://developer.tomtom.com/traffic-api/documentation/traffic-flow/flow-segment-data",
)
