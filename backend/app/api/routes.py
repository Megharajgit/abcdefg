"""Wind procurement dashboard API routes."""
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from app.services.analysis import analyze
from app.services.elexon import load_day
from app.services.preview import preview_day

router = APIRouter()

@router.get("/health", tags=["system"])
def health_check() -> dict[str, str | bool]:
    return {"ok": True, "service": "wind-signal-api"}

@router.get("/dashboard", tags=["wind"])
async def dashboard(delivery_date: date = Query(alias="date"), cutoff_hour: int = Query(default=10, ge=0, le=23)) -> dict:
    """Return pre-cutoff forecasts, actuals, and error metrics for a Jan 2026 day."""
    if delivery_date.year != 2026 or delivery_date.month != 1:
        raise HTTPException(status_code=422, detail="This pilot is scoped to January 2026 delivery days.")
    try:
        result = analyze(delivery_date, await load_day(delivery_date, cutoff_hour), cutoff_hour)
        if result["metrics"]["forecastCoverage"] == 0:
            raise ValueError("Elexon returned no matching forecast periods")
        return result
    except Exception as exc:
        # Keep the UI usable during a demo; the mode and notice make the fallback explicit.
        result = preview_day(delivery_date, cutoff_hour)
        result["notice"] = f"Showing synthetic preview because live Elexon data could not be loaded ({type(exc).__name__})."
        return result
