"""Crime Severity Index (CSI) from Statistics Canada.

The CSI weights each police-reported crime by its seriousness, so a city with
many minor thefts can score better than one with fewer but violent crimes.
Lower is better. Canada in 2006 = 100. The index is calculated the same way
for every geography, so the two tables below are directly comparable.

Two tables are used:

* 35-10-0026-01 - CSI by census metropolitan area (most of our cities).
* 35-10-0188-01 - CSI by police service in Ontario, for places that are not a
  whole CMA:
    - the GTA municipalities (Toronto is split into its cities; each gets the
      police service that patrols it - e.g. Mississauga and Brampton share Peel
      Regional Police, Markham/Vaughan/Richmond Hill share York Regional Police);
    - Oshawa, which has no CMA-level CSI; Durham Regional Police (which polices
      Oshawa, Whitby, Ajax, Pickering, ...) is used instead.
  The police service is added to the value's period label so it shows on the site.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store
from . import statcan
from .base import Source, metric_row, rows_to_frame

# --- Table 1: CSI by census metropolitan area ---------------------------------------
CMA_PRODUCT_ID = 35100026

# Geography dimension member IDs (dimension 1), checked against getCubeMetadata.
CMA_GEO_IDS: dict[str, int] = {
    "halifax": 6,                 # Halifax, Nova Scotia
    "quebec-city": 11,            # Québec, Quebec
    "sherbrooke": 12,             # Sherbrooke, Quebec
    "montreal": 14,               # Montréal, Quebec
    "ottawa": 17,                 # Ottawa-Gatineau, Ontario/Quebec (whole CMA)
    "hamilton": 20,               # Hamilton, Ontario
    "st-catharines-niagara": 21,  # St.Catharines-Niagara, Ontario
    "kitchener-waterloo": 22,     # Kitchener-Cambridge-Waterloo, Ontario
    "london": 23,                 # London, Ontario
    "windsor": 24,                # Windsor, Ontario
    "winnipeg": 29,               # Winnipeg, Manitoba
    "regina": 31,                 # Regina, Saskatchewan
    "saskatoon": 32,              # Saskatoon, Saskatchewan
    "calgary": 34,                # Calgary, Alberta
    "edmonton": 35,               # Edmonton, Alberta
    "vancouver": 37,              # Vancouver, British Columbia
    "victoria": 38,               # Victoria, British Columbia
    "kelowna": 48,                # Kelowna, British Columbia
}

# --- Table 2: CSI by police service in Ontario ---------------------------------------
POLICE_PRODUCT_ID = 35100188

# Police-service member IDs (dimension 1) and the name shown on the site.
TORONTO_POLICE = (200, "Toronto Police Service")            # "Toronto, Ontario, municipal"
PEEL_POLICE = (38, "Peel Regional Police")                  # "Peel Region (Mississauga/Brampton)"
YORK_POLICE = (206, "York Regional Police")                 # "York Region, Ontario, municipal"
HALTON_POLICE = (45, "Halton Regional Police")              # "Halton Region (Oakville/Burlington)"
DURHAM_POLICE = (167, "Durham Regional Police")             # "Durham Region (Oshawa/Whitby/Ajax)"

POLICE_SERVICES: dict[str, tuple[int, str]] = {
    "toronto": TORONTO_POLICE,
    "mississauga": PEEL_POLICE,
    "brampton": PEEL_POLICE,
    "markham": YORK_POLICE,
    "vaughan": YORK_POLICE,
    "richmond-hill": YORK_POLICE,
    "oakville": HALTON_POLICE,
    "milton": HALTON_POLICE,
    "ajax": DURHAM_POLICE,
    "pickering": DURHAM_POLICE,
    "oshawa": DURHAM_POLICE,
}
POLICE_GEO_IDS: dict[str, int] = {slug: member for slug, (member, _) in POLICE_SERVICES.items()}

# Statistics dimension member IDs (dimension 2; the same in both tables) -> metric key.
STATISTICS = {
    1: "crime_severity_index",
    3: "violent_crime_severity_index",
}

# For scripts/check_statcan_ids.py: every (table, slug -> member ID) mapping in this module.
STATCAN_TABLES = [(CMA_PRODUCT_ID, CMA_GEO_IDS), (POLICE_PRODUCT_ID, POLICE_GEO_IDS)]


def fetch_table(
    session: requests.Session,
    product_id: int,
    geo_ids: dict[str, int],
    cities: Sequence[City],
    notes: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Latest CSI and violent CSI from one table for the cities it covers.

    ``notes`` (slug -> text) is appended to the period, e.g. "2025 · Peel Regional Police".
    """
    # One coordinate per (city, metric): geography.statistic
    coordinates = {
        (city.slug, metric): statcan.coordinate(geo_ids[city.slug], stat_id)
        for city in cities
        if city.slug in geo_ids
        for stat_id, metric in STATISTICS.items()
    }
    series = statcan.fetch_series(session, product_id, coordinates, latest_n=1)

    rows: list[dict[str, Any]] = []
    for (slug, metric), points in series.items():
        point = statcan.latest(points)
        if point is not None:
            note = (notes or {}).get(slug)
            period = f"{point.label} · {note}" if note else point.label
            rows.append(metric_row(slug, metric, point.value, period))
    return rows


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch CSI for every city: metro areas from table 1, GTA + Oshawa from table 2."""
    rows = fetch_table(session, CMA_PRODUCT_ID, CMA_GEO_IDS, cities)
    rows += fetch_table(
        session, POLICE_PRODUCT_ID, POLICE_GEO_IDS, cities,
        notes={slug: name for slug, (_, name) in POLICE_SERVICES.items()},
    )
    return rows_to_frame(rows)


SOURCE = Source(
    name="crime",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="Statistics Canada – Crime Severity Index (35-10-0026-01, 35-10-0188-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3510002601",
)
