"""Tests for the ranking maths in city_rank/scoring.py."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from city_rank.scoring import build_rankings, score_categories, score_metrics, score_overall, to_wide
from tests.conftest import make_metrics


def test_to_wide_includes_every_city(three_cities):
    # Only Toronto has data, but all three cities must appear as rows.
    wide = to_wide(make_metrics([("toronto", "rent_2br", 2000)]), three_cities)
    assert list(wide.index) == ["toronto", "montreal", "vancouver"]
    assert wide.loc["toronto", "rent_2br"] == 2000
    assert math.isnan(wide.loc["montreal", "rent_2br"])


def test_lower_is_better_metric_is_flipped():
    # Rent: lower is better, so the cheapest city scores 100.
    values = pd.DataFrame({"rent_2br": [1000.0, 1500.0, 2000.0]}, index=["a", "b", "c"])
    scores = score_metrics(values)
    assert scores["rent_2br"].tolist() == [100.0, 50.0, 0.0]


def test_higher_is_better_metric_is_not_flipped():
    values = pd.DataFrame({"employment_rate": [60.0, 65.0, 70.0]}, index=["a", "b", "c"])
    assert score_metrics(values)["employment_rate"].tolist() == [0.0, 50.0, 100.0]


def test_all_equal_values_score_50_and_missing_stays_missing():
    values = pd.DataFrame({"hot_days": [5.0, 5.0, None]}, index=["a", "b", "c"])
    scores = score_metrics(values)["hot_days"]
    assert scores["a"] == 50.0 and scores["b"] == 50.0
    assert math.isnan(scores["c"])


def test_info_only_metrics_are_not_scored():
    values = pd.DataFrame({"population": [1.0, 2.0], "current_temp_c": [3.0, 4.0]}, index=["a", "b"])
    assert score_metrics(values).columns.tolist() == []


def test_category_score_is_mean_of_available_metrics():
    metric_scores = pd.DataFrame(
        {"crime_severity_index": [100.0, 0.0], "violent_crime_severity_index": [50.0, None]},
        index=["a", "b"],
    )
    cats = score_categories(metric_scores)
    assert cats.loc["a", "safety"] == 75.0
    assert cats.loc["b", "safety"] == 0.0           # the missing metric is ignored
    assert math.isnan(cats.loc["a", "housing"])     # no housing metrics at all -> no data


def test_overall_reweights_when_a_category_is_missing():
    cats = pd.DataFrame({"safety": [80.0, None], "housing": [40.0, 60.0]}, index=["a", "b"])
    overall = score_overall(cats, {"safety": 1, "housing": 1})
    assert overall.loc["a", "overall"] == pytest.approx(60.0)
    # b has no safety data -> its overall is just its housing score, with half the weight covered.
    assert overall.loc["b", "overall"] == pytest.approx(60.0)
    assert overall.loc["b", "coverage"] == pytest.approx(0.5)
    # Tie -> both share rank 1 ("min" ranking).
    assert overall["rank"].tolist() == [1.0, 1.0]


def test_category_without_any_data_does_not_reduce_coverage():
    cats = pd.DataFrame({"safety": [80.0, 20.0], "traffic": [None, None]}, index=["a", "b"])
    overall = score_overall(cats, {"safety": 1, "traffic": 1})
    assert overall["coverage"].tolist() == [1.0, 1.0]


def test_zero_weight_category_is_ignored():
    cats = pd.DataFrame({"safety": [100.0, 0.0], "housing": [0.0, 100.0]}, index=["a", "b"])
    overall = score_overall(cats, {"safety": 0, "housing": 5})
    assert overall.index[0] == "b"
    assert overall.loc["b", "overall"] == 100.0


def test_build_rankings_end_to_end(three_cities):
    metrics = make_metrics(
        [
            ("toronto", "rent_2br", 2000), ("montreal", "rent_2br", 1500), ("vancouver", "rent_2br", 2500),
            ("toronto", "crime_severity_index", 50), ("montreal", "crime_severity_index", 60),
            ("vancouver", "crime_severity_index", 90),
            ("toronto", "unknown_metric", 1),  # ignored: not in the catalog
        ]
    )
    result = build_rankings(metrics, three_cities)
    assert result.overall.index[0] == "montreal"   # cheapest rent, mid crime
    assert result.overall.index[-1] == "vancouver"  # worst at both
    assert "unknown_metric" not in result.values.columns
    assert set(result.overall.columns) == {"overall", "coverage", "rank"}
