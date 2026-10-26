# City Rank AI — Specification

## 1. Purpose

Rank the 20 largest Canadian metro areas on **living standards** using only
public data, and publish the result as a static website that updates itself
every hour through GitHub Actions.

The ranking must be:

- **Transparent.** Every score can be traced back to a raw value, its reference period and its source.
- **Adjustable.** Visitors can change how much each category counts.
- **Robust.** One broken API never stops the update. The site always shows the newest data that could be obtained.

## 2. Cities in scope

The 20 largest census metropolitan areas (CMAs) by 2021 Census population.
They are defined in `city_rank/cities.py`:

Toronto, Montréal, Vancouver, Ottawa–Gatineau, Calgary, Edmonton, Québec,
Winnipeg, Hamilton, Kitchener–Cambridge–Waterloo, London, Halifax,
St. Catharines–Niagara, Windsor, Oshawa, Victoria, Saskatoon, Regina,
Sherbrooke, Kelowna.

Each city has two location roles:

- **The whole CMA** for StatCan statistics (crime, jobs, population, rent).
- **A downtown point** (latitude/longitude) for weather, air quality, amenities and traffic sampling.

## 3. Categories, metrics and sources

Default weights are importance levels from 0 to 10. The percentage is each weight's share of the default total of 20.

| Category | Default weight | Metric (direction) | Source | Source refresh | Our refresh |
|---|---|---|---|---|---|
| Safety | 4 (20%) | Crime Severity Index (↓), Violent CSI (↓) | StatCan 35-10-0026-01 | yearly | weekly check |
| Jobs & economy | 4 (20%) | Unemployment rate (↓), Employment rate (↑), Population growth (↑) | StatCan 14-10-0459-01, 17-10-0148-01 | monthly / yearly | daily / weekly |
| Housing cost | 4 (20%) | Average 2-bedroom rent (↓), Rent change % per year (↓) | CMHC via StatCan 34-10-0133-01 | yearly (October survey) | weekly check |
| Climate | 3 (15%) | Days below −20 °C (↓), Days above 30 °C (↓), Snowfall (↓), Wet days ≥1 mm (↓), Sunshine hours (↑) | Open-Meteo archive, past 365 days | daily | every 12 h |
| Air quality | 2 (10%) | PM2.5 90-day mean (↓) | Open-Meteo Air Quality API | hourly | every 6 h |
| Traffic | 2 (10%) | Rush-hour congestion %, 30-day mean (↓) | TomTom Traffic Flow API (free key) | live | every run (hourly) |
| Amenities | 1 (5%) | Parks, hospitals/clinics, schools, transit stops within 10 km of downtown (↑) | OpenStreetMap via Overpass | live | weekly |

**Info-only metrics** are shown on city pages but not scored:

- Population
- Average temperature
- Current US AQI
- Current temperature, humidity, wind, precipitation and conditions
- Number of traffic samples

**Known gap:** StatCan does not publish a Crime Severity Index for Oshawa (it is policed by Durham Regional Police). Oshawa therefore has no Safety score (see §4.3).

### 3.1 Traffic sampling

- **Sample points:** 9 per city, the downtown centre plus 8 compass points 4 km away. TomTom snaps each point to the nearest major road segment.
- **When:** a city is sampled only during its local weekday rush hours, 07:00–09:59 and 16:00–18:59.
- **Schedule:** the workflow runs every hour. GitHub often starts scheduled runs 2–4 hours late, so fixed times can't be relied on; with hourly runs, each city is sampled several times inside each of its rush-hour windows.
- **Per reading:** congestion % = (1 − current speed ÷ free-flow speed) × 100, clipped at 0.
- **Excluded readings:** closed roads and readings with TomTom confidence below 0.5.
- **The metric:** the mean of all valid readings over the last 30 days. Raw samples are kept for 120 days.
- **Budget:** at most about 1,080 requests a day (20 cities × 6 rush-hour runs × 9 points), against TomTom's free limit of 2,500.

## 4. Scoring

This is implemented in `city_rank/scoring.py`. Step 3 is mirrored in `city_rank/static/rankings.js`.

### 4.1 Metric score (0–100)

The score uses min-max scaling across the 20 cities:

```
score = (value − min) / (max − min) × 100
if lower is better: score = 100 − score
if max == min:      score = 50 for every city
```

### 4.2 Category score

A category score is the mean of that category's metric scores, skipping missing metrics. If a city has no metrics in a category, that category is "no data" for that city.

### 4.3 Overall score

The overall score is the weighted mean of the category scores. If a city has no data for a category, that category's weight is dropped for that city:

```
overall  = Σ (category_score × weight) / Σ weight      (over categories the city has data for)
coverage = Σ weight (available) / Σ weight (all categories with weight > 0)
rank     = position by overall, ties share the better rank (1, 2, 2, 4…)
```

When coverage is below 100%, the page shows a "Partial data" label.

Scores are **relative**: 100 means the best of the 20 cities, not perfect.

## 5. Data storage

The `data/` folder is not committed to `main`. It lives on the `bot/data` branch, and each run restores it before fetching.

```
data/
  metrics/<source>.csv           latest tidy rows: city, metric, value, period, source, fetched_at
  history/weather_observations.csv   current conditions, one row per city per run (kept forever)
  history/traffic_samples.csv        raw TomTom readings (pruned to 120 days)
  history/rankings.csv               overall score + rank per city per UTC date
  weather/daily_365.csv              daily climate table for charts
  weather/forecast.csv               next 7 days per city
  run_status.json                    outcome of each source on the last full run
```

**Merge rule:** new rows replace stored rows for the same (city, metric). Rows that were not refetched are kept, so a city whose request failed keeps its last known value.

## 6. Pipeline behaviour

The entry point is `python -m city_rank`. For each source:

1. **Fresh and complete** (data younger than its refresh interval, every city present): skip. State `cached`.
2. **Fresh but some cities have no data:** fetch only those cities. State `cached`, or `updated` if new rows arrived.
3. **Otherwise:** fetch all cities. State `updated`, `empty` or `failed`.
4. **Failures:** if one city fails, the error is logged and the other cities continue. If every city fails, or the source raises an error, the state is `failed` and the stored data is kept.

After fetching, the pipeline:

1. scores the cities,
2. appends today's ranks to `history/rankings.csv`,
3. renders `docs/`.

The process exits with a non-zero code only if no city can be scored at all.

CLI flags:

| Flag | Effect |
|---|---|
| `--force` | Ignore refresh intervals and refetch every source. |
| `--only a,b` | Run only the named sources, forced. |
| `--no-fetch` | Re-score and re-render from stored data. |
| `--log-level` | Set logging verbosity. |

Environment variables:

| Variable | Effect |
|---|---|
| `TOMTOM_API_KEY` | Enables traffic sampling. |
| `TRAFFIC_FORCE=1` | Sample traffic outside rush hour (for testing). |
| `CITY_RANK_DATA_DIR` | Override the data folder. |
| `CITY_RANK_DOCS_DIR` | Override the docs (website) folder. |

## 7. Website

The site is static, generated with Jinja2 into `docs/`, and served by GitHub Pages.

**`index.html`**
- Priority sliders (0–10 per category). Visitors' settings are saved in the browser's localStorage. There is a reset button.
- Rankings table: rank, city, overall score bar, and the 7 category scores. It is rendered server-side with the default weights, and JavaScript re-sorts it when sliders move.
- A methodology section.
- A data-sources table showing each source's state on the last run.

**`city/<slug>.html`**
- Rank and overall score, plus category score bars with the city's rank in each category.
- "Right now" tiles (weather and AQI) and a 7-day forecast.
- Charts (Plotly 2.35.2 from cdn.plot.ly): rank over time, daily high/low temperature, daily rain, daily snowfall, and rush-hour congestion.
- A monthly climate table and a table of every metric, with value, score, period and source.

**Chart rules**
- Charts follow the light/dark color tokens in `style.css`.
- A button at the top of every page switches light/dark. The choice is saved in localStorage; with no saved choice the site follows the OS setting.
- A decorative skyline silhouette sits fixed at the bottom of the window: three grey layers, the CN Tower, a Ferris wheel and a faded reflection. It is generated by `scripts/draw_skyline.py` into `templates/skyline.svg` and coloured by the `--city-far/mid/near` tokens.
- Cards, tiles and the theme button are frosted glass (translucent fill + backdrop blur + bright rim). They fall back to solid `--surface` when the browser can't blur or the visitor prefers reduced transparency.
- Every chart has a single y-axis.
- Every chart has a table or text equivalent on the page.
- Each page embeds only its own data, so pages also work when opened from disk.

## 8. Automation

The workflow is `.github/workflows/city-rank.yml`.

**Triggers:** a push to `main`, an hourly cron run, and manual dispatch.

**Steps:**
1. Install dependencies.
2. Run `pytest`.
3. Restore `data/` from `bot/data`.
4. Run the pipeline.
5. Push `data/` to `bot/data`.
6. Deploy `docs/` to Pages.

Runs are serialized, so two runs never write to the data branch at the same time.

**Secrets:** `TOMTOM_API_KEY`.

## 9. Non-goals (for now)

- AI or LLM-generated summaries.
- Cities beyond the 20 largest CMAs.
- French-language site.
- Per-neighbourhood scores.
- Income or cost-of-living indices. StatCan's income tables cover only 8 of the 20 CMAs.
