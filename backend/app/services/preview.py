"""Clearly labelled deterministic preview data used only when Elexon is offline."""
from datetime import date, datetime, time, timedelta
from math import sin
from zoneinfo import ZoneInfo
from app.services.analysis import analyze

LONDON = ZoneInfo("Europe/London")

def preview_day(delivery_date: date, cutoff_hour: int = 10) -> dict:
    start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    end = start + timedelta(days=1)
    cutoff = datetime.combine(delivery_date - timedelta(days=1), time(cutoff_hour), tzinfo=LONDON)
    actuals, forecasts, cursor, index = [], [], start, 0
    while cursor < end:
        actual = 11200 + 3400 * sin((index - 8) * 3.14159 / 24) + 750 * sin(index * 0.77)
        forecast = actual + 420 * sin(index * 0.91 + 0.7) + 160 * sin(index * 0.27)
        actuals.append({"fuelType": "WIND", "startTime": cursor.isoformat(), "generation": actual})
        forecasts.append({"startTime": cursor.isoformat(), "publishTime": cutoff.isoformat(), "generation": forecast})
        cursor += timedelta(minutes=30)
        index += 1
    result = analyze(delivery_date, {"actuals": actuals, "forecasts": forecasts, "cutoff": cutoff, "day_start": start, "day_end": end}, cutoff_hour)
    result["source"], result["mode"] = "Synthetic preview data (Elexon unavailable)", "preview"
    return result
