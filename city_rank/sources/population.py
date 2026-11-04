"""Population and population growth from Statistics Canada.

Two tables (both annual, July 1 estimates, 2021 boundaries):

* 17-10-0148-01 - by census metropolitan area: used for the metro-area cities.
* 17-10-0155-01 - by census subdivision (municipality): used for the GTA cities,
  so Mississauga gets Mississauga's population rather than the whole Toronto CMA's.

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

# --- Table 2: by census subdivision (municipality), for the GTA cities -------------
CSD_PRODUCT_ID = 17100155

# Geography member IDs; this table has no other dimensions (coordinate = geography only).
CSD_GEO_IDS: dict[str, int] = {
    "toronto": 2132,        # Toronto (C), Ontario
    "mississauga": 2134,    # Mississauga (CY), Ontario
    "brampton": 2135,       # Brampton (CY), Ontario
    "markham": 2138,        # Markham (CY), Ontario
    "vaughan": 2139,        # Vaughan (CY), Ontario
    "oakville": 2142,       # Oakville (T), Ontario
    "richmond-hill": 2143,  # Richmond Hill (T), Ontario
    "milton": 2152,         # Milton (T), Ontario
    "ajax": 2154,           # Ajax (T), Ontario
    "pickering": 2160,      # Pickering (CY), Ontario
}

# For scripts/check_statcan_ids.py: every (table, slug -> member ID) mapping in this module.
STATCAN_TABLES = [(PRODUCT_ID, GEO_IDS), (CSD_PRODUCT_ID, CSD_GEO_IDS)]


def to_rows(series: dict[str, list[statcan.DataPoint]]) -> list[dict[str, Any]]:
    """Two yearly points per city -> population (latest) and growth % rows."""
    rows: list[dict[str, Any]] = []
    for slug, points in series.items():
        point = statcan.latest(points)
        if point is not None:
            rows.append(metric_row(slug, "population", point.value, point.label))
        change = statcan.pct_change(points)
        if change is not None:
            rows.append(metric_row(slug, "population_growth_pct", change[0], change[1]))
    return rows


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch the last two yearly estimates per city -> population and growth %.

    Two periods are requested so year-over-year growth can be computed.
    """
    # Metro-area cities: geography.gender.age
    cma = {
        city.slug: statcan.coordinate(GEO_IDS[city.slug], GENDER_TOTAL, AGE_ALL)
        for city in cities if city.slug in GEO_IDS
    }
    # GTA municipalities: geography only.
    csd = {city.slug: statcan.coordinate(CSD_GEO_IDS[city.slug]) for city in cities if city.slug in CSD_GEO_IDS}

    rows = to_rows(statcan.fetch_series(session, PRODUCT_ID, cma, latest_n=2))
    rows += to_rows(statcan.fetch_series(session, CSD_PRODUCT_ID, csd, latest_n=2))
    return rows_to_frame(rows)


SOURCE = Source(
    name="population",
    ttl_hours=24 * 7,
    fetch=fetch,
    title="Statistics Canada – Population estimates (17-10-0148-01, 17-10-0155-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710014801",
)
