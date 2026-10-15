# CLAUDE.md

Guidance for Claude Code (and humans) working in this repository.

## What this project is

**City Rank AI** ranks the 20 largest Canadian metro areas on living standards:
safety, jobs, housing cost, climate, air quality, traffic and amenities. All
data comes from public APIs.

A GitHub Actions workflow runs 4× a day. Each run fetches data, re-scores the
cities and publishes a static site to GitHub Pages.

- `SPEC.md` is the authoritative description of the behaviour.
- `PLAN.md` tracks progress and next steps. Update it when you finish or add work.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python -m pytest -q                 # run tests (offline, ~1 s)
.venv/bin/python -m city_rank                 # normal run: fetch what's stale, score, render docs/
.venv/bin/python -m city_rank --no-fetch      # re-score + re-render only (fast; use when editing templates/CSS)
.venv/bin/python -m city_rank --only crime    # force-run one or more sources (comma-separated)
.venv/bin/python -m city_rank --force         # refetch everything (amenities alone takes several minutes)
.venv/bin/python scripts/check_statcan_ids.py # verify StatCan member IDs against live metadata
```

To view the site, open `docs/index.html` in a browser. It works from disk.

Traffic needs `TOMTOM_API_KEY` in the environment. Add `TRAFFIC_FORCE=1` to sample outside rush hour.

## Architecture

```
city_rank/
  cities.py        the 20 cities (slug, name, CMA, province, downtown lat/lon, timezone)
  catalog.py       CATEGORIES (weights) + METRICS (label, unit, category, direction, source)
  sources/         one module per API; each exposes SOURCE = Source(name, ttl_hours, fetch, title, url)
    base.py        Source dataclass, metric_row(), for_each_city() (per-city failure isolation)
    statcan.py     shared StatCan WDS client (coordinates, parsing, pct_change)
    weather.py climate.py air_quality.py crime.py jobs.py population.py housing.py amenities.py traffic.py
  store.py         Store(root): metrics/<source>.csv (merge), history/*.csv (append), JSON
  scoring.py       metric score (min-max) -> category mean -> weighted overall + rank
  pipeline.py      CLI + orchestration (refresh intervals, retry missing cities, run_status.json)
  dashboard.py     builds template contexts; render_site() writes docs/
  templates/       Jinja2: base.html, index.html, city.html
  static/          style.css (color tokens, light/dark), rankings.js (sliders), city.js (Plotly charts)
tests/             pytest, offline; synthetic data + tmp_path
.github/workflows/city-rank.yml
```

**Data flow:**
1. Each `source.fetch(session, cities, store)` returns tidy rows: `city, metric, value, period`.
2. The pipeline stamps `source` and `fetched_at` on them and calls `store.save_metrics`.
3. `build_rankings(store.load_all_metrics())` scores the cities.
4. `render_site()` writes the website.

Generated folders are git-ignored on `main`:

- `data/` is the fetched and accumulated data. The workflow keeps it on the `bot/data` branch and restores it before each run.
- `docs/` is the built site, deployed to GitHub Pages as an artifact.

## Conventions

- **Comment every chunk of code.** The owner reads the code later to understand it. Every module starts with a docstring explaining what it does, where its data comes from, and any caveats. Every function has a docstring. Non-obvious blocks get a short comment explaining *why*.
- **Missing data means no row**, never an empty value (`rows_to_frame` drops NaN). Scoring treats absent rows as "no data" and re-weights.
- **Metric metadata lives only in `catalog.py`.** Sources produce values keyed by metric `key`.
- **Every source must isolate failures.** Use `for_each_city` for per-city APIs. Never let one city or one source crash the run.
- **Keep the scoring formula in sync** between `scoring.score_overall` and `static/rankings.js` `overallScore`.
- **Charts:** a single y-axis per chart (rain and snow get separate charts), colors from the CSS tokens, and a table equivalent for every chart.
- **Never log API keys.** `traffic.fetch_point` raises its own error so requests' message, which contains the URL and the key, never reaches the logs.
- Tests must not use the network.

## How to add a new data source

1. Create `city_rank/sources/<name>.py` with a module docstring, `fetch(session, cities, store) -> DataFrame`, and `SOURCE = Source(...)`. Pick `ttl_hours` to match how often the data really changes.
2. Register it in `city_rank/sources/__init__.py` `ALL_SOURCES`.
3. Add its metrics to `catalog.py`. Give each a `category` and direction to rank it, or `category=None` for info-only.
4. Add parsing tests in `tests/test_sources.py`.
5. Update `SPEC.md` §3 and `PLAN.md`.

## Gotchas

- **StatCan member IDs** are hard-coded per table (`GEO_IDS` in crime/jobs/population/housing). They were verified against `getCubeMetadata`. Re-run `scripts/check_statcan_ids.py` if values look wrong.
- **StatCan's WDS returns results out of order.** Always match them by the coordinate it echoes back.
- **Oshawa has no Crime Severity Index** (Durham Regional Police). Its missing Safety score is expected.
- **The main Overpass server often returns 504.** `amenities.py` falls back to the Kumi mirror, and the pipeline retries only the missing cities on later runs.
- **Traffic only samples during local weekday rush hours.** A manual run at midday adds no samples unless `TRAFFIC_FORCE=1`.
- **The workflow cron times are tied to the rush-hour windows** in `traffic.py`. Change them together.
