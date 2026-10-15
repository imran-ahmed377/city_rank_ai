"""Reading and writing everything under data/.

Layout (all paths relative to the data root):

    metrics/<source>.csv        latest values from one source, "tidy" format:
                                city, metric, value, period, source, fetched_at
    history/<name>.csv          append-only time series (observations, traffic
                                samples, daily rankings)
    weather/<name>.csv          bulk weather tables used for charts
    run_status.json             what happened to each source on the last run

The Store class takes the root folder as a parameter so tests can point it at a
temporary directory instead of the real data/ folder.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

# Column order for every metrics/<source>.csv file.
METRIC_COLUMNS = ["city", "metric", "value", "period", "source", "fetched_at"]

# Timestamps are always stored as UTC ISO-8601 strings like 2026-10-14T22:00:00Z.
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    """Current time in UTC (one function so tests and code agree on 'now')."""
    return datetime.now(timezone.utc)


def format_ts(moment: datetime) -> str:
    """datetime -> '2026-10-14T22:00:00Z'."""
    return moment.astimezone(timezone.utc).strftime(TIME_FORMAT)


def parse_ts(value: str) -> datetime:
    """'2026-10-14T22:00:00Z' -> timezone-aware datetime."""
    return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=timezone.utc)


class Store:
    """File-based storage rooted at one folder (normally data/)."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.metrics_dir = self.root / "metrics"
        self.history_dir = self.root / "history"
        self.weather_dir = self.root / "weather"

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _write_csv(path: Path, df: pd.DataFrame) -> None:
        """Write a DataFrame to CSV, creating parent folders as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)

    @staticmethod
    def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
        """Read a CSV, or return an empty frame (with ``columns``) if it is missing."""
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame(columns=columns or [])
        return pd.read_csv(path)

    # ------------------------------------------------------------------ metrics
    def metrics_path(self, source: str) -> Path:
        return self.metrics_dir / f"{source}.csv"

    def load_metrics(self, source: str) -> pd.DataFrame:
        """Latest stored metric rows for one source (empty frame if none yet)."""
        return self._read_csv(self.metrics_path(source), METRIC_COLUMNS)

    def save_metrics(self, source: str, new_rows: pd.DataFrame) -> pd.DataFrame:
        """Merge freshly fetched rows into the stored file and save it.

        New rows replace old rows for the same (city, metric). Old rows that
        were *not* refetched are kept - so if one city's request failed today,
        yesterday's value for that city survives instead of disappearing.
        """
        old_rows = self.load_metrics(source)
        new_rows = new_rows[METRIC_COLUMNS]
        combined = pd.concat([old_rows, new_rows], ignore_index=True) if not old_rows.empty else new_rows.copy()
        # keep="last" -> the new row wins because it was concatenated after the old one.
        combined = combined.drop_duplicates(subset=["city", "metric"], keep="last")
        combined = combined.sort_values(["city", "metric"]).reset_index(drop=True)
        self._write_csv(self.metrics_path(source), combined)
        return combined

    def load_all_metrics(self) -> pd.DataFrame:
        """All metric rows from every source, concatenated."""
        if not self.metrics_dir.exists():
            return pd.DataFrame(columns=METRIC_COLUMNS)
        frames = [self._read_csv(p, METRIC_COLUMNS) for p in sorted(self.metrics_dir.glob("*.csv"))]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame(columns=METRIC_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def cities_missing(self, source: str, slugs: list[str]) -> list[str]:
        """Which of ``slugs`` have no stored rows at all for this source."""
        rows = self.load_metrics(source)
        present = set(rows["city"]) if not rows.empty else set()
        return [slug for slug in slugs if slug not in present]

    def last_fetched(self, source: str) -> datetime | None:
        """When this source last produced data (newest fetched_at), or None."""
        rows = self.load_metrics(source)
        if rows.empty or "fetched_at" not in rows:
            return None
        return parse_ts(str(rows["fetched_at"].max()))

    def is_fresh(self, source: str, ttl_hours: float, now: datetime | None = None) -> bool:
        """True if the source was fetched less than ``ttl_hours`` ago.

        Used to avoid re-downloading yearly/monthly statistics on every run.
        A ttl of 0 means "always refetch".
        """
        if ttl_hours <= 0:
            return False
        fetched = self.last_fetched(source)
        if fetched is None:
            return False
        return (now or utc_now()) - fetched < timedelta(hours=ttl_hours)

    # ------------------------------------------------------------------ history
    def history_path(self, name: str) -> Path:
        return self.history_dir / f"{name}.csv"

    def load_history(self, name: str) -> pd.DataFrame:
        return self._read_csv(self.history_path(name))

    def append_history(
        self,
        name: str,
        rows: pd.DataFrame,
        key: list[str],
        time_column: str | None = None,
        keep_days: int | None = None,
        now: datetime | None = None,
    ) -> pd.DataFrame:
        """Append rows to history/<name>.csv.

        key        : columns that identify a row; duplicates keep the newest.
        time_column: column holding a UTC timestamp string (needed for pruning).
        keep_days  : if set, drop rows older than this many days.
        """
        existing = self.load_history(name)
        combined = pd.concat([existing, rows], ignore_index=True) if not existing.empty else rows.copy()
        combined = combined.drop_duplicates(subset=key, keep="last")

        # Optional pruning so files like traffic samples don't grow forever.
        if keep_days is not None and time_column and not combined.empty:
            cutoff = format_ts((now or utc_now()) - timedelta(days=keep_days))
            # ISO strings in the same format sort the same way as the times they represent.
            combined = combined[combined[time_column].astype(str) >= cutoff]

        combined = combined.sort_values(key).reset_index(drop=True)
        self._write_csv(self.history_path(name), combined)
        return combined

    # ------------------------------------------------------------------ bulk tables
    def write_table(self, relative_path: str, df: pd.DataFrame) -> None:
        """Write any CSV under the data root, e.g. 'weather/daily_365.csv'."""
        self._write_csv(self.root / relative_path, df)

    def read_table(self, relative_path: str) -> pd.DataFrame:
        return self._read_csv(self.root / relative_path)

    # ------------------------------------------------------------------ JSON
    def write_json(self, relative_path: str, payload: Any) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def read_json(self, relative_path: str, default: Any = None) -> Any:
        path = self.root / relative_path
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
