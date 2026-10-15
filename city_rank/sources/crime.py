"""Crime Severity Index (CSI) from Statistics Canada.

Table 35-10-0026-01 "Crime severity index and weighted clearance rates" (annual).
The CSI weights each police-reported crime by its seriousness, so a city with
many minor thefts can score better than one with fewer but violent crimes.
Lower is better. Canada in 2006 = 100.

Known gap: Oshawa is not published as its own CMA in this table (it is policed
by Durham Regional Police), so Oshawa has no Safety score; scoring.py handles
missing categories by re-weighting the others.
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store
from . import statcan
from .base import Source, metric_row, rows_to_frame

PRODUCT_ID = 35100026

# Geography dimension member IDs (dimension 1), checked against getCubeMetadata.
GEO_IDS: dict[str, int] = {
    "halifax": 6,                 # Halifax, Nova Scotia
    "quebec-city": 11,            # Québec, Quebec
    "sherbrooke": 12,             # Sherbrooke, Quebec
    "montreal": 14,               # Montréal, Quebec
    "ottawa": 17,                 # Ottawa-Gatineau, Ontario/Quebec (whole CMA)
    "toronto": 19,                # Toronto, Ontario
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
    # "oshawa": not available (see module docstring)
}

# Statistics dimension member IDs (dimension 2) -> our metric key.
STATISTICS = {
    1: "crime_severity_index",
    3: "violent_crime_severity_index",
}


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch the latest CSI and violent CSI for every city we have an ID for."""
    # Build one coordinate per (city, metric): geography.statistic
    coordinates = {
        (city.slug, metric): statcan.coordinate(GEO_IDS[city.slug], stat_id)
        for city in cities
        if city.slug in GEO_IDS
        for stat_id, metric in STATISTICS.items()
    }
    series = statcan.fetch_series(session, PRODUCT_ID, coordinates, latest_n=1)

    # Keep the most recent valid value of each series.
    rows: list[dict[str, Any]] = []
    for (slug, metric), points in series.items():
        point = statcan.latest(points)
        if point is not None:
            rows.append(metric_row(slug, metric, point.value, point.label))
    return rows_to_frame(rows)


SOURCE = Source(
    name="crime",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="Statistics Canada – Crime Severity Index (35-10-0026-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3510002601",
)
