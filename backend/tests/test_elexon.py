import asyncio
from datetime import date

import httpx

from app.services import elexon


def test_actuals_use_delivery_settlement_date_and_forecasts_use_publish_window(monkeypatch):
    seen = []
    async def handler(request):
        seen.append(request)
        if "/FUELHH" in request.url.path:
            return httpx.Response(200, json={"data": [{"fuelType": "WIND", "generation": 1}]})
        return httpx.Response(200, json=[{"generation": 2}])
    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    def client_factory(*args, **kwargs):
        return original_client(*args, transport=transport, **kwargs)
    monkeypatch.setattr(elexon.httpx, "AsyncClient", client_factory)
    result = asyncio.run(elexon.load_day(date(2026, 1, 15), 10))
    assert result["actuals"][0]["fuelType"] == "WIND"
    assert result["forecasts"][0]["generation"] == 2
    actual = next(request for request in seen if "/FUELHH" in request.url.path)
    forecast = next(request for request in seen if "/WINDFOR/stream" in request.url.path)
    assert actual.url.params["settlementDateFrom"] == "2026-01-15"
    assert actual.url.params["settlementDateTo"] == "2026-01-15"
    assert "publishDateTimeFrom" not in actual.url.params
    assert forecast.url.params["publishDateTimeTo"] == "2026-01-14T10:00:00Z"
    assert forecast.url.params["publishDateTimeFrom"] == "2026-01-12T10:00:00Z"


def test_transient_elexon_failure_retries_then_returns_records(monkeypatch):
    from app.services import elexon as module
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) == 1 else 200, json=[])
    transport = httpx.MockTransport(handler)
    original_client = httpx.AsyncClient
    def client_factory(*args, **kwargs):
        return original_client(*args, transport=transport, **kwargs)
    monkeypatch.setattr(module.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(module.asyncio, "sleep", _no_sleep)
    async def run():
        async with original_client(transport=transport) as client:
            return await module._get_records(client, "WINDFOR", {"from": "a", "to": "b"})
    assert asyncio.run(run()) == []
    assert len(calls) == 2


async def _no_sleep(_delay):
    return None
