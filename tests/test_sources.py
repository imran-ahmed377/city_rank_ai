"""Tests for the parsing logic of each data source (no network calls)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pandas as pd
import pytest

from city_rank.catalog import METRICS_BY_KEY
from city_rank.cities import CITIES, CITIES_BY_SLUG
from city_rank.sources import ALL_SOURCES, air_quality, amenities, climate, crime, housing, jobs, population, statcan, traffic

TORONTO = CITIES_BY_SLUG["toronto"]


# --------------------------------------------------------------------------- StatCan
def test_coordinate_is_padded_to_ten_members():
    assert statcan.coordinate(19, 1) == "19.1.0.0.0.0.0.0.0.0"
    with pytest.raises(ValueError):
        statcan.coordinate()


@pytest.mark.parametrize(
    "ref, freq, expected",
    [("2025-01-01", 12, "2025"), ("2026-09-01", 6, "2026-09"), ("2026-04-01", 9, "2026-Q2")],
)
def test_period_label(ref, freq, expected):
    assert statcan.period_label(ref, freq) == expected


def test_parse_response_keys_by_coordinate_and_skips_failures():
    # Results deliberately out of order and with one failure, like the real WDS.
    payload = [
        {"status": "SUCCESS", "object": {"coordinate": "2.1.0.0.0.0.0.0.0.0", "vectorDataPoint": [
            {"refPer": "2025-01-01", "value": 70.0, "frequencyCode": 12},
            {"refPer": "2024-01-01", "value": 65.0, "frequencyCode": 12},
        ]}},
        {"status": "FAILED", "object": "Invalid coordinate"},
        {"status": "SUCCESS", "object": {"coordinate": "1.1.0.0.0.0.0.0.0.0", "vectorDataPoint": [
            {"refPer": "2025-01-01", "value": None, "frequencyCode": 12},
        ]}},
    ]
    series = statcan.parse_response(payload)
    assert set(series) == {"1.1.0.0.0.0.0.0.0.0", "2.1.0.0.0.0.0.0.0.0"}
    points = series["2.1.0.0.0.0.0.0.0.0"]
    assert [p.ref_period for p in points] == ["2024-01-01", "2025-01-01"]  # sorted oldest first
    assert statcan.latest(series["1.1.0.0.0.0.0.0.0.0"]) is None          # suppressed value


def test_pct_change():
    points = [statcan.DataPoint("2024-01-01", 100.0, 12), statcan.DataPoint("2025-01-01", 103.0, 12)]
    assert statcan.pct_change(points) == (3.0, "2024–2025")
    assert statcan.pct_change(points[:1]) is None


@pytest.mark.parametrize("module", [crime, jobs, population, housing])
def test_statcan_geo_ids_cover_known_cities(module):
    # Every ID refers to a configured city; only Oshawa may be missing (crime table).
    assert set(module.GEO_IDS) <= set(CITIES_BY_SLUG)
    missing = set(CITIES_BY_SLUG) - set(module.GEO_IDS)
    assert missing <= {"oshawa"}


# --------------------------------------------------------------------------- Climate
def test_climate_summary_counts_thresholds():
    daily = pd.DataFrame(
        {
            "temp_max_c": [31.0, 10.0, -15.0],
            "temp_min_c": [20.0, 0.0, -25.0],
            "precip_mm": [0.0, 5.0, 1.0],
            "snowfall_cm": [0.0, 0.0, 4.0],
            "sunshine_h": [10.0, 5.0, 2.5],
        }
    )
    values = {r["metric"]: r["value"] for r in climate.summarise(TORONTO, daily, "p")}
    assert values["hot_days"] == 1
    assert values["cold_days"] == 1
    assert values["wet_days"] == 2
    assert values["snowfall_cm"] == 4.0
    assert values["sunshine_hours"] == 18.0  # rounded to whole hours


def test_climate_window_ends_yesterday():
    start, end = climate.date_window(date(2026, 10, 14))
    assert end == "2026-10-13"
    assert (date.fromisoformat(end) - date.fromisoformat(start)).days == climate.WINDOW_DAYS - 1


# --------------------------------------------------------------------------- Air quality
def test_air_quality_ignores_forecast_hours():
    payload = {
        "hourly": {"time": ["2026-10-14T10:00", "2026-10-14T11:00", "2026-10-14T12:00"], "pm2_5": [10.0, 20.0, 99.0]},
        "current": {"time": "2026-10-14T11:00", "us_aqi": 42},
    }
    values = {r["metric"]: r["value"] for r in air_quality.parse(TORONTO, payload)}
    assert values["pm25_mean_90d"] == 15.0  # the 12:00 forecast hour is excluded
    assert values["us_aqi_current"] == 42


# --------------------------------------------------------------------------- Amenities
def test_amenities_query_and_parse():
    query = amenities.build_query(TORONTO)
    assert query.count("out count;") == len(amenities.FEATURES)
    payload = {"elements": [{"type": "count", "tags": {"total": str(n)}} for n in (5, 6, 7, 8)]}
    rows = amenities.parse_counts(TORONTO, payload, "2026-10-14")
    assert [r["value"] for r in rows] == [5, 6, 7, 8]
    with pytest.raises(ValueError):
        amenities.parse_counts(TORONTO, {"elements": []}, "x")


# --------------------------------------------------------------------------- Traffic
def test_sample_points_surround_the_centre():
    points = traffic.sample_points(TORONTO)
    assert len(points) == 1 + len(traffic.COMPASS_BEARINGS)
    north = points[1]
    assert north[0] > TORONTO.latitude and north[1] == pytest.approx(TORONTO.longitude)


@pytest.mark.parametrize(
    "utc, expected",
    [
        (datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc), True),   # Wed 08:00 in Toronto (EDT)
        (datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc), False),  # Wed 13:00 - midday
        (datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc), True),   # Wed 17:00
        (datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc), False),  # Saturday
    ],
)
def test_rush_hour_detection(utc, expected):
    assert traffic.in_rush_hour(TORONTO, utc) is expected


def test_congestion_average_filters_bad_readings():
    now = datetime(2026, 10, 14, 22, tzinfo=timezone.utc)
    samples = pd.DataFrame(
        {
            "sampled_at_utc": ["2026-10-14T21:00:00Z"] * 4 + ["2026-08-01T21:00:00Z"],
            "city": ["toronto"] * 5,
            "point": [0, 1, 2, 3, 4],
            "current_speed_kmh": [30, 60, 10, 10, 10],
            "free_flow_speed_kmh": [60, 60, 60, 60, 60],
            "confidence": [1.0, 1.0, 0.2, 1.0, 1.0],   # point 2: low confidence
            "road_closure": [False, False, False, True, False],  # point 3: closed
        }
    )
    summary = traffic.congestion_by_city(samples, now)
    row = summary.iloc[0]
    # Only points 0 (50% slower) and 1 (0%) count; point 4 is outside the 30-day window.
    assert row["congestion_pct"] == pytest.approx(25.0)
    assert row["samples"] == 2


# --------------------------------------------------------------------------- Registry / catalog
def test_every_catalog_metric_has_a_registered_source():
    names = {s.name for s in ALL_SOURCES}
    assert {m.source for m in METRICS_BY_KEY.values()} <= names


def test_city_slugs_are_unique():
    assert len({c.slug for c in CITIES}) == len(CITIES) == 20
