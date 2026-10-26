"""Client for Elexon's public BMRS Insights dataset streams."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import asyncio

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
LONDON = ZoneInfo("Europe/London")


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


async def _get(
    client: httpx.AsyncClient,
    dataset: str,
    published_from: datetime,
    published_to: datetime,
) -> list[dict]:
    """Fetch dataset records by their source publication window."""
    response = await client.get(
        f"{BASE_URL}/datasets/{dataset}/stream",
        params={
            "publishDateTimeFrom": _utc(published_from),
            "publishDateTimeTo": _utc(published_to),
        },
    )
    response.raise_for_status()
    body = response.json()
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        data = body.get("data", [])
        if isinstance(data, list):
            return data
    raise ValueError(f"Elexon returned an unexpected response for {dataset}.")


async def load_day(delivery_date: date, cutoff_hour: int = 10) -> dict:
    """Fetch actuals and forecast files published around one delivery day."""
    day_start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    day_end = day_start + timedelta(days=1)
    cutoff = datetime.combine(delivery_date - timedelta(days=1), time(cutoff_hour), tzinfo=LONDON)

    # Include recent forecast vintages, then select only the latest issue available
    # by the cutoff for each settlement start time in analysis.py.
    forecast_from = cutoff - timedelta(days=2)
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        actuals, forecasts = await asyncio.gather(
            _get(client, "FUELHH", day_start, day_end),
            _get(client, "WINDFOR", forecast_from, cutoff),
        )
    return {
        "actuals": actuals,
        "forecasts": forecasts,
        "cutoff": cutoff,
        "day_start": day_start,
        "day_end": day_end,
    }
