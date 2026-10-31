import asyncio
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
from httpx import ASGITransport, AsyncClient

from app.api import routes
from app.main import app

LONDON = ZoneInfo("Europe/London")


def get(path: str):
    async def request():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path)
    return asyncio.run(request())


def test_health_endpoint():
    response = get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "service": "wind-signal-api"}


def test_valid_january_date_keeps_empty_live_data_visible(monkeypatch):
    day = date(2026, 1, 15)
    start = datetime.combine(day, time.min, tzinfo=LONDON)
    async def fake_load(*_args, **_kwargs):
        return {"actuals": [], "forecasts": [], "cutoff": datetime.combine(day - timedelta(days=1), time(10), tzinfo=LONDON), "day_start": start, "day_end": start + timedelta(days=1)}
    monkeypatch.setattr(routes, "load_day", fake_load)
    response = get("/api/dashboard?date=2026-01-15&cutoff_hour=10")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert body["metrics"]["expectedPeriods"] == 48
    assert body["metrics"]["forecastPeriods"] == 0
    assert "no eligible forecasts" in body["notice"].lower()


def test_invalid_date_and_cutoff_are_rejected():
    assert get("/api/dashboard?date=2026-02-01").status_code == 422
    assert get("/api/dashboard?date=2026-01-15&cutoff_hour=24").status_code == 422


def test_upstream_failure_returns_explicitly_labelled_preview(monkeypatch):
    async def fail(*_args, **_kwargs):
        raise httpx.ConnectError("upstream offline")
    monkeypatch.setattr(routes, "load_day", fail)
    response = get("/api/dashboard?date=2026-01-15&cutoff_hour=10")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "preview"
    assert "synthetic preview" in body["source"].lower()
    assert "could not reach elexon" in body["notice"].lower()
    assert len(body["periods"]) == 48
    assert body["metrics"]["forecastSourceHours"] == 24
    assert body["metrics"]["forecastPeriods"] == 48


def test_upstream_http_failure_returns_explicitly_labelled_preview(monkeypatch):
    request = httpx.Request("GET", "https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream")
    response = httpx.Response(503, request=request)
    async def fail(*_args, **_kwargs):
        raise httpx.HTTPStatusError("upstream unavailable", request=request, response=response)
    monkeypatch.setattr(routes, "load_day", fail)
    body = get("/api/dashboard?date=2026-01-15&cutoff_hour=10").json()
    assert body["mode"] == "preview"
    assert "http 503" in body["notice"].lower()
