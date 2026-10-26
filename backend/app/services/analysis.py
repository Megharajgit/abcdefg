"""Normalize Elexon records and calculate forecast error metrics."""
from datetime import date, datetime, timedelta
from math import sqrt
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _number(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def analyze(delivery_date: date, raw: dict, cutoff_hour: int = 10) -> dict:
    cutoff, start, end = raw["cutoff"], raw["day_start"], raw["day_end"]
    actual_map: dict[datetime, tuple[datetime, float]] = {}
    for row in raw["actuals"]:
        if str(row.get("fuelType", "")).upper() != "WIND":
            continue
        target, value = _dt(row.get("startTime")), _number(row.get("generation"))
        if not target or value is None:
            continue
        target_local = target.astimezone(LONDON)
        if not start <= target_local < end:
            continue
        published = _dt(row.get("publishTime")) or target
        published_local = published.astimezone(LONDON)
        previous = actual_map.get(target_local)
        if previous is None or published_local >= previous[0]:
            actual_map[target_local] = (published_local, value)

    forecast_map: dict[datetime, tuple[datetime, float]] = {}
    for row in raw["forecasts"]:
        target = _dt(row.get("startTime"))
        published = _dt(row.get("publishTime"))
        value = _number(row.get("generation"))
        if not (target and published and value is not None):
            continue
        target_local = target.astimezone(LONDON)
        published_local = published.astimezone(LONDON)
        if start <= target_local < end and published_local <= cutoff:
            previous = forecast_map.get(target_local)
            if previous is None or published_local > previous[0]:
                forecast_map[target_local] = (published_local, value)

    rows, cursor = [], start
    while cursor < end:
        forecast = forecast_map.get(cursor)
        actual_entry = actual_map.get(cursor)
        actual = actual_entry[1] if actual_entry else None
        rows.append({
            "startTime": cursor.isoformat(),
            "forecast": round(forecast[1], 1) if forecast else None,
            "publishTime": forecast[0].isoformat() if forecast else None,
            "actual": round(actual, 1) if actual is not None else None,
            "error": round(forecast[1] - actual, 1) if forecast and actual is not None else None,
        })
        cursor += timedelta(minutes=30)

    pairs = [
        (row["forecast"], row["actual"])
        for row in rows
        if row["forecast"] is not None and row["actual"] is not None
    ]
    errors = [forecast - actual for forecast, actual in pairs]
    mae = sum(abs(error) for error in errors) / len(errors) if errors else None
    rmse = sqrt(sum(error * error for error in errors) / len(errors)) if errors else None
    bias = sum(errors) / len(errors) if errors else None
    valid_mape = [(forecast, actual) for forecast, actual in pairs if actual >= 100]
    mape = (
        sum(abs((forecast - actual) / actual) for forecast, actual in valid_mape)
        / len(valid_mape) * 100
        if valid_mape
        else None
    )
    return {
        "deliveryDate": delivery_date.isoformat(),
        "cutoff": cutoff.isoformat(),
        "cutoffHour": cutoff_hour,
        "timezone": "Europe/London",
        "periods": rows,
        "metrics": {
            "matchedPeriods": len(pairs),
            "forecastCoverage": round(sum(row["forecast"] is not None for row in rows) / len(rows) * 100, 1),
            "mae": round(mae, 1) if mae is not None else None,
            "rmse": round(rmse, 1) if rmse is not None else None,
            "bias": round(bias, 1) if bias is not None else None,
            "mape": round(mape, 1) if mape is not None else None,
            "actualMean": round(sum(actual for _, actual in pairs) / len(pairs), 1) if pairs else None,
        },
        "source": "Elexon BMRS Insights API",
        "mode": "live",
    }
