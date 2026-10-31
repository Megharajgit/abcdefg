"""Normalize Elexon records and calculate full precision accuracy metrics."""
import logging
from datetime import date, datetime, timedelta
from math import isfinite, sqrt
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")
MAPE_MIN_ACTUAL_MW = 100.0
logger = logging.getLogger(__name__)


def _dt(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        # Elexon timestamps are UTC; naive timestamps are normalized as UTC.
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number >= 0 else None


def _revision(row: dict) -> int:
    try:
        return int(row.get("documentRevisionNumber") or 0)
    except (TypeError, ValueError):
        return 0


def analyze(delivery_date: date, raw: dict, cutoff_hour: int = 10) -> dict:
    cutoff = _dt(raw["cutoff"])
    start_local, end_local = raw["day_start"], raw["day_end"]
    start, end = start_local.astimezone(UTC), end_local.astimezone(UTC)

    # Keep the most recently published/revised valid WIND observation per start.
    actual_map: dict[datetime, tuple[datetime, int, float]] = {}
    invalid_actuals = 0
    for row in raw.get("actuals", []):
        if str(row.get("fuelType", "")).strip().upper() != "WIND":
            continue
        target, value = _dt(row.get("startTime")), _number(row.get("generation"))
        if target is None or value is None:
            invalid_actuals += 1
            continue
        if not start <= target < end:
            continue
        published = _dt(row.get("publishTime")) or target
        candidate = (published, _revision(row), value)
        if target not in actual_map or candidate[:2] >= actual_map[target][:2]:
            actual_map[target] = candidate

    # First select the newest source forecast per forecast start time.
    forecast_sources: dict[datetime, tuple[datetime, int, float]] = {}
    invalid_forecasts = 0
    for row in raw.get("forecasts", []):
        target = _dt(row.get("startTime"))
        published = _dt(row.get("publishTime"))
        value = _number(row.get("generation"))
        if target is None or published is None or value is None:
            invalid_forecasts += 1
            continue
        if not start <= target < end or published > cutoff:
            continue
        candidate = (published, _revision(row), value)
        if target not in forecast_sources or candidate[:2] >= forecast_sources[target][:2]:
            forecast_sources[target] = candidate

    # Elexon's WINDFOR is hourly. Its hourly value applies to each of the two
    # half-hour settlement periods within that hour. Keep exact :30 source rows
    # usable too, should the feed provide them. An explicit :30 source row wins
    # a tie against an inherited hourly value for that same settlement start.
    forecast_map: dict[datetime, tuple[datetime, int, int, float]] = {}
    for target, (published, revision, value) in forecast_sources.items():
        period_starts = [target]
        if target.minute == 0 and target.second == 0:
            period_starts.append(target + timedelta(minutes=30))
        for period_start in period_starts:
            if not start <= period_start < end:
                continue
            candidate = (published, int(period_start == target), revision, value)
            existing = forecast_map.get(period_start)
            if existing is None or candidate[:3] >= existing[:3]:
                forecast_map[period_start] = candidate

    rows = []
    cursor = start
    while cursor < end:
        forecast = forecast_map.get(cursor)
        actual = actual_map.get(cursor)
        forecast_value = forecast[3] if forecast else None
        actual_value = actual[2] if actual else None
        rows.append({
            "startTime": cursor.astimezone(LONDON).isoformat(),
            "forecast": forecast_value,
            "publishTime": forecast[0].astimezone(LONDON).isoformat() if forecast else None,
            "actual": actual_value,
            "error": forecast_value - actual_value if forecast_value is not None and actual_value is not None else None,
        })
        cursor += timedelta(minutes=30)

    expected = len(rows)
    if invalid_actuals:
        logger.warning("Skipped %s malformed or missing-generation WIND actual rows for %s", invalid_actuals, delivery_date)
    if invalid_forecasts:
        logger.warning("Skipped %s malformed or missing-generation WINDFOR rows for %s", invalid_forecasts, delivery_date)
    forecast_count = sum(row["forecast"] is not None for row in rows)
    actual_values = [row["actual"] for row in rows if row["actual"] is not None]
    pairs = [(row["forecast"], row["actual"]) for row in rows if row["forecast"] is not None and row["actual"] is not None]
    errors = [forecast - actual for forecast, actual in pairs]
    mae = sum(abs(error) for error in errors) / len(errors) if errors else None
    rmse = sqrt(sum(error * error for error in errors) / len(errors)) if errors else None
    bias = sum(errors) / len(errors) if errors else None
    mape_pairs = [(forecast, actual) for forecast, actual in pairs if actual >= MAPE_MIN_ACTUAL_MW]
    mape = sum(abs((forecast - actual) / actual) for forecast, actual in mape_pairs) / len(mape_pairs) * 100 if mape_pairs else None
    if expected != 48 and delivery_date.month == 1:
        logger.warning("Expected 48 half-hours for January date %s, generated %s", delivery_date, expected)

    return {
        "deliveryDate": delivery_date.isoformat(),
        "cutoff": cutoff.astimezone(LONDON).isoformat(),
        "cutoffHour": cutoff_hour,
        "timezone": "Europe/London",
        "periods": rows,
        "metrics": {
            "expectedPeriods": expected,
            "forecastPeriods": forecast_count,
            "forecastSourceHours": len(forecast_sources),
            "actualPeriods": len(actual_values),
            "matchedPeriods": len(pairs),
            "forecastCoverage": forecast_count / expected * 100 if expected else 0.0,
            "actualCoverage": len(actual_values) / expected * 100 if expected else 0.0,
            "matchedCoverage": len(pairs) / expected * 100 if expected else 0.0,
            "mapePeriods": len(mape_pairs),
            "mapeActualThresholdMW": MAPE_MIN_ACTUAL_MW,
            "mae": mae,
            "rmse": rmse,
            "bias": bias,
            "mape": mape,
            "actualMean": sum(actual_values) / len(actual_values) if actual_values else None,
        },
        "source": "Elexon BMRS Insights API",
        "mode": "live",
    }
