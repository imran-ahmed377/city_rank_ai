"""Registry of all data sources, in the order the pipeline runs them.

To add a new source: create a module in this folder that defines ``SOURCE``
(see base.py for the contract), add it to ALL_SOURCES below, and describe its
metrics in catalog.py.
"""

from __future__ import annotations

from . import air_quality, amenities, climate, crime, housing, jobs, population, traffic, weather
from .base import Source

ALL_SOURCES: tuple[Source, ...] = (
    weather.SOURCE,
    climate.SOURCE,
    air_quality.SOURCE,
    crime.SOURCE,
    jobs.SOURCE,
    population.SOURCE,
    housing.SOURCE,
    amenities.SOURCE,
    traffic.SOURCE,
)

SOURCES_BY_NAME: dict[str, Source] = {s.name: s for s in ALL_SOURCES}
