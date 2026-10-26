# City Rank AI

Ranks the **20 largest Canadian metro areas** on living standards:

- safety
- jobs and economy
- housing cost
- climate
- air quality
- traffic
- amenities

All data comes from public APIs. A GitHub Actions workflow refreshes the data and republishes the dashboard every hour.

**Live dashboard:** https://imran-ahmed377.github.io/city_rank_ai/

## What's on the site

- **Rankings page.** An overall score (0–100) and seven category scores per city. Sliders let you set your own priorities, and the table re-ranks instantly.
- **City pages.** Category scores and ranks, current weather and a 7-day forecast, 12 months of temperature, rain and snow charts, rank history, rush-hour congestion, and every underlying metric with its source and period.

## Data sources

| Category | Source | Key needed? |
|---|---|---|
| Climate, current weather, air quality | [Open-Meteo](https://open-meteo.com/) (forecast, archive and air-quality APIs) | No |
| Safety | Statistics Canada – Crime Severity Index (35-10-0026-01) | No |
| Jobs & economy | Statistics Canada – Labour Force Survey (14-10-0459-01), Population estimates (17-10-0148-01) | No |
| Housing cost | CMHC average rents via Statistics Canada (34-10-0133-01) | No |
| Amenities | OpenStreetMap via the Overpass API | No |
| Traffic | [TomTom Traffic Flow API](https://developer.tomtom.com/) | Yes (free tier) |

The scoring method is explained on the site and in [SPEC.md](SPEC.md).

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m pytest -q                # tests
python -m city_rank                # fetch data, score, build docs/
```

Then open `docs/index.html` in your browser.

Useful options:

| Command | What it does |
|---|---|
| `python -m city_rank --no-fetch` | Rebuild the site from stored data only. |
| `python -m city_rank --only crime,jobs` | Refresh specific sources. |
| `python -m city_rank --force` | Refetch everything. |
| `TOMTOM_API_KEY=... python -m city_rank` | Enable traffic sampling (only during weekday rush hours). |

## Automation setup

1. **GitHub Pages:** Settings → Pages → Source: **GitHub Actions**.
2. **TomTom key:**
   1. Create a free key at https://developer.tomtom.com/.
   2. Add it in Settings → Secrets and variables → Actions → **New repository secret**, named `TOMTOM_API_KEY`.
3. **Workflow:** [.github/workflows/city-rank.yml](.github/workflows/city-rank.yml) runs every hour, on every push to `main`, and manually from the Actions tab.

Fetched data and history are stored on the `bot/data` branch, so `main` contains only code.

## Project docs

- [SPEC.md](SPEC.md): what the system does and how scores are calculated.
- [PLAN.md](PLAN.md): progress and roadmap.
- [CLAUDE.md](CLAUDE.md): developer guide (architecture, conventions, gotchas).
