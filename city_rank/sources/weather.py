"""Current conditions + 7-day forecast from the Open-Meteo forecast API.

Runs on every pipeline run (ttl 0) so the dashboard always shows fresh
"right now" weather. Produces:

* metrics/weather.csv               - current temperature, humidity, wind, etc. (info only)
* history/weather_observations.csv  - one row per city per run, kept forever
* weather/forecast.csv              - next 7 days per city, shown on city pages

Open-Meteo is free and needs no API key: https://open-meteo.com/en/docs
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..config import HTTP_TIMEOUT
from ..store import Store, format_ts, utc_now
from .base import Source, for_each_city, metric_row, rows_to_frame

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7

# Open-Meteo field name -> our metric key, for the "current" block.
CURRENT_FIELDS = {
    "temperature_2m": "current_temp_c",
    "relative_humidity_2m": "current_humidity_pct",
    "wind_speed_10m": "current_wind_kmh",
    "precipitation": "current_precip_mm",
    "weather_code": "current_weather_code",
}


def fetch_city(session: requests.Session, city: City) -> dict[str, Any]:
    """Download current conditions and the daily forecast for one city (raw JSON)."""
    params = {
        "latitude": city.latitude,
        "longitude": city.longitude,
        "timezone": city.timezone,
        "forecast_days": FORECAST_DAYS,
        "current": ",".join(CURRENT_FIELDS),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
    }
    response = session.get(FORECAST_API, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload.get("current"), dict) or not isinstance(payload.get("daily"), dict):
        raise ValueError("unexpected Open-Meteo payload")
    return payload


def parse_current(city: City, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn the 'current' block into metric rows. Period = local observation time."""
    current = payload["current"]
    period = str(current.get("time", ""))
    return [metric_row(city, key, current.get(field), period) for field, key in CURRENT_FIELDS.items()]


def parse_forecast(city: City, payload: dict[str, Any]) -> pd.DataFrame:
    """Turn the 'daily' block into a small forecast table for one city."""
    daily = payload["daily"]
    return pd.DataFrame(
        {
            "city": city.slug,
            "date": daily.get("time", []),
            "weather_code": daily.get("weather_code", []),
            "temp_max_c": daily.get("temperature_2m_max", []),
            "temp_min_c": daily.get("temperature_2m_min", []),
            "precip_mm": daily.get("precipitation_sum", []),
            "precip_probability_pct": daily.get("precipitation_probability_max", []),
        }
    )


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Pipeline entry point: fetch all cities, write side files, return metric rows."""
    forecasts: list[pd.DataFrame] = []

    # Per-city work: one API call gives us both the current block and the forecast.
    def one_city(city: City) -> list[dict[str, Any]]:
        payload = fetch_city(session, city)
        forecasts.append(parse_forecast(city, payload))
        return parse_current(city, payload)

    rows = for_each_city(cities, one_city, "weather")
    metrics = rows_to_frame(rows)

    # Forecast table for the city pages (replaced every run).
    if forecasts:
        store.write_table("weather/forecast.csv", pd.concat(forecasts, ignore_index=True))

    # Observation history: pivot the current metrics to one row per city and append.
    if not metrics.empty:
        observations = metrics.pivot(index="city", columns="metric", values="value").reset_index()
        observations.insert(0, "observed_at_utc", format_ts(utc_now()))
        store.append_history("weather_observations", observations, key=["observed_at_utc", "city"])

    return metrics


SOURCE = Source(
    name="weather",
    ttl_hours=0,
    fetch=fetch,
    title="Open-Meteo Forecast API",
    url="https://open-meteo.com/en/docs",
)
