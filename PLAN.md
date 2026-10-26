# City Rank AI — Plan

This file tracks what has been built and what comes next. Tick items off as they land.

## Phase 0: Starting point (done)

- [x] A single-script weather dashboard for 8 cities, using the Open-Meteo forecast and archive APIs.
- [x] A daily GitHub Actions run that pushes data to a bot branch and deploys to GitHub Pages.

## Phase 1: City ranking v2 (done, 2026-10-14)

### Restructure
- [x] Renamed the repository from `weathertracker-ai` to `city_rank_ai`.
- [x] Replaced `weather_dashboard.py` with the `city_rank/` package: sources, store, catalog, scoring, dashboard and pipeline.
- [x] Every module and function is commented, so the code can be read later without outside context.
- [x] Added CLAUDE.md, SPEC.md and PLAN.md.

### Cities
- [x] Expanded to the 20 largest CMAs.

### Data sources (each one isolated, with per-city failure handling)
- [x] Current weather and 7-day forecast (Open-Meteo).
- [x] Past-year climate metrics and daily chart data (Open-Meteo archive).
- [x] Air quality: 90-day PM2.5 mean and current AQI (Open-Meteo).
- [x] Crime Severity Index (StatCan 35-10-0026-01).
- [x] Unemployment and employment rate (StatCan Labour Force Survey 14-10-0459-01).
- [x] Population and growth (StatCan 17-10-0148-01).
- [x] Two-bedroom rent and rent change (CMHC via StatCan 34-10-0133-01).
- [x] Amenities: parks, healthcare, schools and transit stops (OpenStreetMap / Overpass, with a fallback mirror).
- [x] Rush-hour traffic congestion (TomTom Traffic Flow, key stored as a GitHub secret).

### Pipeline and scoring
- [x] Refresh intervals per source, retrying only the cities that are missing data.
- [x] 0–100 scoring: metric, then category, then weighted overall, with re-weighting when data is missing.

### Website
- [x] Rankings home page with weight sliders (defaults plus visitor adjustments).
- [x] A detail page per city, including the 12-month weather charts.
- [x] Light and dark mode. Every chart has a table equivalent.
- [x] Light/dark toggle button (remembers the choice, otherwise follows the OS) and a layered skyline silhouette background with frosted-glass cards (2026-10-26).

### Automation and fixes
- [x] Workflow runs tests first and restores `data/` from `bot/data`.
  - This fixes a bug in v1, where the observation history was reset on every run.
- [x] pytest suite (offline, no network).

## Phase 2: Next up

- [x] Switched the workflow to hourly runs (2026-10-26). GitHub was starting scheduled runs 2–4 hours late, so Eastern and Atlantic cities never got a rush-hour traffic sample. `bot/data` now stores only `data/`.
- [ ] **Add the `TOMTOM_API_KEY` secret** in GitHub (Settings → Secrets and variables → Actions). Until then, traffic shows "no data".
- [ ] After the first successful run, delete the old `bot/weather-data` branch. It's no longer used.
- [ ] Check the live site after 1–2 days. The rank history and traffic charts need a few runs before they fill in.
- [ ] Add a map view on the home page: city markers colored by overall score.
- [ ] Add a CMHC rental vacancy rate (housing availability). Check that a StatCan table covers all 20 CMAs.
- [ ] Add healthcare access: the "% with a regular healthcare provider" by health region. This needs a mapping from health region to CMA.
- [ ] Add income or affordability, i.e. rent-to-income. This needs a source that covers all 20 CMAs (Census 2021 profile, or the T1FF tables).
- [ ] Weather extremes: count days with poor air quality (AQI > 100) over the year, not just the mean.
- [ ] Show trend arrows in the rankings table (rank change versus 7 days ago, from `history/rankings.csv`).
- [ ] Shareable weight presets in the URL (for example `#safety=8&housing=10`).

## Phase 3: Later / ideas

- [ ] AI-written daily summary of rank changes. The user decided against this for now; it would need an Anthropic API key secret.
- [ ] French version of the site.
- [ ] More cities (all 41 CMAs). Several StatCan tables don't cover the smaller ones.
- [ ] Data-quality alerts: open a GitHub issue automatically when a source fails 3 runs in a row.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-14 | 20 largest CMAs | A good balance of coverage and data availability. |
| 2026-10-14 | TomTom free tier for traffic | The only practical live congestion source. It fits the free quota with rush-hour-only sampling. |
| 2026-10-14 | Free-key APIs allowed | Keys are stored as GitHub secrets. |
| 2026-10-14 | Default weights plus visitor sliders | One clear default ranking, while staying personalizable. |
| 2026-10-14 | No AI features yet | Keep v2 focused on data. |
| 2026-10-14 | Data on the `bot/data` branch | Keeps `main` history clean; the workflow restores it on each run. |
| 2026-10-14 | Rankings page plus one page per city | Keeps pages small; per-city weather charts live on the city pages. |
| 2026-10-14 | Min-max scaling | Easy to explain ("best = 100, worst = 0"). Can be revisited if outliers dominate. |
| 2026-10-26 | Hourly workflow runs | Scheduled runs started 2–4 h late and missed rush hour. Hourly runs catch every city; Actions minutes are free for public repos. |
| 2026-10-14 | No income metric | The StatCan CMA income table covers only 8 of the 20 cities. |
