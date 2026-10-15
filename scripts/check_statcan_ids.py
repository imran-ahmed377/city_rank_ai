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


def main() -> int:
    session = build_session()
    problems = 0
    for module in (crime, jobs, population, housing):
        response = session.post(f"{WDS_BASE}/getCubeMetadata", json=[{"productId": module.PRODUCT_ID}], timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        meta = response.json()[0]["object"]
        names = {m["memberId"]: m["memberNameEn"] for m in meta["dimension"][0]["member"]}
        print(f"\n{module.PRODUCT_ID}  {meta['cubeTitleEn']}")
        for slug, member_id in module.GEO_IDS.items():
            city = CITIES_BY_SLUG[slug]
            statcan_name = names.get(member_id, "<missing>")
            # The first word of the CMA name should appear in StatCan's label.
            ok = simplify(city.cma_name.split("–")[0]) in simplify(statcan_name)
            problems += not ok
            print(f"  {'ok ' if ok else '!! '} {city.cma_name:32} -> {member_id:>4}: {statcan_name}")
    print(f"\n{problems} possible mismatch(es)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
