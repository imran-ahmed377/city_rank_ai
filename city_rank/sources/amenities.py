"""Amenity counts from OpenStreetMap, queried through the Overpass API.

For each city we count features within RADIUS_M metres of downtown:

* parks_10km          leisure=park
* healthcare_10km     amenity=hospital | clinic | doctors
* schools_10km        amenity=school
* transit_stops_10km  public_transport=platform (bus/tram/train stops)

Every city is measured over the same circle, so the counts are directly
comparable (no per-capita adjustment needed). OSM is community-mapped, so
counts reflect mapping completeness as well as reality - good enough for a
relative comparison, which is why Amenities has a low default weight.

Refreshed weekly (map data changes slowly and Overpass is a shared free service).
Docs: https://wiki.openstreetmap.org/wiki/Overpass_API
"""

from __future__ import annotations

import time
from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..config import HTTP_TIMEOUT
from ..http import build_session
from ..store import Store, utc_now
from .base import Source, for_each_city, metric_row, rows_to_frame

# Public Overpass servers, tried in order. The main server is often overloaded
# (HTTP 504); the Kumi Systems mirror is a well-known public fallback.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
RADIUS_M = 10_000
PAUSE_BETWEEN_CITIES_S = 2  # be polite to the shared Overpass server

# metric key -> Overpass filter. Order matters: results come back in this order.
FEATURES: dict[str, str] = {
    "parks_10km": 'nwr["leisure"="park"]',
    "healthcare_10km": 'nwr["amenity"~"^(hospital|clinic|doctors)$"]',
    "schools_10km": 'nwr["amenity"="school"]',
    "transit_stops_10km": 'node["public_transport"="platform"]',
}


def build_query(city: City) -> str:
    """Overpass QL: one 'out count' statement per feature around the city centre."""
    around = f"(around:{RADIUS_M},{city.latitude},{city.longitude})"
    statements = "\n".join(f"{selector}{around};out count;" for selector in FEATURES.values())
    return f"[out:json][timeout:120];\n{statements}"


def parse_counts(city: City, payload: dict[str, Any], period: str) -> list[dict[str, Any]]:
    """Read the 'count' elements (one per feature, same order as FEATURES)."""
    counts = [el for el in payload.get("elements", []) if el.get("type") == "count"]
    if len(counts) != len(FEATURES):
        raise ValueError(f"expected {len(FEATURES)} counts, got {len(counts)}")
    return [
        metric_row(city, metric, int(element["tags"]["total"]), period)
        for metric, element in zip(FEATURES, counts)
    ]


def run_query(session: requests.Session, query: str) -> dict[str, Any]:
    """POST the query to each Overpass endpoint in turn until one succeeds."""
    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = session.post(endpoint, data={"data": query}, timeout=HTTP_TIMEOUT + 60)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - try the next server
            errors.append(f"{endpoint}: {exc}")
    raise RuntimeError("all Overpass endpoints failed: " + " | ".join(errors))


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Pipeline entry point: one Overpass query per city."""
    period = utc_now().strftime("%Y-%m-%d")  # date we counted (OSM snapshot)

    # Overpass gets its own session with a single retry: when the main server is
    # overloaded, repeated retries just waste minutes - falling back to the mirror is faster.
    overpass_session = build_session(retries=1)

    def one_city(city: City) -> list[dict[str, Any]]:
        payload = run_query(overpass_session, build_query(city))
        time.sleep(PAUSE_BETWEEN_CITIES_S)
        return parse_counts(city, payload, period)

    return rows_to_frame(for_each_city(cities, one_city, "amenities"))


SOURCE = Source(
    name="amenities",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="OpenStreetMap via Overpass API",
    url="https://wiki.openstreetmap.org/wiki/Overpass_API",
)
