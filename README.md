# City Rank AI

Ranks **29 Canadian cities** on living standards: the largest metro areas, with Toronto split into its ten biggest GTA cities (Toronto, Mississauga, Brampton, Markham, Vaughan, Oakville, Richmond Hill, Milton, Ajax, Pickering). Each is scored on:

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
- **City pages.** Category scores and ranks, current weather and a 7-day forecast, 12 months of temperature, rain and snow charts, rank history, rush-hour congestion (every sampled day plus a Monday–Friday breakdown), and every underlying metric with its source and period.
- **Compare page.** Pick any three cities and see every score, statistic and chart side by side, with the best of the three highlighted. The selection is in the URL, so comparisons can be shared.

## Data sources

| Category | Source | Key needed? |
|---|---|---|
| Climate, current weather, air quality | [Open-Meteo](https://open-meteo.com/) (forecast, archive and air-quality APIs) | No |
| Safety | Statistics Canada – Crime Severity Index by metro area (35-10-0026-01) and by Ontario police service (35-10-0188-01) | No |
| Jobs & economy | Statistics Canada – Labour Force Survey (14-10-0459-01), Population estimates by metro area and municipality (17-10-0148-01, 17-10-0155-01) | No |
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
3. **Workflow:** [.github/workflows/city-rank.yml](.github/workflows/city-rank.yml) runs on every push to `main`, on GitHub's hourly schedule (best-effort, see below), and manually from the Actions tab. A manual run can refetch specific sources:
   `gh workflow run city-rank.yml -f only=population,crime` (or `-f force=true` for everything).
4. **Reliable hourly runs:** see the next section.

### Reliable hourly runs (cron-job.org)

GitHub treats scheduled workflows as best-effort, and in practice runs this one only every 5–7 hours. Traffic needs a sample in every rush hour, so an external free cron service triggers the workflow every hour instead. GitHub's schedule stays as a backup; duplicate runs are harmless because each city is sampled at most once per hour.

1. **Create a GitHub token that can only start this workflow.** Go to GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → *Generate new token*.
   - Repository access: **Only select repositories** → `city_rank_ai`.
   - Permissions → Repository permissions → **Actions: Read and write**. Leave everything else at "No access".
   - Pick an expiry date and put a reminder in your calendar to renew it.
2. **Create a free account at https://cron-job.org** and add a cron job:
   - URL: `https://api.github.com/repos/imran-ahmed377/city_rank_ai/actions/workflows/city-rank.yml/dispatches`
   - Schedule: every hour, at minute 5.
   - Advanced → Request method: **POST**.
   - Headers:
     - `Accept: application/vnd.github+json`
     - `Authorization: Bearer <your token>`
     - `X-GitHub-Api-Version: 2022-11-28`
   - Request body: `{"ref":"main"}`
3. **Test it** with cron-job.org's "Test run" button. GitHub answers **204 No Content** on success, and a new run appears in the repo's Actions tab within a minute.

Cost: everything here is free. Public repositories get unlimited Actions minutes; cron-job.org is free; TomTom usage stays under its free 2,500 requests/day (about 1,570 at most, with a hard stop at 2,200).

Fetched data and history are stored on the `bot/data` branch, so `main` contains only code.

## Project docs

- [SPEC.md](SPEC.md): what the system does and how scores are calculated.
- [PLAN.md](PLAN.md): progress and roadmap.
- [CLAUDE.md](CLAUDE.md): developer guide (architecture, conventions, gotchas).

## License

The code is released under the [MIT License](LICENSE). Copyright (c) 2026 Imran Ahmed.

The data shown on the site is not covered by this licence. It belongs to its providers and is used under their terms:

- Statistics Canada: [Open Licence](https://www.statcan.gc.ca/en/reference/licence)
- Open-Meteo: [CC BY 4.0](https://open-meteo.com/en/license)
- OpenStreetMap: © OpenStreetMap contributors, [ODbL](https://www.openstreetmap.org/copyright)
- TomTom: [TomTom developer terms](https://developer.tomtom.com/terms-and-conditions)
