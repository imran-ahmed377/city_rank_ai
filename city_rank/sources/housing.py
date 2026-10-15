"""Rental housing cost from CMHC, published through Statistics Canada.

Table 34-10-0133-01 "Canada Mortgage and Housing Corporation, average rents for
areas with a population of 10,000 and over" (annual, October survey).

* rent_2br        - average monthly rent for a two-bedroom unit (lower is better)
* rent_change_pct - year-over-year change in that rent (lower is better)
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store
from . import statcan
from .base import Source, metric_row, rows_to_frame

PRODUCT_ID = 34100133

# Geography dimension member IDs (dimension 1).
GEO_IDS: dict[str, int] = {
    "halifax": 10,                 # Halifax, Nova Scotia
    "montreal": 46,                # Montréal, Quebec
    "quebec-city": 48,             # Québec, Quebec
    "sherbrooke": 56,              # Sherbrooke, Quebec
    "hamilton": 85,                # Hamilton, Ontario
    "kitchener-waterloo": 92,      # Kitchener-Cambridge-Waterloo, Ontario
    "london": 96,                  # London, Ontario
    "oshawa": 104,                 # Oshawa, Ontario
    "ottawa": 105,                 # Ottawa-Gatineau, Ontario/Quebec
    "st-catharines-niagara": 117,  # St. Catharines-Niagara, Ontario
    "toronto": 125,                # Toronto, Ontario
    "windsor": 128,                # Windsor, Ontario
    "winnipeg": 134,               # Winnipeg, Manitoba
    "regina": 140,                 # Regina, Saskatchewan
    "saskatoon": 141,              # Saskatoon, Saskatchewan
    "calgary": 146,                # Calgary, Alberta
    "edmonton": 148,               # Edmonton, Alberta
    "kelowna": 169,                # Kelowna, British Columbia
    "vancouver": 184,              # Vancouver, British Columbia
    "victoria": 186,               # Victoria, British Columbia
}

STRUCTURE_ROW_AND_APARTMENT = 3   # Dimension 2: "Row and apartment structures of three units and over"
UNIT_TWO_BEDROOM = 3              # Dimension 3: "Two bedroom units"


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch the last two yearly 2-bedroom rents -> rent level and change %."""
    coordinates = {
        city.slug: statcan.coordinate(GEO_IDS[city.slug], STRUCTURE_ROW_AND_APARTMENT, UNIT_TWO_BEDROOM)
        for city in cities
        if city.slug in GEO_IDS
    }
    series = statcan.fetch_series(session, PRODUCT_ID, coordinates, latest_n=2)

    rows: list[dict[str, Any]] = []
    for slug, points in series.items():
        point = statcan.latest(points)
        if point is not None:
            rows.append(metric_row(slug, "rent_2br", point.value, point.label))
        change = statcan.pct_change(points)
        if change is not None:
            rows.append(metric_row(slug, "rent_change_pct", change[0], change[1]))
    return rows_to_frame(rows)


SOURCE = Source(
    name="housing",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="CMHC average rents via Statistics Canada (34-10-0133-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410013301",
)
