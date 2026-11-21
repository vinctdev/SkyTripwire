"""Optional Flightradar24 provider via the unofficial ``FlightRadarAPI`` library.

Opt-in only. The data is proprietary: personal and educational use only, commercial
use requires contacting Flightradar24. If FR24 blocks requests, we stop and report it.
We never work around a block.
"""

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol

import anyio
from curl_cffi.requests.exceptions import RequestException
from FlightRadarAPI import CloudflareError, FlightRadar24API, FlightRadarError

from skytripwire.providers.base import (
    Aircraft,
    AreaQuery,
    DataField,
    GlobalField,
    GlobalQuery,
    ProviderBlockedError,
    ProviderError,
    ProviderUnavailableError,
    Query,
)

_METERS_PER_NM = 1852
_MISSING = (None, "", "N/A")
_GLOBAL_FIELDS = frozenset({GlobalField.TYPE, GlobalField.REGISTRATION, GlobalField.AIRLINE})


class FeedClient(Protocol):
    """The part of ``FlightRadar24API`` we use. Allows a fake in tests."""

    def get_bounds_by_point(self, latitude: float, longitude: float, radius: float) -> str: ...

    def get_flights(
        self,
        airline: str | None = None,
        bounds: str | None = None,
        registration: str | None = None,
        aircraft_type: str | None = None,
    ) -> list[Any]: ...


def _default_client(timeout: int) -> FeedClient:
    api = FlightRadar24API(timeout=timeout)
    # Aircraft only, no ground vehicles.
    api.set_flight_tracker_config(vehicles=0)
    return api


class Fr24Provider:
    def __init__(
        self,
        *,
        timeout: int = 30,
        client_factory: Callable[[], FeedClient] | None = None,
    ) -> None:
        self._factory = client_factory or (lambda: _default_client(timeout))
        self._client: FeedClient | None = None
        # The library keeps a session with cookies; do not use it from two threads at once.
        self._lock = anyio.Lock()

    @property
    def name(self) -> str:
        return "fr24"

    @property
    def provides(self) -> frozenset[DataField]:
        return frozenset({DataField.ROUTE})

    def supports(self, query: Query) -> bool:
        if isinstance(query, AreaQuery):
            return True
        return query.field in _GLOBAL_FIELDS

    async def fetch(self, query: Query) -> list[Aircraft]:
        if not self.supports(query):
            raise ValueError(f"FR24 cannot answer {query!r}")
        async with self._lock:
            flights = await anyio.to_thread.run_sync(self._fetch_sync, query)
        return [aircraft for f in flights if (aircraft := flight_to_aircraft(f)) is not None]

    def _fetch_sync(self, query: Query) -> list[Any]:
        try:
            if self._client is None:
                self._client = self._factory()
            client = self._client
            if isinstance(query, AreaQuery):
                bounds = client.get_bounds_by_point(
                    query.latitude, query.longitude, query.radius_nm * _METERS_PER_NM
                )
                return client.get_flights(bounds=bounds)
            return client.get_flights(**_global_kwargs(query))
        except CloudflareError as exc:
            raise ProviderBlockedError("FR24 blocked the request (Cloudflare)") from exc
        except (FlightRadarError, RequestException) as exc:
            raise ProviderUnavailableError(f"FR24 request failed: {exc!r}") from exc
        except ValueError as exc:
            raise ProviderError("FR24 returned an unexpected response") from exc

    async def aclose(self) -> None:
        self._client = None


def _global_kwargs(query: GlobalQuery) -> dict[str, str]:
    match query.field:
        case GlobalField.TYPE:
            return {"aircraft_type": query.value}
        case GlobalField.REGISTRATION:
            return {"registration": query.value}
        case GlobalField.AIRLINE:
            return {"airline": query.value}
        case _:
            raise ValueError(f"unsupported field {query.field}")


def flight_to_aircraft(flight: Any) -> Aircraft | None:
    """Convert a ``FlightRadarAPI.Flight`` into an :class:`Aircraft`."""
    source_id = _text(getattr(flight, "id", None))
    if source_id is None:
        return None
    hex_code = _text(flight.icao_24bit)
    timestamp = _number(flight.time)
    callsign = _text(flight.callsign)
    return Aircraft(
        provider="fr24",
        source_id=source_id,
        hex=hex_code.lower() if hex_code else None,
        latitude=_number(flight.latitude),
        longitude=_number(flight.longitude),
        altitude_ft=_integer(flight.altitude),
        on_ground=bool(_integer(flight.on_ground)),
        ground_speed_kts=_number(flight.ground_speed),
        vertical_rate_fpm=_integer(flight.vertical_speed),
        track_deg=_number(flight.heading),
        callsign=callsign.upper() if callsign else None,
        registration=_upper(flight.registration),
        type_code=_upper(flight.aircraft_code),
        airline_icao=_upper(flight.airline_icao),
        squawk=_text(flight.squawk),
        origin_iata=_upper(flight.origin_airport_iata),
        destination_iata=_upper(flight.destination_airport_iata),
        seen_at=datetime.fromtimestamp(timestamp, tz=UTC) if timestamp else datetime.now(UTC),
    )


def _text(value: Any) -> str | None:
    if value in _MISSING:
        return None
    text = str(value).strip()
    return text or None


def _upper(value: Any) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _number(value: Any) -> float | None:
    if value in _MISSING or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return round(number) if number is not None else None
