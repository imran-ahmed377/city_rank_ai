"""Population and population growth from Statistics Canada.

Table 17-10-0148-01 "Population estimates, July 1, by census metropolitan area
and census agglomeration, 2021 boundaries" (annual).

* population            - latest estimate (info only, shown on city pages)
* population_growth_pct - change over the latest year (ranked, higher is better:
                          people move where the jobs and opportunities are)
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store
from . import statcan
from .base import Source, metric_row, rows_to_frame

PRODUCT_ID = 17100148

# Geography dimension member IDs (dimension 1).
GEO_IDS: dict[str, int] = {
    "halifax": 5,                 # Halifax (CMA), Nova Scotia
    "quebec-city": 10,            # Québec (CMA), Quebec
    "sherbrooke": 11,             # Sherbrooke (CMA), Quebec
    "montreal": 14,               # Montréal (CMA), Quebec
    "ottawa": 15,                 # Ottawa - Gatineau (CMA), Ontario/Quebec
    "oshawa": 21,                 # Oshawa (CMA), Ontario
    "toronto": 22,                # Toronto (CMA), Ontario
    "hamilton": 23,               # Hamilton (CMA), Ontario
    "st-catharines-niagara": 24,  # St. Catharines - Niagara (CMA), Ontario
    "kitchener-waterloo": 25,     # Kitchener - Cambridge - Waterloo (CMA), Ontario
    "london": 28,                 # London (CMA), Ontario
    "windsor": 29,                # Windsor (CMA), Ontario
    "winnipeg": 33,               # Winnipeg (CMA), Manitoba
    "regina": 34,                 # Regina (CMA), Saskatchewan
    "saskatoon": 35,              # Saskatoon (CMA), Saskatchewan
    "calgary": 37,                # Calgary (CMA), Alberta
    "edmonton": 39,               # Edmonton (CMA), Alberta
    "kelowna": 40,                # Kelowna (CMA), British Columbia
    "vancouver": 44,              # Vancouver (CMA), British Columbia
    "victoria": 45,               # Victoria (CMA), British Columbia
}

GENDER_TOTAL = 1      # Dimension 2: "Total - gender"
AGE_ALL = 1           # Dimension 3: "All ages"


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch the last two yearly estimates per city -> population and growth %."""
    coordinates = {
        city.slug: statcan.coordinate(GEO_IDS[city.slug], GENDER_TOTAL, AGE_ALL)
        for city in cities
        if city.slug in GEO_IDS
    }
    # Two periods so we can compute year-over-year growth.
    series = statcan.fetch_series(session, PRODUCT_ID, coordinates, latest_n=2)

    rows: list[dict[str, Any]] = []
    for slug, points in series.items():
        point = statcan.latest(points)
        if point is not None:
            rows.append(metric_row(slug, "population", point.value, point.label))
        change = statcan.pct_change(points)
        if change is not None:
            rows.append(metric_row(slug, "population_growth_pct", change[0], change[1]))
    return rows_to_frame(rows)


SOURCE = Source(
    name="population",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="Statistics Canada – Population estimates (17-10-0148-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710014801",
)
