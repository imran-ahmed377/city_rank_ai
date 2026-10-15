"""Turn raw metric values into 0-100 scores and an overall ranking.

The method, in three steps
--------------------------
1. Metric score (0-100). For each ranked metric we compare the cities with
   min-max scaling:  score = (value - min) / (max - min) * 100.
   If lower is better (crime, rent, ...) the score is flipped: 100 - score.
   So the best city on a metric gets 100, the worst gets 0. If every city has
   the same value, all get 50.

2. Category score (0-100). The average of the metric scores in that category
   (e.g. Safety = mean of CSI score and violent CSI score). Missing metrics are
   ignored; if a city has no metrics at all in a category, that category is
   "no data" for that city.

3. Overall score (0-100). The weighted average of the category scores, using
   the category weights (default from catalog.py, adjustable on the dashboard).
   If a city lacks a category, the remaining weights are re-normalised for that
   city, and ``coverage`` records what share of the total weight was available.

Scores are *relative*: 100 means "best of the cities we rank", not "perfect".
The dashboard's JavaScript (static/rankings.js) repeats step 3 in the browser
when visitors move the weight sliders - keep the two in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd

from .catalog import CATEGORIES, METRICS_BY_KEY, default_weights, metrics_in_category, ranked_metrics
from .cities import City


@dataclass
class RankingResult:
    """Everything the dashboard needs, indexed by city slug.

    values          : raw metric values (all metrics, incl. info-only), city x metric
    periods         : reference period of each value, city x metric
    metric_scores   : 0-100 score per ranked metric, city x metric
    category_scores : 0-100 score per category, city x category
    overall         : columns overall, coverage, rank (sorted best first)
    """

    values: pd.DataFrame
    periods: pd.DataFrame
    metric_scores: pd.DataFrame
    category_scores: pd.DataFrame
    overall: pd.DataFrame


def to_wide(metrics_long: pd.DataFrame, cities: Sequence[City], column: str = "value") -> pd.DataFrame:
    """Long rows (city, metric, value, ...) -> wide table: one row per city, one column per metric.

    Every city appears (even with no data) so missing values are explicit NaN.
    """
    slugs = [c.slug for c in cities]
    if metrics_long.empty:
        return pd.DataFrame(index=pd.Index(slugs, name="city"))
    # If the same (city, metric) appears twice, the last row wins.
    deduped = metrics_long.drop_duplicates(subset=["city", "metric"], keep="last")
    wide = deduped.pivot(index="city", columns="metric", values=column)
    wide = wide.reindex(slugs)
    wide.index.name = "city"
    return wide


def score_metrics(values: pd.DataFrame) -> pd.DataFrame:
    """Step 1: min-max scale each ranked metric to 0-100 (100 = best)."""
    scores = pd.DataFrame(index=values.index)
    for metric in ranked_metrics():
        if metric.key not in values.columns:
            continue
        column = pd.to_numeric(values[metric.key], errors="coerce")
        low, high = column.min(), column.max()
        if pd.isna(low):
            continue  # no city has this metric
        if high == low:
            scaled = column.where(column.isna(), 50.0)  # everyone ties
        else:
            scaled = (column - low) / (high - low) * 100
            if not metric.higher_is_better:
                scaled = 100 - scaled
        scores[metric.key] = scaled
    return scores


def score_categories(metric_scores: pd.DataFrame) -> pd.DataFrame:
    """Step 2: average the metric scores inside each category (NaN = no data)."""
    result = pd.DataFrame(index=metric_scores.index)
    for category in CATEGORIES:
        keys = [m.key for m in metrics_in_category(category.key) if m.key in metric_scores.columns]
        # mean(axis=1) skips NaN; a row of all-NaN stays NaN.
        result[category.key] = metric_scores[keys].mean(axis=1) if keys else float("nan")
    return result


def score_overall(category_scores: pd.DataFrame, weights: Mapping[str, float] | None = None) -> pd.DataFrame:
    """Step 3: weighted average of category scores, re-normalised per city.

    Returns a frame with overall (0-100), coverage (0-1) and rank (1 = best),
    sorted from best to worst. Cities with no data at all get NaN and rank last.
    """
    weights = dict(weights or default_weights())
    # Only categories with a weight AND data for at least one city take part.
    # (A category nobody has yet, e.g. traffic before the first sample, should not
    # make every city look "partial".)
    keys = [k for k in category_scores.columns if weights.get(k, 0) > 0 and category_scores[k].notna().any()]
    total_weight = sum(weights[k] for k in keys)

    rows = []
    for slug, row in category_scores.iterrows():
        available = [k for k in keys if pd.notna(row[k])]
        used_weight = sum(weights[k] for k in available)
        overall = (
            sum(row[k] * weights[k] for k in available) / used_weight if used_weight > 0 else float("nan")
        )
        coverage = used_weight / total_weight if total_weight > 0 else 0.0
        rows.append({"city": slug, "overall": overall, "coverage": coverage})

    result = pd.DataFrame(rows).set_index("city")
    # "min" ranking: ties share the better rank (1, 2, 2, 4 ...).
    result["rank"] = result["overall"].rank(ascending=False, method="min")
    return result.sort_values(["overall"], ascending=False, na_position="last")


def category_ranks(category_scores: pd.DataFrame) -> pd.DataFrame:
    """Rank of each city within each category (1 = best, NaN when no data)."""
    return category_scores.rank(ascending=False, method="min")


def build_rankings(
    metrics_long: pd.DataFrame,
    cities: Sequence[City],
    weights: Mapping[str, float] | None = None,
) -> RankingResult:
    """Run steps 1-3 on the combined metric rows from all sources."""
    # Only keep metrics we know about (ignores leftovers from removed metrics).
    known = metrics_long[metrics_long["metric"].isin(METRICS_BY_KEY)] if not metrics_long.empty else metrics_long
    values = to_wide(known, cities, "value").apply(pd.to_numeric, errors="coerce")
    periods = to_wide(known, cities, "period")
    metric_scores = score_metrics(values)
    category_scores = score_categories(metric_scores)
    overall = score_overall(category_scores, weights)
    return RankingResult(values, periods, metric_scores, category_scores, overall)
