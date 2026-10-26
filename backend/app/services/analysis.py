"""Normalize Elexon records and compute forecast error metrics."""
from datetime import date, datetime, timedelta
from math import sqrt
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=ZoneInfo("UTC")) if parsed.tzinfo is None else parsed

def _number(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def analyze(delivery_date: date, raw: dict, cutoff_hour: int = 10) -> dict:
    cutoff, start, end = raw["cutoff"], raw["day_start"], raw["day_end"]
    actual_map: dict[datetime, float] = {}
    for row in raw["actuals"]:
        if str(row.get("fuelType", "")).upper() != "WIND":
            continue
        target, value = _dt(row.get("startTime")), _number(row.get("generation"))
        if target and value is not None and start <= target.astimezone(LONDON) < end:
            actual_map[target.astimezone(LONDON)] = value
    forecast_map: dict[datetime, tuple[datetime, float]] = {}
    for row in raw["forecasts"]:
        target, published, value = _dt(row.get("startTime")), _dt(row.get("publishTime")), _number(row.get("generation"))
        if not (target and published and value is not None):
            continue
        target_local, published_local = target.astimezone(LONDON), published.astimezone(LONDON)
        if start <= target_local < end and published_local <= cutoff:
            previous = forecast_map.get(target_local)
            if previous is None or published_local > previous[0]:
                forecast_map[target_local] = (published_local, value)
    rows, cursor = [], start
    while cursor < end:
        forecast, actual = forecast_map.get(cursor), actual_map.get(cursor)
        rows.append({"startTime": cursor.isoformat(), "forecast": round(forecast[1], 1) if forecast else None,
                     "publishTime": forecast[0].isoformat() if forecast else None,
                     "actual": round(actual, 1) if actual is not None else None,
                     "error": round(forecast[1] - actual, 1) if forecast and actual is not None else None})
        cursor += timedelta(minutes=30)
    pairs = [(r["forecast"], r["actual"]) for r in rows if r["forecast"] is not None and r["actual"] is not None]
    errors = [f - a for f, a in pairs]
    mae = sum(abs(e) for e in errors) / len(errors) if errors else None
    rmse = sqrt(sum(e * e for e in errors) / len(errors)) if errors else None
    bias = sum(errors) / len(errors) if errors else None
    valid_mape = [(f, a) for f, a in pairs if a >= 100]
    mape = sum(abs((f - a) / a) for f, a in valid_mape) / len(valid_mape) * 100 if valid_mape else None
    return {"deliveryDate": delivery_date.isoformat(), "cutoff": cutoff.isoformat(), "cutoffHour": cutoff_hour,
            "timezone": "Europe/London", "periods": rows,
            "metrics": {"matchedPeriods": len(pairs), "forecastCoverage": round(sum(r["forecast"] is not None for r in rows) / len(rows) * 100, 1),
                        "mae": round(mae, 1) if mae is not None else None, "rmse": round(rmse, 1) if rmse is not None else None,
                        "bias": round(bias, 1) if bias is not None else None, "mape": round(mape, 1) if mape is not None else None,
                        "actualMean": round(sum(a for _, a in pairs) / len(pairs), 1) if pairs else None},
            "source": "Elexon BMRS Insights API", "mode": "live"}
