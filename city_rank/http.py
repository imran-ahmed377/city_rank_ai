"""Shared HTTP session with automatic retries.

Public APIs occasionally return 429 (rate limited) or 5xx (temporarily down).
Instead of failing the whole daily run, the session retries those responses with
exponential backoff (1s, 2s, 4s, 8s ...).
"""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import USER_AGENT


def build_session(retries: int = 4) -> requests.Session:
    """Create a requests.Session that retries transient failures ``retries`` times."""
    retry = Retry(
        total=retries,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        # POST is included because StatCan and Overpass use POST for *read-only*
        # queries, so repeating them is safe.
        allowed_methods={"GET", "POST"},
        # Return the final failed response instead of raising inside urllib3;
        # callers then call response.raise_for_status() and get a clear error.
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session
