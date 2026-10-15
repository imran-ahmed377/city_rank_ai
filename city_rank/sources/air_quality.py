"""Air quality from the Open-Meteo Air Quality API (no key needed).

* pm25_mean_90d  - mean of hourly PM2.5 over the past ~90 days (ranked, lower is better).
                   A 90-day window smooths out single bad days but still captures
                   wildfire-smoke seasons.
* us_aqi_current - current US AQI (info only).

Docs: https://open-meteo.com/en/docs/air-quality-api
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..config import HTTP_TIMEOUT
from ..store import Store
from .base import Source, for_each_city, metric_row, rows_to_frame

AIR_QUALITY_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
PAST_DAYS = 90


def fetch_city(session: requests.Session, city: City) -> dict[str, Any]:
    """Download hourly PM2.5 for the past PAST_DAYS days plus the current AQI."""
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "timezone": city.timezone,
        "past_days": PAST_DAYS,
        "forecast_days": 1,
        "hourly": "pm2_5",
        "current": "us_aqi,pm2_5",
    }
    response = session.get(AIR_QUALITY_API, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return response.json()


def parse(city: City, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute the 90-day PM2.5 mean and read the current AQI."""
    hourly = payload.get("hourly") or {}
    times: list[str] = hourly.get("time", [])
    values: list[float | None] = hourly.get("pm2_5", [])
    current = payload.get("current") or {}

    # The response also contains today's forecast hours; keep only hours up to "now"
    # (ISO timestamps compare correctly as strings) so the mean is observed data.
    now = str(current.get("time", "9999"))
    observed = [v for t, v in zip(times, values) if v is not None and t <= now]

    rows = []
    if observed:
        period = f"{times[0][:10]} to {now[:10]}"
        rows.append(metric_row(city, "pm25_mean_90d", round(sum(observed) / len(observed), 2), period))
    rows.append(metric_row(city, "us_aqi_current", current.get("us_aqi"), now))
    return rows


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Pipeline entry point."""
    rows = for_each_city(cities, lambda city: parse(city, fetch_city(session, city)), "air_quality")
    return rows_to_frame(rows)


SOURCE = Source(
    name="air_quality",
    ttl_hours=6,
    fetch=fetch,
    title="Open-Meteo Air Quality API",
    url="https://open-meteo.com/en/docs/air-quality-api",
)
