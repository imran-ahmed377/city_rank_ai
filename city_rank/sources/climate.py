"""Past-year climate from the Open-Meteo historical (archive) API.

For each city we download the previous 365 days of daily weather and:

1. save the full daily table to weather/daily_365.csv (drives the charts on
   each city page), and
2. summarise it into ranked climate metrics: extreme cold days, hot days,
   snowfall, wet days and sunshine hours.

Refreshed every 12 hours (the archive only gains one day per day).
Docs: https://open-meteo.com/en/docs/historical-weather-api
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..config import HTTP_TIMEOUT
from ..store import Store, utc_now
from .base import Source, for_each_city, metric_row, rows_to_frame

ARCHIVE_API = "https://archive-api.open-meteo.com/v1/archive"
WINDOW_DAYS = 365

# Thresholds used for the climate metrics (see catalog.py for descriptions).
EXTREME_COLD_C = -20.0   # daily low below this counts as an "extreme cold day"
HOT_C = 30.0             # daily high above this counts as a "hot day"
WET_DAY_MM = 1.0         # at least this much precipitation counts as a "wet day"

DAILY_FIELDS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "rain_sum",
    "snowfall_sum",
    "wind_speed_10m_max",
    "sunshine_duration",
)


def date_window(today=None) -> tuple[str, str]:
    """(start, end) dates for the last WINDOW_DAYS full days, ending yesterday (UTC)."""
    end = (today or utc_now().date()) - timedelta(days=1)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    return start.isoformat(), end.isoformat()


def fetch_city(session: requests.Session, city: City, start: str, end: str) -> pd.DataFrame:
    """Download daily archive data for one city and return it as a DataFrame."""
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "timezone": city.timezone,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_FIELDS),
    }
    response = session.get(ARCHIVE_API, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    daily = response.json().get("daily")
    if not isinstance(daily, dict):
        raise ValueError("unexpected Open-Meteo archive payload")

    # Rename API fields to short, unit-bearing column names.
    df = pd.DataFrame(
        {
            "date": daily.get("time", []),
            "temp_max_c": daily.get("temperature_2m_max", []),
            "temp_min_c": daily.get("temperature_2m_min", []),
            "precip_mm": daily.get("precipitation_sum", []),
            "rain_mm": daily.get("rain_sum", []),
            "snowfall_cm": daily.get("snowfall_sum", []),
            "wind_max_kmh": daily.get("wind_speed_10m_max", []),
            # sunshine_duration is in seconds -> convert to hours.
            "sunshine_h": [None if s is None else round(s / 3600, 2) for s in daily.get("sunshine_duration", [])],
        }
    )
    df.insert(0, "city", city.slug)
    return df


def summarise(city: City, daily: pd.DataFrame, period: str) -> list[dict[str, Any]]:
    """Reduce one city's daily table to the yearly climate metrics.

    Days with missing values are simply not counted (comparisons with NaN are False).
    """
    if daily.empty:
        return []
    mean_temp = ((daily["temp_max_c"] + daily["temp_min_c"]) / 2).mean()
    return [
        metric_row(city, "cold_days", int((daily["temp_min_c"] < EXTREME_COLD_C).sum()), period),
        metric_row(city, "hot_days", int((daily["temp_max_c"] > HOT_C).sum()), period),
        metric_row(city, "snowfall_cm", round(float(daily["snowfall_cm"].sum()), 1), period),
        metric_row(city, "wet_days", int((daily["precip_mm"] >= WET_DAY_MM).sum()), period),
        metric_row(city, "sunshine_hours", round(float(daily["sunshine_h"].sum()), 0), period),
        metric_row(city, "mean_temp_c", round(float(mean_temp), 1), period),
    ]


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Pipeline entry point."""
    start, end = date_window()
    period = f"{start} to {end}"
    tables: list[pd.DataFrame] = []

    def one_city(city: City) -> list[dict[str, Any]]:
        daily = fetch_city(session, city, start, end)
        tables.append(daily)
        return summarise(city, daily, period)

    rows = for_each_city(cities, one_city, "climate")

    # Merge into the existing daily table so a city that failed today keeps its old data.
    if tables:
        new = pd.concat(tables, ignore_index=True)
        old = store.read_table("weather/daily_365.csv")
        if not old.empty:
            old = old[~old["city"].isin(new["city"].unique())]
            new = pd.concat([old, new], ignore_index=True)
        store.write_table("weather/daily_365.csv", new.sort_values(["city", "date"]))

    return rows_to_frame(rows)


SOURCE = Source(
    name="climate",
    ttl_hours=12,
    fetch=fetch,
    title="Open-Meteo Historical Weather API",
    url="https://open-meteo.com/en/docs/historical-weather-api",
)
