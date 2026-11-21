from datetime import UTC, datetime
from typing import Any

import pytest
from FlightRadarAPI import CloudflareError, Flight, FlightRadarError

from skytripwire.config import Settings
from skytripwire.providers import build_providers
from skytripwire.providers.base import (
    AreaQuery,
    GlobalField,
    GlobalQuery,
    ProviderBlockedError,
    ProviderUnavailableError,
)
from skytripwire.providers.fr24 import Fr24Provider, flight_to_aircraft

pytestmark = pytest.mark.anyio


def make_flight(flight_id: str = "3a1b2c3d", **overrides: Any) -> Flight:
    # Synthetic feed entry, field order as in FlightRadarAPI.entities.flight._Field.
    info: list[Any] = [
        "3C6444",
        50.1032,
        8.7741,
        251,
        12025,
        310,
        "1000",
        "F-EDDF1",
        "A319",
        "D-AIBD",
        1795017600,
        "FRA",
        "MUC",
        "LH123",
        0,
        -1216,
        "DLH4AB",
        0,
        "DLH",
    ]
    fields = {"hex": 0, "altitude": 4, "registration": 9, "on_ground": 14, "callsign": 16}
    for name, value in overrides.items():
        info[fields[name]] = value
    return Flight(flight_id, info)


class FakeClient:
    def __init__(self, flights: list[Flight] | None = None, error: Exception | None = None):
        self.flights = flights or []
        self.error = error
        self.calls: list[dict[str, Any]] = []
        self.bounds_args: tuple[float, float, float] | None = None

    def get_bounds_by_point(self, latitude: float, longitude: float, radius: float) -> str:
        self.bounds_args = (latitude, longitude, radius)
        return "BOUNDS"

    def get_flights(
        self,
        airline: str | None = None,
        bounds: str | None = None,
        registration: str | None = None,
        aircraft_type: str | None = None,
    ) -> list[Any]:
        self.calls.append(
            {
                "airline": airline,
                "bounds": bounds,
                "registration": registration,
                "aircraft_type": aircraft_type,
            }
        )
        if self.error:
            raise self.error
        return list(self.flights)


def test_flight_to_aircraft() -> None:
    aircraft = flight_to_aircraft(make_flight())
    assert aircraft is not None
    assert aircraft.provider == "fr24"
    assert aircraft.source_id == "3a1b2c3d"
    assert aircraft.hex == "3c6444"
    assert aircraft.identity == "3c6444"
    assert (aircraft.latitude, aircraft.longitude) == (50.1032, 8.7741)
    assert aircraft.altitude_ft == 12025
    assert aircraft.on_ground is False
    assert aircraft.ground_speed_kts == 310
    assert aircraft.vertical_rate_fpm == -1216
    assert aircraft.track_deg == 251
    assert aircraft.callsign == "DLH4AB"
    assert aircraft.registration == "D-AIBD"
    assert aircraft.type_code == "A319"
    assert aircraft.airline_icao == "DLH"
    assert aircraft.squawk == "1000"
    assert aircraft.origin_iata == "FRA"
    assert aircraft.destination_iata == "MUC"
    assert aircraft.military is None
    assert aircraft.category is None
    assert aircraft.seen_at == datetime.fromtimestamp(1795017600, tz=UTC)


def test_flight_to_aircraft_missing_values() -> None:
    aircraft = flight_to_aircraft(
        make_flight(hex="", registration="N/A", callsign="", on_ground=1, altitude=0)
    )
    assert aircraft is not None
    assert aircraft.hex is None
    assert aircraft.identity == "fr24:3a1b2c3d"
    assert aircraft.registration is None
    assert aircraft.callsign is None
    assert aircraft.on_ground is True


def test_supports() -> None:
    provider = Fr24Provider(client_factory=FakeClient)
    assert provider.supports(AreaQuery(50, 8, 600))
    assert provider.supports(GlobalQuery(GlobalField.AIRLINE, "DLH"))
    assert provider.supports(GlobalQuery(GlobalField.TYPE, "A388"))
    assert provider.supports(GlobalQuery(GlobalField.REGISTRATION, "D-AIMA"))
    assert not provider.supports(GlobalQuery(GlobalField.CALLSIGN, "DLH4AB"))
    assert not provider.supports(GlobalQuery(GlobalField.MILITARY))


async def test_area_query_uses_bounds_in_meters() -> None:
    client = FakeClient([make_flight()])
    provider = Fr24Provider(client_factory=lambda: client)
    result = await provider.fetch(AreaQuery(50.0, 8.5, 10))
    assert [a.registration for a in result] == ["D-AIBD"]
    assert client.bounds_args == (50.0, 8.5, 18520)
    assert client.calls[0]["bounds"] == "BOUNDS"


@pytest.mark.parametrize(
    ("query", "kwarg"),
    [
        (GlobalQuery(GlobalField.AIRLINE, "dlh"), ("airline", "DLH")),
        (GlobalQuery(GlobalField.TYPE, "A388"), ("aircraft_type", "A388")),
        (GlobalQuery(GlobalField.REGISTRATION, "D-AIMA"), ("registration", "D-AIMA")),
    ],
)
async def test_global_queries(query: GlobalQuery, kwarg: tuple[str, str]) -> None:
    client = FakeClient()
    provider = Fr24Provider(client_factory=lambda: client)
    await provider.fetch(query)
    name, value = kwarg
    assert client.calls[0][name] == value


async def test_client_is_created_once() -> None:
    created: list[FakeClient] = []

    def factory() -> FakeClient:
        created.append(FakeClient())
        return created[-1]

    provider = Fr24Provider(client_factory=factory)
    await provider.fetch(GlobalQuery(GlobalField.TYPE, "A388"))
    await provider.fetch(GlobalQuery(GlobalField.TYPE, "B744"))
    assert len(created) == 1


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (CloudflareError("blocked", None), ProviderBlockedError),
        (FlightRadarError("boom"), ProviderUnavailableError),
    ],
)
async def test_errors_are_mapped(error: Exception, expected: type[Exception]) -> None:
    provider = Fr24Provider(client_factory=lambda: FakeClient(error=error))
    with pytest.raises(expected):
        await provider.fetch(GlobalQuery(GlobalField.TYPE, "A388"))


async def test_build_providers(settings: Settings) -> None:
    default = build_providers(settings)
    settings.fr24_enabled = True
    with_fr24 = build_providers(settings)
    assert [p.name for p in default] == ["adsblol"]
    assert [p.name for p in with_fr24] == ["adsblol", "fr24"]
    for provider in default + with_fr24:
        await provider.aclose()
