"""adsb.lol provider (default). Public REST API, data under ODbL 1.0.

API reference: https://api.adsb.lol/docs
"""

import math
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx2

from skytripwire import __version__
from skytripwire.providers.base import (
    Aircraft,
    AreaQuery,
    DataField,
    GlobalField,
    ProviderError,
    ProviderUnavailableError,
    Query,
    RateLimitedError,
    airline_from_callsign,
)

MAX_RADIUS_NM = 250
_MILITARY_FLAG = 1

_GLOBAL_PATHS: dict[GlobalField, str] = {
    GlobalField.TYPE: "/v2/type/{}",
    GlobalField.REGISTRATION: "/v2/reg/{}",
    GlobalField.CALLSIGN: "/v2/callsign/{}",
    GlobalField.SQUAWK: "/v2/sqk/{}",
    GlobalField.HEX: "/v2/hex/{}",
    GlobalField.MILITARY: "/v2/mil",
}


class AdsbLolProvider:
    def __init__(
        self,
        base_url: str = "https://api.adsb.lol",
        api_key: str | None = None,
        *,
        timeout: float = 20.0,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"User-Agent": f"SkyTripwire/{__version__}", "Accept": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx2.AsyncClient(
            base_url=base_url, headers=headers, timeout=timeout, transport=transport
        )

    @property
    def name(self) -> str:
        return "adsblol"

    @property
    def provides(self) -> frozenset[DataField]:
        return frozenset({DataField.MILITARY, DataField.CATEGORY, DataField.EMERGENCY})

    def supports(self, query: Query) -> bool:
        if isinstance(query, AreaQuery):
            return query.radius_nm <= MAX_RADIUS_NM
        return query.field in _GLOBAL_PATHS

    async def fetch(self, query: Query) -> list[Aircraft]:
        if not self.supports(query):
            raise ValueError(f"adsb.lol cannot answer {query!r}")
        try:
            response = await self._client.get(_path(query))
        except httpx2.TransportError as exc:
            raise ProviderUnavailableError(f"adsb.lol request failed: {exc!r}") from exc

        if response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
            raise RateLimitedError(
                "adsb.lol quota exceeded", _retry_after(response.headers.get("Retry-After"))
            )
        if response.is_server_error:
            raise ProviderUnavailableError(f"adsb.lol answered HTTP {response.status_code}")
        if response.status_code != httpx2.codes.OK:
            raise ProviderError(f"adsb.lol answered HTTP {response.status_code}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("adsb.lol returned invalid JSON") from exc
        return parse_response(payload)

    async def aclose(self) -> None:
        await self._client.aclose()


def _path(query: Query) -> str:
    if isinstance(query, AreaQuery):
        radius = max(1, math.ceil(query.radius_nm))
        return f"/v2/point/{query.latitude:.4f}/{query.longitude:.4f}/{radius}"
    template = _GLOBAL_PATHS[query.field]
    return template.format(quote(query.value, safe=""))


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def parse_response(payload: Any) -> list[Aircraft]:
    if not isinstance(payload, Mapping) or not isinstance(payload.get("ac"), list):
        raise ProviderError("adsb.lol response has no aircraft list")
    now_ms = _number(payload.get("now"))
    now = datetime.fromtimestamp(now_ms / 1000, tz=UTC) if now_ms else datetime.now(UTC)
    return [
        aircraft
        for item in payload["ac"]
        if isinstance(item, Mapping) and (aircraft := parse_aircraft(item, now)) is not None
    ]


def parse_aircraft(item: Mapping[str, Any], now: datetime) -> Aircraft | None:
    hex_code = _text(item.get("hex"))
    if hex_code is None:
        return None
    hex_code = hex_code.lower()

    alt_baro = item.get("alt_baro")
    on_ground = alt_baro == "ground"
    altitude = 0 if on_ground else _integer(alt_baro)

    callsign = _text(item.get("flight"))
    callsign = callsign.upper() if callsign else None
    emergency = _text(item.get("emergency"))
    seen = _number(item.get("seen")) or 0.0
    db_flags = _integer(item.get("dbFlags")) or 0
    vertical_rate = _integer(item.get("baro_rate"))
    if vertical_rate is None:
        vertical_rate = _integer(item.get("geom_rate"))

    return Aircraft(
        provider="adsblol",
        source_id=hex_code,
        hex=hex_code,
        latitude=_number(item.get("lat")),
        longitude=_number(item.get("lon")),
        altitude_ft=altitude,
        on_ground=on_ground,
        ground_speed_kts=_number(item.get("gs")),
        vertical_rate_fpm=vertical_rate,
        track_deg=_number(item.get("track")),
        callsign=callsign,
        registration=_upper(item.get("r")),
        type_code=_upper(item.get("t")),
        airline_icao=airline_from_callsign(callsign),
        squawk=_text(item.get("squawk")),
        emergency=None if emergency in (None, "none") else emergency,
        category=_upper(item.get("category")),
        military=bool(db_flags & _MILITARY_FLAG),
        seen_at=now - timedelta(seconds=seen),
    )


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _upper(value: Any) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return round(number) if number is not None else None
