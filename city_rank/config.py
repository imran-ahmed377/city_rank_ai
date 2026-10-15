"""Project-wide settings: folder locations and HTTP behaviour.

Anything that more than one module needs lives here so it is defined once.
Source-specific settings (API URLs, refresh intervals) live in each source module
so you can read a source top-to-bottom without jumping around.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Folder layout -----------------------------------------------------------
# PROJECT_ROOT is the repository root (the folder that contains city_rank/).
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# data/  : everything the pipeline fetches or accumulates (CSV + JSON).
#          Not committed to main - the workflow stores it on the bot/data branch.
# docs/  : the generated static website that GitHub Pages serves.
DATA_DIR = Path(os.getenv("CITY_RANK_DATA_DIR", PROJECT_ROOT / "data"))
DOCS_DIR = Path(os.getenv("CITY_RANK_DOCS_DIR", PROJECT_ROOT / "docs"))

# Jinja2 templates and the CSS/JS files copied into docs/assets/.
TEMPLATES_DIR = PACKAGE_DIR / "templates"
STATIC_DIR = PACKAGE_DIR / "static"

# --- HTTP --------------------------------------------------------------------
# A descriptive User-Agent is polite and is required by some public APIs
# (Overpass/OpenStreetMap asks clients to identify themselves).
USER_AGENT = "city_rank_ai/2.0 (+https://github.com/imran-ahmed377/city_rank_ai)"

# Seconds to wait for a response before giving up on a single request.
# StatCan and Overpass can be slow, so this is generous.
HTTP_TIMEOUT = 90

# --- Site --------------------------------------------------------------------
SITE_TITLE = "City Rank Canada"
REPO_URL = "https://github.com/imran-ahmed377/city_rank_ai"
