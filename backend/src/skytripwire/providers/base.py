"""Provider interface, query types and the normalized aircraft record.

Filters and the matcher only ever see :class:`Aircraft`. Each data source translates
its own response format into it, and leaves fields it cannot fill as ``None``.
"""

import math
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

_AIRLINE_CALLSIGN = re.compile(r"^([A-Z]{3})\d")
_SQUAWK = re.compile(r"^[0-7]{4}$")
_MAX_LATITUDE = 90.0
_MAX_LONGITUDE = 180.0


@dataclass(frozen=True, slots=True, kw_only=True)
class Aircraft:
    """One aircraft as seen by a provider at one point in time."""

    provider: str
    # Provider specific id, stable for the duration of a flight.
    source_id: str
    # 24-bit ICAO address in lowercase hex. A leading "~" marks a non-ICAO address.
    hex: str | None = None

    latitude: float | None = None
    longitude: float | None = None
    altitude_ft: int | None = None
    on_ground: bool = False
    ground_speed_kts: float | None = None
    vertical_rate_fpm: int | None = None
    track_deg: float | None = None

    callsign: str | None = None
    registration: str | None = None
    type_code: str | None = None
    airline_icao: str | None = None
    squawk: str | None = None
    # ADS-B emergency status, None when there is no emergency or it is unknown.
    emergency: str | None = None
    # ADS-B emitter category (A0 to D7).
    category: str | None = None
    # None when the provider does not know (FR24).
    military: bool | None = None

    origin_iata: str | None = None
    destination_iata: str | None = None

    seen_at: datetime

    @property
    def identity(self) -> str:
        """Key used for deduplication, comparable across providers when the hex is known."""
        return self.hex or f"{self.provider}:{self.source_id}"


class DataField(StrEnum):
    """Optional data that only some providers deliver. Used to pick a provider for a filter."""

    ROUTE = "route"
    MILITARY = "military"
    CATEGORY = "category"
    EMERGENCY = "emergency"


class GlobalField(StrEnum):
    """Fields that can be queried without an area."""

    TYPE = "type"
    REGISTRATION = "registration"
    CALLSIGN = "callsign"
    AIRLINE = "airline"
    SQUAWK = "squawk"
    HEX = "hex"
    MILITARY = "military"


@dataclass(frozen=True, slots=True)
class AreaQuery:
    """All aircraft inside a circle."""

    latitude: float
    longitude: float
    radius_nm: float

    def __post_init__(self) -> None:
        if not -_MAX_LATITUDE <= self.latitude <= _MAX_LATITUDE:
            raise ValueError(f"latitude out of range: {self.latitude}")
        if not -_MAX_LONGITUDE <= self.longitude <= _MAX_LONGITUDE:
            raise ValueError(f"longitude out of range: {self.longitude}")
        if not (self.radius_nm > 0 and math.isfinite(self.radius_nm)):
            raise ValueError(f"radius must be positive: {self.radius_nm}")


@dataclass(frozen=True, slots=True)
class GlobalQuery:
    """Aircraft anywhere in the world matching one field."""

    field: GlobalField
    value: str = ""

    def __post_init__(self) -> None:
        value = self.value.strip()
        if self.field is GlobalField.MILITARY:
            if value:
                raise ValueError("military query takes no value")
        elif not value:
            raise ValueError(f"{self.field} query needs a value")
        elif self.field is GlobalField.HEX:
            value = value.lower()
        else:
            value = value.upper()
        if self.field is GlobalField.SQUAWK and not _SQUAWK.match(value):
            raise ValueError(f"invalid squawk: {value!r}")
        object.__setattr__(self, "value", value)


type Query = AreaQuery | GlobalQuery


class Provider(Protocol):
    """A data source. Implementations raise :class:`ProviderError` subclasses on failure."""

    @property
    def name(self) -> str: ...

    @property
    def provides(self) -> frozenset[DataField]:
        """Optional data fields this provider fills in."""
        ...

    def supports(self, query: Query) -> bool:
        """Whether this provider can answer the query with a single request."""
        ...

    async def fetch(self, query: Query) -> list[Aircraft]: ...

    async def aclose(self) -> None: ...


class ProviderError(Exception):
    """The provider failed to answer. Base class of all provider errors."""


class ProviderUnavailableError(ProviderError):
    """Network error, timeout or server error. Usually temporary."""


class RateLimitedError(ProviderError):
    """The request quota is used up."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderBlockedError(ProviderError):
    """The provider actively blocks us (e.g. bot protection). Never work around this."""


def airline_from_callsign(callsign: str | None) -> str | None:
    """ICAO airline designator from an ICAO callsign such as ``DLH4AB``, else None."""
    if not callsign:
        return None
    match = _AIRLINE_CALLSIGN.match(callsign)
    return match.group(1) if match else None
