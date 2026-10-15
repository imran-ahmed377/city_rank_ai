"""City Rank AI - ranks Canadian metro areas on living standards.

The package is organised as a small data pipeline:

    sources/   -> fetch raw data from public APIs and turn it into tidy metric rows
    store.py   -> read/write those rows (and history files) under data/
    catalog.py -> describes every metric: label, unit, category, better direction
    scoring.py -> turns metric values into 0-100 scores and a weighted ranking
    dashboard.py + templates/ + static/ -> render the static website into docs/
    pipeline.py -> runs all of the above in order (entry point: python -m city_rank)
"""

__version__ = "2.0.0"
