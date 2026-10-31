from datetime import date, datetime, timedelta, timezone
from math import isclose
from zoneinfo import ZoneInfo

from app.services.analysis import analyze

DELIVERY = date(2026, 1, 15)
UTC = timezone.utc
LONDON = ZoneInfo("Europe/London")
START = datetime(2026, 1, 15, tzinfo=UTC)
CUTOFF = datetime(2026, 1, 14, 10, tzinfo=LONDON)


def raw(actuals=None, forecasts=None):
    return {
        "actuals": actuals or [], "forecasts": forecasts or [], "cutoff": CUTOFF,
        "day_start": datetime(2026, 1, 15, tzinfo=LONDON),
        "day_end": datetime(2026, 1, 16, tzinfo=LONDON),
    }


def row(start, generation, **extra):
    return {"startTime": start.isoformat().replace("+00:00", "Z"), "generation": generation, **extra}


def test_latest_forecast_by_cutoff_including_exact_cutoff():
    target = START
    forecasts = [
        row(target, 100, publishTime="2026-01-13T08:00:00Z"),
        row(target, 110, publishTime="2026-01-14T09:59:59Z"),
        row(target, 120, publishTime="2026-01-14T10:00:00Z"),
        row(target, 999, publishTime="2026-01-14T10:00:01Z"),
    ]
    result = analyze(DELIVERY, raw(forecasts=forecasts))
    assert result["periods"][0]["forecast"] == 120
    assert result["periods"][0]["publishTime"].startswith("2026-01-14T10:00:00")
    assert result["metrics"]["forecastPeriods"] == 2
    assert result["periods"][1]["forecast"] == 120


def test_actuals_filter_wind_deduplicate_and_ignore_missing_values():
    target = START
    actuals = [
        row(target, 90, fuelType="WIND", publishTime="2026-01-15T01:00:00Z"),
        row(target, 95, fuelType="WIND", publishTime="2026-01-15T02:00:00Z"),
        row(target, 500, fuelType="GAS", publishTime="2026-01-15T03:00:00Z"),
        row(target + timedelta(minutes=30), None, fuelType="WIND"),
        row(target + timedelta(hours=1), 0, fuelType="WIND"),
    ]
    result = analyze(DELIVERY, raw(actuals=actuals))
    assert result["periods"][0]["actual"] == 95
    assert result["periods"][1]["actual"] is None
    assert result["periods"][2]["actual"] == 0
    assert result["metrics"]["actualPeriods"] == 2


def test_january_day_has_exactly_48_half_hour_slots():
    periods = analyze(DELIVERY, raw())["periods"]
    times = [datetime.fromisoformat(p["startTime"]) for p in periods]
    assert len(times) == 48
    assert (times[0].hour, times[0].minute) == (0, 0)
    assert (times[-1].hour, times[-1].minute) == (23, 30)
    assert all(b - a == timedelta(minutes=30) for a, b in zip(times, times[1:]))


def test_hourly_windfor_forecasts_cover_both_half_hour_settlement_periods():
    forecasts, actuals = [], []
    for hour in range(24):
        target = START + timedelta(hours=hour)
        forecasts.append(row(target, 1000 + hour, publishTime="2026-01-14T09:30:00Z"))
    for period in range(48):
        target = START + timedelta(minutes=30 * period)
        actuals.append(row(target, 900, fuelType="WIND"))
    metrics = analyze(DELIVERY, raw(actuals, forecasts))["metrics"]
    assert metrics["expectedPeriods"] == 48
    assert metrics["forecastSourceHours"] == 24
    assert metrics["forecastPeriods"] == 48
    assert metrics["actualPeriods"] == 48
    assert metrics["matchedPeriods"] == 48


def test_later_publication_wins_independently_for_each_source_hour():
    forecasts = [
        row(START, 100, publishTime="2026-01-14T08:00:00Z"),
        row(START, 110, publishTime="2026-01-14T09:00:00Z"),
        row(START + timedelta(hours=1), 200, publishTime="2026-01-14T08:30:00Z"),
    ]
    periods = analyze(DELIVERY, raw(forecasts=forecasts))["periods"]
    assert periods[0]["forecast"] == 110
    assert periods[1]["forecast"] == 110
    assert periods[2]["forecast"] == 200


def test_accuracy_metrics_use_full_precision_matched_pairs():
    forecasts, actuals = [], []
    for i, (forecast, actual) in enumerate(zip([100, 200, 300], [90, 220, 290])):
        target = START + timedelta(minutes=30 * i)
        forecasts.append(row(target, forecast, publishTime="2026-01-14T09:00:00Z"))
        actuals.append(row(target, actual, fuelType="WIND"))
    metrics = analyze(DELIVERY, raw(actuals, forecasts))["metrics"]
    assert isclose(metrics["mae"], 13.3333333333, rel_tol=1e-9)
    assert isclose(metrics["rmse"], 14.1421356237, rel_tol=1e-9)
    assert isclose(metrics["bias"], 0.0, abs_tol=1e-12)
    assert metrics["matchedPeriods"] == 3
    assert metrics["mapePeriods"] == 2


def test_missing_forecast_actual_no_matches_and_partial_coverage():
    result = analyze(DELIVERY, raw(actuals=[row(START, 10, fuelType="WIND")]))
    assert result["periods"][0]["forecast"] is None
    assert result["periods"][0]["error"] is None
    assert result["metrics"]["matchedPeriods"] == 0
    assert result["metrics"]["actualPeriods"] == 1
    assert result["metrics"]["forecastCoverage"] == 0
    assert result["metrics"]["mae"] is None and result["metrics"]["mape"] is None

    target = START + timedelta(minutes=30)
    partial = analyze(DELIVERY, raw(forecasts=[row(target, 1, publishTime="2026-01-14T09:00:00Z")]))
    assert partial["metrics"]["forecastPeriods"] == 1
    assert partial["metrics"]["actualPeriods"] == 0
    assert partial["metrics"]["matchedPeriods"] == 0
    assert isclose(partial["metrics"]["forecastCoverage"], 100 / 48)
