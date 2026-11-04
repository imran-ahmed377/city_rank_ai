"""Maintenance check: do our hard-coded StatCan member IDs still point at the right cities?

StatCan occasionally restructures tables. Run this when a StatCan source starts
returning odd values or missing cities:

    python scripts/check_statcan_ids.py

For each table it downloads the live metadata and prints our city next to the
geography name StatCan has for that member ID, flagging likely mismatches.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

# Make `city_rank` importable when run as a plain script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from city_rank.cities import CITIES_BY_SLUG  # noqa: E402
from city_rank.config import HTTP_TIMEOUT  # noqa: E402
from city_rank.http import build_session  # noqa: E402
from city_rank.sources import crime, housing, jobs, population  # noqa: E402
from city_rank.sources.statcan import WDS_BASE  # noqa: E402


def simplify(text: str) -> str:
    """Lower-case, strip accents and punctuation so 'Montréal' matches 'Montreal'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in text.lower() if ch.isalnum())


def expected_words(city, module) -> list[str]:
    """Words that should appear in StatCan's label for this city's member.

    The city's own name, its CMA name (GTA cities map to the Toronto CMA), and
    for police-service mappings the service's name (e.g. "York" for Markham).
    """
    words = [city.name.split("–")[0], city.cma_name.split("–")[0]]
    services = getattr(module, "POLICE_SERVICES", {})
    if city.slug in services:
        words.append(services[city.slug][1].split()[0])
    return [simplify(w) for w in words]


def main() -> int:
    session = build_session()
    problems = 0
    for module in (crime, jobs, population, housing):
        for product_id, geo_ids in module.STATCAN_TABLES:
            response = session.post(f"{WDS_BASE}/getCubeMetadata", json=[{"productId": product_id}], timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            meta = response.json()[0]["object"]
            names = {m["memberId"]: m["memberNameEn"] for m in meta["dimension"][0]["member"]}
            print(f"\n{product_id}  {meta['cubeTitleEn']}")
            for slug, member_id in geo_ids.items():
                city = CITIES_BY_SLUG[slug]
                statcan_name = names.get(member_id, "<missing>")
                ok = any(word in simplify(statcan_name) for word in expected_words(city, module))
                problems += not ok
                print(f"  {'ok ' if ok else '!! '} {city.name:26} -> {member_id:>5}: {statcan_name}")
    print(f"\n{problems} possible mismatch(es)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
