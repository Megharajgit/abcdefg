"""Wind procurement dashboard API routes."""
from datetime import date
import logging

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.services.analysis import analyze
from app.services.elexon import load_day
from app.services.preview import preview_day

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str | bool]:
    return {"ok": True, "service": "wind-signal-api"}


@router.get("/dashboard", tags=["wind"])
async def dashboard(
    delivery_date: date = Query(alias="date"),
    cutoff_hour: int = Query(default=10, ge=0, le=23),
) -> dict:
    """Return forecasts available by the cutoff, actuals, and error metrics."""
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(status_code=422, detail="This pilot is scoped to January 2026 delivery days.")
    try:
        raw = await load_day(delivery_date, cutoff_hour)
        result = analyze(delivery_date, raw, cutoff_hour)
        if result["metrics"]["matchedPeriods"] == 0 and result["metrics"]["forecastPeriods"] == 0:
            result["notice"] = (
                "Elexon returned no eligible forecasts for this delivery date and cutoff. "
                "Missing values remain null and accuracy metrics are unavailable until periods match."
            )
        elif result["metrics"]["matchedPeriods"] == 0 and result["metrics"]["actualPeriods"] == 0:
            result["notice"] = (
                "Elexon returned no actual observations for this delivery date. "
                "The live forecasts remain visible; accuracy metrics are unavailable until actuals arrive."
            )
        elif result["metrics"]["matchedPeriods"] == 0:
            result["notice"] = "Live data was returned, but no settlement periods have both an eligible forecast and an actual observation."
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning("Elexon returned HTTP %s for dashboard request", exc.response.status_code)
        result = preview_day(delivery_date, cutoff_hour)
        result["notice"] = f"Elexon returned HTTP {exc.response.status_code}; showing synthetic preview data."
        return result
    except httpx.RequestError:
        logger.exception("Could not reach Elexon")
        result = preview_day(delivery_date, cutoff_hour)
        result["notice"] = "Could not reach Elexon; showing synthetic preview data."
        return result
    except ValueError as exc:
        logger.warning("Elexon data could not be matched: %s", exc)
        result = preview_day(delivery_date, cutoff_hour)
        result["notice"] = f"{exc} Showing synthetic preview data."
        return result
    except Exception as exc:
        logger.exception("Unexpected dashboard data error")
        raise HTTPException(status_code=502, detail="Dashboard data processing failed. Check the API logs for details.") from exc
