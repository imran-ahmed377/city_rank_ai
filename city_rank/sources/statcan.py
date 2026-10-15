"""Small client for the Statistics Canada Web Data Service (WDS).

StatCan publishes thousands of data tables ("cubes"). Each table has several
dimensions (Geography, Statistic, Sex, ...) and every combination of one member
per dimension is a single time series. A series is addressed by a
"coordinate": the member IDs joined by dots, always padded to 10 positions:

    Crime table 35-10-0026-01, Toronto (member 19), "Crime severity index" (member 1)
    -> coordinate "19.1.0.0.0.0.0.0.0.0"

The member IDs used by our sources were looked up once with the
getCubeMetadata endpoint and are written next to each table in the source
modules (crime.py, jobs.py, population.py, housing.py).

No API key needed. Docs: https://www.statcan.gc.ca/en/developers/wds
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Hashable, Mapping

import requests

from ..config import HTTP_TIMEOUT

log = logging.getLogger(__name__)

WDS_BASE = "https://www150.statcan.gc.ca/t1/wds/rest"
DATA_ENDPOINT = f"{WDS_BASE}/getDataFromCubePidCoordAndLatestNPeriods"

# StatCan frequency codes (subset we use) -> how to label a reference period.
FREQ_MONTHLY = 6
FREQ_QUARTERLY = 9
FREQ_ANNUAL = 12


@dataclass(frozen=True)
class DataPoint:
    """One observation of a series: its reference period and value."""

    ref_period: str        # e.g. "2026-09-01"
    value: float | None    # None when StatCan suppressed the value
    frequency: int         # StatCan frequency code

    @property
    def label(self) -> str:
        """Human-friendly period: '2026-09' (monthly), '2026-Q2', or '2025' (annual)."""
        return period_label(self.ref_period, self.frequency)


def coordinate(*member_ids: int) -> str:
    """Build a 10-position coordinate string from member IDs (missing dims = 0)."""
    if not 1 <= len(member_ids) <= 10:
        raise ValueError("a coordinate has between 1 and 10 members")
    padded = list(member_ids) + [0] * (10 - len(member_ids))
    return ".".join(str(m) for m in padded)


def period_label(ref_period: str, frequency: int) -> str:
    """Format a StatCan refPer date for display based on the series frequency."""
    year, month = ref_period[:4], ref_period[5:7]
    if frequency == FREQ_ANNUAL:
        return year
    if frequency == FREQ_QUARTERLY and month.isdigit():
        return f"{year}-Q{(int(month) - 1) // 3 + 1}"
    if frequency == FREQ_MONTHLY:
        return f"{year}-{month}"
    return ref_period


def parse_response(payload: list[dict[str, Any]]) -> dict[str, list[DataPoint]]:
    """Map coordinate -> data points (oldest first) from a WDS data response.

    The WDS does NOT return results in request order, so we key them by the
    coordinate echoed back in each result. Failed items are logged and skipped.
    """
    series: dict[str, list[DataPoint]] = {}
    for item in payload:
        obj = item.get("object") or {}
        if item.get("status") != "SUCCESS" or not isinstance(obj, dict):
            log.warning("StatCan series failed: %s", obj)
            continue
        points = [
            DataPoint(
                ref_period=str(p.get("refPer", "")),
                value=p.get("value"),
                frequency=int(p.get("frequencyCode") or 0),
            )
            for p in obj.get("vectorDataPoint") or []
        ]
        points.sort(key=lambda p: p.ref_period)
        series[str(obj.get("coordinate"))] = points
    return series


def fetch_series(
    session: requests.Session,
    product_id: int,
    coordinates: Mapping[Hashable, str],
    latest_n: int = 1,
) -> dict[Hashable, list[DataPoint]]:
    """Fetch the latest ``latest_n`` points for many series of one table in one request.

    ``coordinates`` maps any key you like (e.g. (city_slug, metric)) to a
    coordinate string; the result uses the same keys. Keys whose series failed
    are missing from the result.
    """
    if not coordinates:
        return {}
    body = [{"productId": product_id, "coordinate": coord, "latestN": latest_n} for coord in coordinates.values()]
    response = session.post(DATA_ENDPOINT, json=body, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    by_coordinate = parse_response(response.json())
    return {key: by_coordinate[coord] for key, coord in coordinates.items() if coord in by_coordinate}


# --- Small helpers used by the table modules ------------------------------------

def valid_points(points: list[DataPoint]) -> list[DataPoint]:
    """Drop suppressed (None) values."""
    return [p for p in points if p.value is not None]


def latest(points: list[DataPoint]) -> DataPoint | None:
    """Most recent non-suppressed point, or None."""
    good = valid_points(points)
    return good[-1] if good else None


def pct_change(points: list[DataPoint]) -> tuple[float, str] | None:
    """Percent change between the last two valid points, with a period label.

    Returns e.g. (3.25, "2024–2025"), or None if fewer than two points.
    """
    good = valid_points(points)
    if len(good) < 2 or not good[-2].value:
        return None
    previous, current = good[-2], good[-1]
    change = (current.value / previous.value - 1) * 100
    return round(change, 2), f"{previous.label}–{current.label}"
