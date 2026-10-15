"""The list of cities we rank: the 20 largest Canadian metro areas (CMAs).

A "census metropolitan area" (CMA) is Statistics Canada's definition of a city
plus its commuter belt. Most of our statistics (crime, jobs, population, rent)
are published per CMA, so each City here represents a whole CMA, while the
latitude/longitude point at its downtown core (used for weather, air quality,
amenities and traffic sampling).

Order = population rank from the 2021 Census.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class City:
    """One ranked metro area.

    slug       : short id used in file names, URLs and every data file ("toronto").
    name       : display name on the dashboard.
    cma_name   : official StatCan CMA name, shown as a subtitle.
    province   : two-letter province code.
    latitude / longitude : downtown reference point.
    timezone   : IANA timezone, used for weather days and traffic rush-hour checks.
    """

    slug: str
    name: str
    cma_name: str
    province: str
    latitude: float
    longitude: float
    timezone: str


CITIES: tuple[City, ...] = (
    City("toronto", "Toronto", "Toronto", "ON", 43.6532, -79.3832, "America/Toronto"),
    City("montreal", "Montréal", "Montréal", "QC", 45.5017, -73.5673, "America/Toronto"),
    City("vancouver", "Vancouver", "Vancouver", "BC", 49.2827, -123.1207, "America/Vancouver"),
    City("ottawa", "Ottawa", "Ottawa–Gatineau", "ON", 45.4215, -75.6972, "America/Toronto"),
    City("calgary", "Calgary", "Calgary", "AB", 51.0447, -114.0719, "America/Edmonton"),
    City("edmonton", "Edmonton", "Edmonton", "AB", 53.5461, -113.4938, "America/Edmonton"),
    City("quebec-city", "Québec City", "Québec", "QC", 46.8139, -71.2080, "America/Toronto"),
    City("winnipeg", "Winnipeg", "Winnipeg", "MB", 49.8951, -97.1384, "America/Winnipeg"),
    City("hamilton", "Hamilton", "Hamilton", "ON", 43.2557, -79.8711, "America/Toronto"),
    City("kitchener-waterloo", "Kitchener–Waterloo", "Kitchener–Cambridge–Waterloo", "ON", 43.4516, -80.4925, "America/Toronto"),
    City("london", "London", "London", "ON", 42.9849, -81.2453, "America/Toronto"),
    City("halifax", "Halifax", "Halifax", "NS", 44.6488, -63.5752, "America/Halifax"),
    City("st-catharines-niagara", "St. Catharines–Niagara", "St. Catharines–Niagara", "ON", 43.1594, -79.2469, "America/Toronto"),
    City("windsor", "Windsor", "Windsor", "ON", 42.3149, -83.0364, "America/Toronto"),
    City("oshawa", "Oshawa", "Oshawa", "ON", 43.8971, -78.8658, "America/Toronto"),
    City("victoria", "Victoria", "Victoria", "BC", 48.4284, -123.3656, "America/Vancouver"),
    City("saskatoon", "Saskatoon", "Saskatoon", "SK", 52.1332, -106.6700, "America/Regina"),
    City("regina", "Regina", "Regina", "SK", 50.4452, -104.6189, "America/Regina"),
    City("sherbrooke", "Sherbrooke", "Sherbrooke", "QC", 45.4042, -71.8929, "America/Toronto"),
    City("kelowna", "Kelowna", "Kelowna", "BC", 49.8880, -119.4960, "America/Vancouver"),
)

# Quick lookup by slug, e.g. CITIES_BY_SLUG["toronto"].
CITIES_BY_SLUG: dict[str, City] = {city.slug: city for city in CITIES}
