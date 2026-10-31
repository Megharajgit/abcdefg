"""Client for Elexon's public BMRS Insights datasets."""
import asyncio
import logging
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
LONDON = ZoneInfo("Europe/London")
logger = logging.getLogger(__name__)
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _records(body: object, dataset: str) -> list[dict]:
    """Normalize documented array responses and the JSON metadata envelope."""
    if isinstance(body, list) and all(isinstance(row, dict) for row in body):
        return body
    if isinstance(body, dict):
        for key in ("data", "results"):
            records = body.get(key)
            if isinstance(records, list) and all(isinstance(row, dict) for row in records):
                return records
    raise ValueError(f"Elexon returned an unexpected {dataset} response shape.")


async def _get_records(
    client: httpx.AsyncClient,
    dataset: str,
    params: dict[str, str],
    *,
    stream: bool = True,
) -> list[dict]:
    """Fetch dataset records with bounded retries for throttling/transient errors."""
    endpoint = f"{BASE_URL}/datasets/{dataset}" + ("/stream" if stream else "")
    for attempt in range(3):
        response = await client.get(endpoint, params=params)
        if response.status_code not in RETRYABLE_STATUS or attempt == 2:
            break
        retry_after = response.headers.get("Retry-After")
        try:
            delay = min(5.0, max(0.0, float(retry_after))) if retry_after else 0.5 * (2**attempt)
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                delay = min(5.0, max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds()))
            except (TypeError, ValueError, OverflowError):
                delay = 0.5 * (2**attempt)
        logger.warning("Elexon %s returned HTTP %s; retry %s/2 in %.1fs", dataset, response.status_code, attempt + 1, delay)
        await asyncio.sleep(delay)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error("Elexon %s request failed: status=%s url=%s body=%s", dataset, response.status_code, response.request.url, response.text[:500])
        raise
    try:
        return _records(response.json(), dataset)
    except ValueError:
        logger.exception("Elexon %s returned invalid JSON or an unexpected shape", dataset)
        raise


async def load_day(delivery_date: date, cutoff_hour: int = 10) -> dict:
    """Load delivery-date actuals and all forecast issues published by the cutoff.

    FUELHH supports settlementDateFrom/To on the dataset endpoint. This is the
    correct selector for historical actuals; publication timestamps describe
    ingestion/revisions and do not identify the delivery period. WINDFOR uses
    publication-time filters to retrieve candidate forecast vintages.
    """
    day_start = datetime.combine(delivery_date, time.min, tzinfo=LONDON)
    day_end = day_start + timedelta(days=1)
    cutoff = datetime.combine(delivery_date - timedelta(days=1), time(cutoff_hour), tzinfo=LONDON)
    forecast_from = cutoff - timedelta(days=2)
    timeout = httpx.Timeout(25.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        actuals, forecasts = await asyncio.gather(
            _get_records(client, "FUELHH", {
                "settlementDateFrom": delivery_date.isoformat(),
                "settlementDateTo": delivery_date.isoformat(),
                "format": "json",
            }, stream=False),
            _get_records(client, "WINDFOR", {
                "publishDateTimeFrom": _utc(forecast_from),
                "publishDateTimeTo": _utc(cutoff),
            }),
        )
    return {"actuals": actuals, "forecasts": forecasts, "cutoff": cutoff, "day_start": day_start, "day_end": day_end}
