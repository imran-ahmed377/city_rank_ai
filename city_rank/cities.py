"""The list of places we rank: Canada's 20 largest metro areas, with Toronto split
into its 10 largest municipalities (the GTA) - 29 places in total.

A "census metropolitan area" (CMA) is Statistics Canada's definition of a city
plus its commuter belt. Most of our statistics (crime, jobs, population, rent)
are published per CMA, so each City here normally represents a whole CMA, while
the latitude/longitude point at its downtown core (used for weather, air quality,
amenities and traffic sampling).

The Toronto CMA is too big and varied to rank as one place, so it is split into
its largest municipalities (GTA_SLUGS). For those, data comes from the most
local level StatCan publishes:
    population  -> the municipality itself (census subdivision)
    crime       -> its police service (Toronto, Peel, York, Halton, Durham)
    jobs, rent  -> the whole Toronto CMA (shared, labelled "Toronto metro")
    weather, air, amenities, traffic -> the municipality's own location

Order = population rank from the 2021 Census (GTA cities in place of Toronto).
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
    # --- Greater Toronto Area: municipalities of the Toronto CMA -------------------
    City("toronto", "Toronto", "Toronto", "ON", 43.6532, -79.3832, "America/Toronto"),
    City("mississauga", "Mississauga", "Toronto", "ON", 43.5890, -79.6441, "America/Toronto"),
    City("brampton", "Brampton", "Toronto", "ON", 43.6853, -79.7599, "America/Toronto"),
    City("markham", "Markham", "Toronto", "ON", 43.8564, -79.3375, "America/Toronto"),
    City("vaughan", "Vaughan", "Toronto", "ON", 43.7942, -79.5268, "America/Toronto"),
    City("oakville", "Oakville", "Toronto", "ON", 43.4675, -79.6877, "America/Toronto"),
    City("richmond-hill", "Richmond Hill", "Toronto", "ON", 43.8828, -79.4403, "America/Toronto"),
    City("milton", "Milton", "Toronto", "ON", 43.5183, -79.8774, "America/Toronto"),
    City("ajax", "Ajax", "Toronto", "ON", 43.8509, -79.0204, "America/Toronto"),
    City("pickering", "Pickering", "Toronto", "ON", 43.8384, -79.0868, "America/Toronto"),
    # --- Other metro areas (whole CMAs) ----------------------------------------------
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

# The GTA municipalities (all inside the Toronto CMA). Sources use this to know
# when a value is shared Toronto-metro data rather than the city's own.
GTA_SLUGS: frozenset[str] = frozenset(
    ("toronto", "mississauga", "brampton", "markham", "vaughan", "oakville",
     "richmond-hill", "milton", "ajax", "pickering")
)
TORONTO_METRO_NOTE = "Toronto metro"   # appended to the period of shared values


def metro_period(slug: str, period: str) -> str:
    """Label a value that a GTA city shares with the whole Toronto CMA.

    '2026-09' -> '2026-09 · Toronto metro' for GTA cities; unchanged for others.
    """
    return f"{period} · {TORONTO_METRO_NOTE}" if slug in GTA_SLUGS else period
