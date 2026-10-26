"""Small, explicit client for Elexon's public BMRS Insights API."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import asyncio
import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
LONDON = ZoneInfo("Europe/London")

def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

async def _get(client: httpx.AsyncClient, path: str, start: datetime, end: datetime) -> list[dict]:
    response = await client.get(f"{BASE_URL}/{path}/stream", params={"from": _utc(start), "to": _utc(end)})
    response.raise_for_status()
    body = response.json()
    return body if isinstance(body, list) else body.get("data", []) if isinstance(body, dict) else []

async def load_day(delivery_date: date, cutoff_hour: int = 10) -> dict:
    """Load actuals and forecast publications for one delivery day."""
    day_start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    day_end = day_start + timedelta(days=1)
    cutoff = datetime.combine(delivery_date - timedelta(days=1), time(cutoff_hour), tzinfo=LONDON)
    query_start = cutoff - timedelta(days=1)
    async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
        actuals, forecasts = await asyncio.gather(
            _get(client, "datasets/FUELHH", day_start, day_end),
            _get(client, "datasets/WINDFOR", query_start, day_end),
        )
    return {"actuals": actuals, "forecasts": forecasts, "cutoff": cutoff, "day_start": day_start, "day_end": day_end}
