"""Labour market indicators from the Statistics Canada Labour Force Survey.

Table 14-10-0459-01 "Labour force characteristics by census metropolitan area,
three-month moving average, seasonally adjusted" (monthly).

* unemployment_rate - lower is better
* employment_rate   - higher is better
"""

from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
import requests

from ..cities import City
from ..store import Store
from . import statcan
from .base import Source, metric_row, rows_to_frame

PRODUCT_ID = 14100459

# Geography dimension member IDs (dimension 1).
GEO_IDS: dict[str, int] = {
    "halifax": 6,                 # Halifax, Nova Scotia
    "quebec-city": 13,            # Québec, Quebec
    "sherbrooke": 14,             # Sherbrooke, Quebec
    "montreal": 17,               # Montréal, Quebec
    "ottawa": 19,                 # Ottawa-Gatineau, Ontario/Quebec
    "oshawa": 25,                 # Oshawa, Ontario
    "toronto": 26,                # Toronto, Ontario
    "hamilton": 27,               # Hamilton, Ontario
    "st-catharines-niagara": 28,  # St. Catharines-Niagara, Ontario
    "kitchener-waterloo": 29,     # Kitchener-Cambridge-Waterloo, Ontario
    "london": 32,                 # London, Ontario
    "windsor": 33,                # Windsor, Ontario
    "winnipeg": 38,               # Winnipeg, Manitoba
    "regina": 40,                 # Regina, Saskatchewan
    "saskatoon": 41,              # Saskatoon, Saskatchewan
    "calgary": 44,                # Calgary, Alberta
    "edmonton": 46,               # Edmonton, Alberta
    "kelowna": 48,                # Kelowna, British Columbia
    "vancouver": 52,              # Vancouver, British Columbia
    "victoria": 53,               # Victoria, British Columbia
}

# Dimension 2 "Labour force characteristics" member -> our metric key.
CHARACTERISTICS = {
    5: "unemployment_rate",
    7: "employment_rate",
}
STATISTIC_ESTIMATE = 1        # Dimension 3: "Estimate" (not the standard error)
DATA_TYPE_SEASONAL_ADJ = 1    # Dimension 4: "Seasonally adjusted"


def fetch(session: requests.Session, cities: Sequence[City], store: Store) -> pd.DataFrame:
    """Fetch the latest unemployment and employment rates."""
    # Coordinate = geography.characteristic.statistic.data_type
    coordinates = {
        (city.slug, metric): statcan.coordinate(GEO_IDS[city.slug], char_id, STATISTIC_ESTIMATE, DATA_TYPE_SEASONAL_ADJ)
        for city in cities
        if city.slug in GEO_IDS
        for char_id, metric in CHARACTERISTICS.items()
    }
    series = statcan.fetch_series(session, PRODUCT_ID, coordinates, latest_n=1)

    rows: list[dict[str, Any]] = []
    for (slug, metric), points in series.items():
        point = statcan.latest(points)
        if point is not None:
            rows.append(metric_row(slug, metric, point.value, point.label))
    return rows_to_frame(rows)


SOURCE = Source(
    name="jobs",
    ttl_hours=24,
    fetch=fetch,
    title="Statistics Canada – Labour Force Survey (14-10-0459-01)",
    url="https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410045901",
)
