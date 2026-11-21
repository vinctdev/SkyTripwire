from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from skytripwire.providers.adsblol import AdsbLolProvider, parse_response
from skytripwire.providers.base import (
    AreaQuery,
    GlobalField,
    GlobalQuery,
    ProviderError,
    ProviderUnavailableError,
    Query,
    RateLimitedError,
)
from tests.conftest import load_fixture

pytestmark = pytest.mark.anyio

EMPTY = {"ac": [], "msg": "No error", "now": 0, "total": 0, "ctime": 0, "ptime": 0}

type Handler = Callable[[httpx2.Request], httpx2.Response]


def make_provider(handler: Handler, api_key: str | None = None) -> AdsbLolProvider:
    return AdsbLolProvider(
        "https://api.example.test", api_key, transport=httpx2.MockTransport(handler)
    )


def recorder() -> tuple[list[httpx2.Request], Handler]:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=EMPTY)

    return requests, handler


@pytest.mark.parametrize(
    ("query", "path"),
    [
        (AreaQuery(50.0379, 8.5622, 30), "/v2/point/50.0379/8.5622/30"),
        (AreaQuery(-33.94612, 151.17722, 12.2), "/v2/point/-33.9461/151.1772/13"),
        (AreaQuery(0, 0, 0.3), "/v2/point/0.0000/0.0000/1"),
        (GlobalQuery(GlobalField.TYPE, "a388"), "/v2/type/A388"),
        (GlobalQuery(GlobalField.REGISTRATION, "D-AIMA"), "/v2/reg/D-AIMA"),
        (GlobalQuery(GlobalField.CALLSIGN, "dlh 4ab"), "/v2/callsign/DLH%204AB"),
        (GlobalQuery(GlobalField.SQUAWK, "7700"), "/v2/sqk/7700"),
        (GlobalQuery(GlobalField.HEX, "3C6444"), "/v2/hex/3c6444"),
        (GlobalQuery(GlobalField.MILITARY), "/v2/mil"),
    ],
)
async def test_request_path(query: Query, path: str) -> None:
    requests, handler = recorder()
    provider = make_provider(handler)
    assert await provider.fetch(query) == []
    assert requests[0].url.raw_path.decode() == path
    await provider.aclose()


async def test_headers_with_and_without_api_key() -> None:
    requests, handler = recorder()
    with_key = make_provider(handler, api_key="secret")
    without_key = make_provider(handler)
    await with_key.fetch(GlobalQuery(GlobalField.MILITARY))
    await without_key.fetch(GlobalQuery(GlobalField.MILITARY))
    assert requests[0].headers["x-api-key"] == "secret"
    assert "x-api-key" not in requests[1].headers
    assert requests[1].headers["user-agent"].startswith("SkyTripwire/")
    await with_key.aclose()
    await without_key.aclose()


def test_supports() -> None:
    provider = AdsbLolProvider()
    assert provider.supports(AreaQuery(50, 8, 250))
    assert not provider.supports(AreaQuery(50, 8, 250.5))
    assert provider.supports(GlobalQuery(GlobalField.CALLSIGN, "DLH4AB"))
    assert not provider.supports(GlobalQuery(GlobalField.AIRLINE, "DLH"))


async def test_unsupported_query_raises() -> None:
    provider = make_provider(recorder()[1])
    with pytest.raises(ValueError, match="cannot answer"):
        await provider.fetch(GlobalQuery(GlobalField.AIRLINE, "DLH"))
    await provider.aclose()


@pytest.mark.parametrize(("header", "expected"), [("120", 120.0), ("soon", None), (None, None)])
async def test_rate_limit(header: str | None, expected: float | None) -> None:
    headers = {"Retry-After": header} if header is not None else {}
    provider = make_provider(lambda _: httpx2.Response(429, headers=headers, text="rate limit"))
    with pytest.raises(RateLimitedError) as info:
        await provider.fetch(GlobalQuery(GlobalField.MILITARY))
    assert info.value.retry_after == expected
    await provider.aclose()


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx2.Response(503), ProviderUnavailableError),
        (httpx2.Response(422, json={"detail": []}), ProviderError),
        (httpx2.Response(200, text="<html>"), ProviderError),
        (httpx2.Response(200, json={"msg": "No error"}), ProviderError),
    ],
)
async def test_error_responses(response: httpx2.Response, error: type[ProviderError]) -> None:
    provider = make_provider(lambda _: response)
    with pytest.raises(error):
        await provider.fetch(GlobalQuery(GlobalField.MILITARY))
    await provider.aclose()


async def test_transport_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    provider = make_provider(handler)
    with pytest.raises(ProviderUnavailableError):
        await provider.fetch(GlobalQuery(GlobalField.MILITARY))
    await provider.aclose()


def test_parse_response() -> None:
    aircraft = parse_response(load_fixture("adsblol_point.json"))
    now = datetime(2026, 11, 18, 16, 0, tzinfo=UTC)
    assert [a.hex for a in aircraft] == ["3c6444", "3c4b26", "ae1234", "~2a0f1c"]

    airliner, ground, military, tisb = aircraft
    assert airliner.provider == "adsblol"
    assert airliner.source_id == "3c6444"
    assert airliner.callsign == "DLH4AB"
    assert airliner.airline_icao == "DLH"
    assert airliner.registration == "D-AIBD"
    assert airliner.type_code == "A319"
    assert airliner.altitude_ft == 12025
    assert airliner.on_ground is False
    assert airliner.ground_speed_kts == 310.4
    assert airliner.vertical_rate_fpm == -1216
    assert airliner.track_deg == 251.3
    assert airliner.squawk == "1000"
    assert airliner.emergency is None
    assert airliner.category == "A3"
    assert airliner.military is False
    assert (airliner.latitude, airliner.longitude) == (50.1032, 8.7741)
    assert airliner.seen_at == now - timedelta(seconds=0.4)

    assert ground.on_ground is True
    assert ground.altitude_ft == 0
    assert ground.callsign == "D-EXYZ"
    assert ground.airline_icao is None

    assert military.military is True
    assert military.emergency == "general"
    assert military.squawk == "7700"
    assert military.category == "A7"
    assert military.vertical_rate_fpm == 64
    assert military.latitude is None
    assert military.callsign is None

    assert tisb.registration is None
    assert tisb.type_code is None
