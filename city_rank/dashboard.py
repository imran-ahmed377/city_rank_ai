"""Render the static website (docs/) from a RankingResult.

Output:
    docs/index.html          rankings table + weight sliders + methodology + sources
    docs/city/<slug>.html    one detail page per city (scores, metrics, charts)
    docs/assets/*            CSS/JS copied from city_rank/static/
    docs/.nojekyll           tells GitHub Pages to serve files as-is

Templates live in city_rank/templates/. Each page embeds only its own data
(as JSON inside a <script> tag), so pages stay small and work when opened
straight from disk.
"""

from __future__ import annotations

import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config
from .catalog import CATEGORIES, METRICS, METRICS_BY_KEY, Metric
from .cities import CITIES, CITIES_BY_SLUG
from .scoring import RankingResult, category_ranks
from .sources import SOURCES_BY_NAME
from .sources.traffic import HISTORY_NAME as TRAFFIC_HISTORY, daily_congestion
from .store import Store

# WMO weather interpretation codes used by Open-Meteo -> short description.
WMO_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Rain showers", 81: "Rain showers", 82: "Violent showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


# --------------------------------------------------------------------------- small helpers
def clean(value: Any) -> Any:
    """Convert pandas/NumPy missing values to None and NumPy numbers to Python numbers (JSON-safe)."""
    if value is None:
        return None
    if hasattr(value, "item"):  # numpy scalar -> plain Python int/float
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def format_value(value: Any, metric: Metric) -> str:
    """Format a metric value for display: thousands separators + catalog decimals."""
    value = clean(value)
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:,.{metric.decimals}f}"
    return str(value)


def format_score(value: Any) -> str:
    value = clean(value)
    return "—" if value is None else f"{value:.0f}"


def aqi_label(aqi: Any) -> str:
    """US AQI number -> category name."""
    aqi = clean(aqi)
    if aqi is None:
        return ""
    for limit, label in ((50, "Good"), (100, "Moderate"), (150, "Unhealthy for sensitive groups"),
                         (200, "Unhealthy"), (300, "Very unhealthy")):
        if aqi <= limit:
            return label
    return "Hazardous"


def refresh_label(ttl_hours: float | None) -> str:
    """Source refresh interval in words: 'every run', 'every 12 hours', 'every 7 days'."""
    if ttl_hours is None:
        return ""
    if ttl_hours <= 0:
        return "every run"
    if ttl_hours < 24:
        return f"every {ttl_hours:g} hours"
    days = ttl_hours / 24
    return "daily" if days == 1 else f"every {days:g} days"


def format_time(moment: datetime) -> str:
    """'14 Oct 2026, 22:00 UTC'."""
    return moment.strftime("%d %b %Y, %H:%M UTC")


# --------------------------------------------------------------------------- page contexts
def build_index_context(result: RankingResult, run_status: dict[str, Any]) -> dict[str, Any]:
    """Data for index.html: one row per city in rank order."""
    cat_ranks = category_ranks(result.category_scores)
    rows = []
    for slug, overall in result.overall.iterrows():
        city = CITIES_BY_SLUG[slug]
        rows.append(
            {
                "slug": slug,
                "name": city.name,
                "province": city.province,
                "rank": clean(overall["rank"]),
                "overall": clean(overall["overall"]),
                "coverage": clean(overall["coverage"]),
                # None = no data for that category (shown as an em dash).
                "scores": {c.key: clean(result.category_scores.at[slug, c.key]) for c in CATEGORIES},
                "category_ranks": {c.key: clean(cat_ranks.at[slug, c.key]) for c in CATEGORIES},
            }
        )

    # Join run status with source metadata for the "Data sources" table.
    sources = []
    for status in run_status.get("sources", []):
        source = SOURCES_BY_NAME.get(status.get("source"))
        sources.append({**status, "refresh": refresh_label(source.ttl_hours if source else None)})

    return {
        "categories": [
            {"key": c.key, "label": c.label, "description": c.description, "default_weight": c.default_weight}
            for c in CATEGORIES
        ],
        "rows": rows,
        "sources": sources,
        "metrics_by_category": {
            c.key: [m.label for m in METRICS if m.category == c.key] for c in CATEGORIES
        },
    }


def monthly_summary(daily: pd.DataFrame) -> list[dict[str, Any]]:
    """Month-by-month table (the accessible twin of the year-long charts)."""
    if daily.empty:
        return []
    df = daily.assign(month=daily["date"].astype(str).str[:7])
    grouped = df.groupby("month").agg(
        temp_max_c=("temp_max_c", "mean"),
        temp_min_c=("temp_min_c", "mean"),
        rain_mm=("rain_mm", "sum"),
        snowfall_cm=("snowfall_cm", "sum"),
        sunshine_h=("sunshine_h", "sum"),
    )
    return [
        {
            "month": month,
            "temp_max_c": f"{r.temp_max_c:.1f}",
            "temp_min_c": f"{r.temp_min_c:.1f}",
            "rain_mm": f"{r.rain_mm:.0f}",
            "snowfall_cm": f"{r.snowfall_cm:.0f}",
            "sunshine_h": f"{r.sunshine_h:.0f}",
        }
        for month, r in grouped.iterrows()
    ]


def build_city_context(
    slug: str,
    result: RankingResult,
    climate_daily: pd.DataFrame,
    forecast: pd.DataFrame,
    rank_history: pd.DataFrame,
    traffic_daily: pd.DataFrame,
) -> dict[str, Any]:
    """Data for city.html."""
    city = CITIES_BY_SLUG[slug]
    overall = result.overall.loc[slug]
    cat_ranks = category_ranks(result.category_scores)
    values = result.values.loc[slug] if slug in result.values.index else pd.Series(dtype=float)
    periods = result.periods.loc[slug] if slug in result.periods.index else pd.Series(dtype=object)

    def value_of(key: str) -> Any:
        return clean(values.get(key)) if key in values.index else None

    # Category bars.
    categories = [
        {
            "key": c.key,
            "label": c.label,
            "description": c.description,
            "score": clean(result.category_scores.at[slug, c.key]),
            "rank": clean(cat_ranks.at[slug, c.key]),
        }
        for c in CATEGORIES
    ]

    # Metric table, grouped by category, then an "other information" group.
    def metric_entry(metric: Metric) -> dict[str, Any]:
        score = result.metric_scores.at[slug, metric.key] if metric.key in result.metric_scores.columns else None
        source = SOURCES_BY_NAME.get(metric.source)
        return {
            "label": metric.label,
            "description": metric.description,
            "value": format_value(value_of(metric.key), metric),
            "unit": metric.unit,
            "score": format_score(score),
            "period": clean(periods.get(metric.key)) if metric.key in periods.index else None,
            "source_title": source.title if source else metric.source,
            "source_url": source.url if source else "",
            "higher_is_better": metric.higher_is_better,
        }

    groups = [
        {"label": c.label, "metrics": [metric_entry(m) for m in METRICS if m.category == c.key]}
        for c in CATEGORIES
    ]
    groups.append(
        {
            "label": "Other information (not scored)",
            "metrics": [metric_entry(m) for m in METRICS if m.category is None and m.source != "weather"],
        }
    )

    # "Right now" tiles.
    code = value_of("current_weather_code")
    aqi = value_of("us_aqi_current")
    now_tiles = {
        "temp": format_value(value_of("current_temp_c"), METRICS_BY_KEY["current_temp_c"]),
        "conditions": WMO_CODES.get(int(code), "") if code is not None else "",
        "humidity": format_value(value_of("current_humidity_pct"), METRICS_BY_KEY["current_humidity_pct"]),
        "wind": format_value(value_of("current_wind_kmh"), METRICS_BY_KEY["current_wind_kmh"]),
        "aqi": format_value(aqi, METRICS_BY_KEY["us_aqi_current"]),
        "aqi_label": aqi_label(aqi),
        "observed": clean(periods.get("current_temp_c")) if "current_temp_c" in periods.index else None,
    }

    # 7-day forecast rows.
    forecast_rows = []
    for r in forecast[forecast["city"] == slug].itertuples(index=False) if not forecast.empty else []:
        forecast_rows.append(
            {
                "date": pd.to_datetime(r.date).strftime("%a %d %b"),
                "conditions": WMO_CODES.get(int(r.weather_code), "") if pd.notna(r.weather_code) else "",
                "high": "—" if pd.isna(r.temp_max_c) else f"{r.temp_max_c:.0f}",
                "low": "—" if pd.isna(r.temp_min_c) else f"{r.temp_min_c:.0f}",
                "precip": "—" if pd.isna(r.precip_mm) else f"{r.precip_mm:.1f}",
                "chance": "—" if pd.isna(r.precip_probability_pct) else f"{r.precip_probability_pct:.0f}",
            }
        )

    # Chart data (lists of plain values; None for gaps).
    daily = climate_daily[climate_daily["city"] == slug].sort_values("date") if not climate_daily.empty else climate_daily
    history = rank_history[rank_history["city"] == slug].sort_values("date") if not rank_history.empty else rank_history
    traffic = traffic_daily[traffic_daily["city"] == slug].sort_values("date") if not traffic_daily.empty else traffic_daily

    def column(df: pd.DataFrame, name: str) -> list[Any]:
        return [clean(v) for v in df[name]] if not df.empty and name in df else []

    charts = {
        "climate": {
            "date": column(daily, "date"),
            "temp_max_c": column(daily, "temp_max_c"),
            "temp_min_c": column(daily, "temp_min_c"),
            "rain_mm": column(daily, "rain_mm"),
            "snowfall_cm": column(daily, "snowfall_cm"),
        },
        "rank_history": {"date": column(history, "date"), "rank": column(history, "rank"), "overall": column(history, "overall")},
        "traffic": {"date": column(traffic, "date"), "congestion_pct": [None if v is None else round(v, 1) for v in column(traffic, "congestion_pct")]},
        "total_cities": len(CITIES),
    }

    return {
        "city": city,
        "rank": clean(overall["rank"]),
        "overall": clean(overall["overall"]),
        "coverage": clean(overall["coverage"]),
        "categories": categories,
        "groups": groups,
        "now": now_tiles,
        "forecast": forecast_rows,
        "monthly": monthly_summary(daily),
        "climate_window": f"{daily['date'].iloc[0]} to {daily['date'].iloc[-1]}" if not daily.empty else None,
        "charts": charts,
    }


# --------------------------------------------------------------------------- rendering
def make_environment() -> Environment:
    """Jinja2 environment with HTML auto-escaping and our display filters."""
    env = Environment(
        loader=FileSystemLoader(config.TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["score"] = format_score
    env.filters["ordinal_rank"] = lambda r: "—" if clean(r) is None else f"#{int(r)}"
    return env


def render_site(
    result: RankingResult,
    store: Store,
    run_status: dict[str, Any],
    docs_dir: Path,
    generated_at: datetime,
) -> None:
    """Write the whole site into ``docs_dir`` (replacing the previous build)."""
    env = make_environment()
    docs_dir = Path(docs_dir)

    # Fresh output folders: remove old city pages and assets so deleted cities don't linger.
    for sub in ("city", "assets"):
        shutil.rmtree(docs_dir / sub, ignore_errors=True)
    (docs_dir / "city").mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.STATIC_DIR, docs_dir / "assets")
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")

    common = {
        "site_title": config.SITE_TITLE,
        "repo_url": config.REPO_URL,
        "generated_at": format_time(generated_at),
        "total_cities": len(CITIES),
    }

    # Home page.
    index_html = env.get_template("index.html").render(root=".", **common, **build_index_context(result, run_status))
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")

    # Shared tables for the city pages, loaded once.
    climate_daily = store.read_table("weather/daily_365.csv")
    forecast = store.read_table("weather/forecast.csv")
    rank_history = store.load_history("rankings")
    traffic_daily = daily_congestion(store.load_history(TRAFFIC_HISTORY))

    city_template = env.get_template("city.html")
    for slug in result.overall.index:
        context = build_city_context(slug, result, climate_daily, forecast, rank_history, traffic_daily)
        html = city_template.render(root="..", **common, **context)
        (docs_dir / "city" / f"{slug}.html").write_text(html, encoding="utf-8")
