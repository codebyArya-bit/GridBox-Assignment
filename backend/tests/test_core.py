from datetime import date, datetime, timezone
import math
import pytest
from app.core import (parse_cutoff, decision_cutoff, delivery_day,
                      half_hour_intervals, evaluate, latest_asof)

def at(day, hour, minute=0):
    return f"{day}T{hour:02d}:{minute:02d}:00Z"

def test_boundary_decisions():
    assert delivery_day(date(2026, 1, 1)) == date(2026, 1, 2)
    assert delivery_day(date(2026, 1, 31)) == date(2026, 2, 1)
    with pytest.raises(ValueError):
        delivery_day(date(2026, 2, 1))

def test_0950_uk_and_custom_minute_cutoff():
    assert decision_cutoff(date(2026, 1, 15)) == datetime(2026, 1, 15, 9, 50, tzinfo=timezone.utc)
    assert decision_cutoff(date(2026, 7, 15), "09:50") == datetime(2026, 7, 15, 8, 50, tzinfo=timezone.utc)
    assert decision_cutoff(date(2026, 1, 15), "10:17").minute == 17
    for bad in ["11", "11:99", "24:00", "abcde", "11:1"]:
        with pytest.raises(ValueError):
            parse_cutoff(bad)

def test_hourly_aggregation_and_metric_correctness():
    day = date(2026, 1, 15)
    target = "2026-01-16"
    actuals = [
        {"startTime": at(target, 0), "fuelType": "WIND", "generation": 100},
        {"startTime": at(target, 0, 30), "fuelType": "WIND", "generation": 140},
        {"startTime": at(target, 1), "fuelType": "WIND", "generation": 160},
        {"startTime": at(target, 1, 30), "fuelType": "WIND", "generation": 180},
    ]
    forecasts = [
        {"startTime": at(target, 0), "publishTime": at("2026-01-15", 9, 30), "generation": 110},
        {"startTime": at(target, 1), "publishTime": at("2026-01-15", 9, 30), "generation": 190},
        {"startTime": at(target, 0), "publishTime": at("2026-01-15", 10, 30), "generation": 9999},
    ]
    result = evaluate(actuals, forecasts, day)
    assert result["expectedIntervals"] == 24
    assert result["expectedHalfHourIntervals"] == 48
    assert result["observedHalfHourIntervals"] == 4
    assert result["actualIntervals"] == result["forecastIntervals"] == result["matchedIntervals"] == 2
    assert result["series"][0]["actualMW"] == 120
    assert result["series"][0]["forecastMW"] == 110
    assert result["series"][0]["actualHalfHoursMW"] == [100, 140]
    assert result["series"][1]["actualMW"] == 170
    assert result["maeMW"] == 15
    assert result["rmseMW"] == round(math.sqrt(250), 2)
    assert result["biasMW"] == 5

def test_no_imputation_when_one_half_hour_is_missing():
    actuals = [{"startTime": at("2026-01-16", 0), "fuelType": "WIND", "generation": 100}]
    forecast = [{"startTime": at("2026-01-16", 0), "publishTime": at("2026-01-15", 8), "generation": 200}]
    result = evaluate(actuals, forecast, date(2026, 1, 15))
    assert result["actualIntervals"] == result["matchedIntervals"] == 0
    assert result["series"][0]["actualMW"] is None
    assert result["series"][0]["actualHalfHoursMW"] == [100.0, None]
    assert result["maeMW"] is None

def test_no_future_published_forecasts():
    target = at("2026-01-16", 0)
    values = [
        {"startTime": target, "publishTime": at("2026-01-15", 7), "generation": 1},
        {"startTime": target, "publishTime": at("2026-01-15", 9, 49), "generation": 2},
        {"startTime": target, "publishTime": at("2026-01-15", 9, 51), "generation": 3},
    ]
    result = latest_asof(values, decision_cutoff(date(2026, 1, 15)))
    assert result[datetime(2026, 1, 16, tzinfo=timezone.utc)]["forecast"] == 2

def test_invalid_other_fuels_and_nan():
    actuals = [
        {"startTime": at("2026-01-16", 0), "fuelType": "SOLAR", "generation": 900},
        {"startTime": at("2026-01-16", 0), "fuelType": "WIND", "generation": float("nan")},
    ]
    assert evaluate(actuals, [], date(2026, 1, 15))["observedHalfHourIntervals"] == 0

def test_dst_safe_slot_construction():
    assert len(half_hour_intervals(date(2026, 3, 29))) == 46
    assert len(half_hour_intervals(date(2026, 10, 25))) == 50

def test_empty_day_no_fabricated_metrics():
    d = evaluate([], [], date(2026, 1, 1))
    assert d["matchedIntervals"] == 0 and d["maeMW"] is None
    assert len(d["series"]) == 24
