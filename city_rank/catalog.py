"""The catalog: what every metric means and how it counts toward the ranking.

This is the single place to change *what* is ranked:

* CATEGORIES - the ranking pillars (Safety, Housing cost, ...) and their default
  importance (0-10). The dashboard sliders start at these values.
* METRICS    - each individual measurement. A metric with a ``category`` is
  ranked; a metric whose category is None is "info only" (shown on the city
  page but not scored, e.g. current temperature or raw population).

The data sources (city_rank/sources/*) only produce values keyed by metric
``key``; everything about presentation and scoring comes from here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """A ranking pillar. ``default_weight`` is a 0-10 importance level."""

    key: str
    label: str
    default_weight: int
    description: str


@dataclass(frozen=True)
class Metric:
    """One measurement.

    key              : id used in data files ("unemployment_rate").
    label            : human-readable name.
    unit             : unit shown after the value ("%", "days", "CAD/month").
    category         : Category.key it scores toward, or None for info-only.
    higher_is_better : True/False for ranked metrics; None for info-only.
    source           : name of the source module that produces it.
    description      : one sentence explaining the metric (shown as a tooltip/table text).
    decimals         : how many decimals to display.
    """

    key: str
    label: str
    unit: str
    category: str | None
    higher_is_better: bool | None
    source: str
    description: str
    decimals: int = 1


# --- Categories --------------------------------------------------------------
# Default weights sum to 20; as percentages that is
# climate 15%, air 10%, safety 20%, economy 20%, housing 20%, traffic 10%, amenities 5%.
CATEGORIES: tuple[Category, ...] = (
    Category("safety", "Safety", 4, "Police-reported crime, weighted by seriousness."),
    Category("economy", "Jobs & economy", 4, "Labour market strength and population growth."),
    Category("housing", "Housing cost", 4, "Average rent and how fast it is rising."),
    Category("climate", "Climate", 3, "Extreme cold/heat, snow, wet days and sunshine over the past year."),
    Category("air", "Air quality", 2, "Fine-particle (PM2.5) pollution over the past 90 days."),
    Category("traffic", "Traffic", 2, "Rush-hour road congestion measured by TomTom."),
    Category("amenities", "Amenities", 1, "Parks, healthcare, schools and transit stops near downtown."),
)

CATEGORIES_BY_KEY: dict[str, Category] = {c.key: c for c in CATEGORIES}


# --- Metrics -----------------------------------------------------------------
METRICS: tuple[Metric, ...] = (
    # Safety (StatCan table 35-10-0026-01, annual)
    Metric("crime_severity_index", "Crime Severity Index", "index", "safety", False, "crime",
           "Volume and seriousness of all police-reported crime (Canada 2006 = 100).", 1),
    Metric("violent_crime_severity_index", "Violent Crime Severity Index", "index", "safety", False, "crime",
           "Same as the CSI but for violent offences only.", 1),

    # Jobs & economy (StatCan 14-10-0459-01 monthly, 17-10-0148-01 annual)
    Metric("unemployment_rate", "Unemployment rate", "%", "economy", False, "jobs",
           "Share of the labour force without a job (3-month moving average, seasonally adjusted).", 1),
    Metric("employment_rate", "Employment rate", "%", "economy", True, "jobs",
           "Share of people aged 15+ who are employed.", 1),
    Metric("population_growth_pct", "Population growth", "% / yr", "economy", True, "population",
           "Change in population over the latest year; a sign of economic pull.", 2),
    Metric("population", "Population", "people", None, None, "population",
           "Metro-area population estimate (July 1).", 0),

    # Housing cost (StatCan 34-10-0133-01 / CMHC, annual October survey)
    Metric("rent_2br", "Average 2-bedroom rent", "CAD/month", "housing", False, "housing",
           "CMHC average rent for a two-bedroom unit in apartment and row buildings.", 0),
    Metric("rent_change_pct", "Rent change", "% / yr", "housing", False, "housing",
           "Year-over-year change in the average 2-bedroom rent.", 1),

    # Climate (Open-Meteo historical archive, previous 365 days)
    Metric("cold_days", "Extreme cold days", "days", "climate", False, "climate",
           "Days in the past year with a low below −20 °C.", 0),
    Metric("hot_days", "Hot days", "days", "climate", False, "climate",
           "Days in the past year with a high above 30 °C.", 0),
    Metric("snowfall_cm", "Snowfall", "cm / yr", "climate", False, "climate",
           "Total snowfall over the past year.", 0),
    Metric("wet_days", "Wet days", "days", "climate", False, "climate",
           "Days in the past year with at least 1 mm of precipitation.", 0),
    Metric("sunshine_hours", "Sunshine", "hours / yr", "climate", True, "climate",
           "Total hours of sunshine over the past year.", 0),
    Metric("mean_temp_c", "Average temperature", "°C", None, None, "climate",
           "Mean of daily highs and lows over the past year.", 1),

    # Air quality (Open-Meteo air-quality API)
    Metric("pm25_mean_90d", "PM2.5 (90-day mean)", "µg/m³", "air", False, "air_quality",
           "Average fine-particle pollution over the past 90 days; wildfire smoke shows up here.", 1),
    Metric("us_aqi_current", "Air Quality Index now", "US AQI", None, None, "air_quality",
           "Current US Air Quality Index (0-50 good, 51-100 moderate, 100+ unhealthy for some).", 0),

    # Traffic (TomTom Traffic Flow API, rush-hour samples, 30-day mean)
    Metric("congestion_pct", "Rush-hour congestion", "%", "traffic", False, "traffic",
           "How much slower than free-flow traffic moves at rush hour (30-day average).", 1),
    Metric("traffic_samples", "Traffic samples (30 days)", "samples", None, None, "traffic",
           "Number of road-segment measurements behind the congestion figure.", 0),

    # Amenities (OpenStreetMap via the Overpass API, within 10 km of downtown)
    Metric("parks_10km", "Parks", "count", "amenities", True, "amenities",
           "Parks mapped in OpenStreetMap within 10 km of downtown.", 0),
    Metric("healthcare_10km", "Hospitals & clinics", "count", "amenities", True, "amenities",
           "Hospitals, clinics and doctors' offices within 10 km of downtown.", 0),
    Metric("schools_10km", "Schools", "count", "amenities", True, "amenities",
           "Schools within 10 km of downtown.", 0),
    Metric("transit_stops_10km", "Transit stops", "count", "amenities", True, "amenities",
           "Public-transport stops/platforms within 10 km of downtown.", 0),

    # Current weather (Open-Meteo forecast API) - info only, refreshed every run
    Metric("current_temp_c", "Temperature now", "°C", None, None, "weather", "Current air temperature.", 1),
    Metric("current_humidity_pct", "Humidity now", "%", None, None, "weather", "Current relative humidity.", 0),
    Metric("current_wind_kmh", "Wind now", "km/h", None, None, "weather", "Current wind speed at 10 m.", 1),
    Metric("current_precip_mm", "Precipitation now", "mm", None, None, "weather", "Precipitation in the current hour.", 1),
    Metric("current_weather_code", "Conditions code", "WMO", None, None, "weather", "WMO weather code.", 0),
)

METRICS_BY_KEY: dict[str, Metric] = {m.key: m for m in METRICS}


def ranked_metrics() -> list[Metric]:
    """Metrics that count toward a category score (category is not None)."""
    return [m for m in METRICS if m.category is not None]


def metrics_in_category(category_key: str) -> list[Metric]:
    """Ranked metrics belonging to one category, in catalog order."""
    return [m for m in METRICS if m.category == category_key]


def default_weights() -> dict[str, float]:
    """Category key -> default importance (0-10)."""
    return {c.key: float(c.default_weight) for c in CATEGORIES}
