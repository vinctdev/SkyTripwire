"""Match aircraft against filter criteria. Pure functions, no I/O.

Rules:
- Lists are OR within a field, fields are AND with each other. Empty list means "any".
- A criterion that is set never matches an aircraft where the value is unknown.
  Exception: "exclude military" lets aircraft with unknown military status through.
- Type, registration and callsign accept shell-style wildcards (``DLH*``, ``B74?``).
- Registrations are compared without hyphens and spaces (``DAIMA`` equals ``D-AIMA``).
"""

import re
from dataclasses import dataclass
from fnmatch import fnmatchcase

from skytripwire.db.models import Filter
from skytripwire.engine.geo import distance_nm
from skytripwire.providers.base import Aircraft

EMERGENCY_SQUAWKS = frozenset({"7500", "7600", "7700"})

_WILDCARD = re.compile(r"[*?\[]")
_REGISTRATION_NOISE = re.compile(r"[\s-]")


@dataclass(frozen=True, slots=True)
class Area:
    latitude: float
    longitude: float
    radius_nm: float


@dataclass(frozen=True, slots=True)
class Patterns:
    """A set of exact values plus wildcard patterns, matched case-insensitively."""

    exact: frozenset[str] = frozenset()
    wildcards: tuple[str, ...] = ()
    # Exact values as entered (uppercase, but e.g. with the registration hyphen), for queries.
    originals: tuple[str, ...] = ()

    @classmethod
    def build(cls, values: list[str], *, registration: bool = False) -> "Patterns":
        cleaned = list(dict.fromkeys(v.strip().upper() for v in values if v.strip()))
        plain = [v for v in cleaned if not _WILDCARD.search(v)]
        return cls(
            exact=frozenset(_normalize(v, registration=registration) for v in plain),
            wildcards=tuple(
                _normalize(v, registration=registration) for v in cleaned if _WILDCARD.search(v)
            ),
            originals=tuple(plain),
        )

    def __bool__(self) -> bool:
        return bool(self.exact or self.wildcards)

    def matches(self, value: str | None, *, registration: bool = False) -> bool:
        if value is None:
            return False
        value = _normalize(value, registration=registration)
        return value in self.exact or any(fnmatchcase(value, p) for p in self.wildcards)


@dataclass(frozen=True, slots=True)
class Criteria:
    """Immutable, normalized form of a :class:`Filter`, ready for fast matching."""

    filter_id: int | None
    name: str
    area: Area | None = None
    type_codes: Patterns = Patterns()
    registrations: Patterns = Patterns()
    callsigns: Patterns = Patterns()
    airlines: frozenset[str] = frozenset()
    squawks: frozenset[str] = frozenset()
    categories: frozenset[str] = frozenset()
    military: bool | None = None
    emergency_only: bool = False
    include_on_ground: bool = False
    altitude_min_ft: int | None = None
    altitude_max_ft: int | None = None
    ground_speed_min_kts: float | None = None
    ground_speed_max_kts: float | None = None
    origin_airports: frozenset[str] = frozenset()
    destination_airports: frozenset[str] = frozenset()
    cooldown_minutes: int = 60

    @classmethod
    def from_filter(cls, f: Filter) -> "Criteria":
        area = None
        if (
            f.area_latitude is not None
            and f.area_longitude is not None
            and f.area_radius_nm is not None
        ):
            area = Area(f.area_latitude, f.area_longitude, f.area_radius_nm)
        return cls(
            filter_id=f.id,
            name=f.name,
            area=area,
            type_codes=Patterns.build(f.type_codes),
            registrations=Patterns.build(f.registrations, registration=True),
            callsigns=Patterns.build(f.callsigns),
            airlines=_upper_set(f.airlines),
            squawks=_upper_set(f.squawks),
            categories=_upper_set(f.categories),
            military=f.military,
            emergency_only=f.emergency_only,
            include_on_ground=f.include_on_ground,
            altitude_min_ft=f.altitude_min_ft,
            altitude_max_ft=f.altitude_max_ft,
            ground_speed_min_kts=f.ground_speed_min_kts,
            ground_speed_max_kts=f.ground_speed_max_kts,
            origin_airports=_upper_set(f.origin_airports),
            destination_airports=_upper_set(f.destination_airports),
            cooldown_minutes=f.cooldown_minutes,
        )


def matches(criteria: Criteria, aircraft: Aircraft) -> bool:  # noqa: PLR0911
    """Whether the aircraft satisfies every criterion of the filter."""
    if aircraft.on_ground and not criteria.include_on_ground:
        return False
    if criteria.area is not None and not in_area(criteria.area, aircraft):
        return False
    if not _identity_matches(criteria, aircraft):
        return False
    if not _flags_match(criteria, aircraft):
        return False
    if not _in_range(aircraft.altitude_ft, criteria.altitude_min_ft, criteria.altitude_max_ft):
        return False
    if not _in_range(
        aircraft.ground_speed_kts, criteria.ground_speed_min_kts, criteria.ground_speed_max_kts
    ):
        return False
    return _in_set(aircraft.origin_iata, criteria.origin_airports) and _in_set(
        aircraft.destination_iata, criteria.destination_airports
    )


def in_area(area: Area, aircraft: Aircraft) -> bool:
    if aircraft.latitude is None or aircraft.longitude is None:
        return False
    distance = distance_nm(area.latitude, area.longitude, aircraft.latitude, aircraft.longitude)
    return distance <= area.radius_nm


def _identity_matches(criteria: Criteria, aircraft: Aircraft) -> bool:
    if criteria.type_codes and not criteria.type_codes.matches(aircraft.type_code):
        return False
    if criteria.registrations and not criteria.registrations.matches(
        aircraft.registration, registration=True
    ):
        return False
    if criteria.callsigns and not criteria.callsigns.matches(aircraft.callsign):
        return False
    return _in_set(aircraft.airline_icao, criteria.airlines)


def _flags_match(criteria: Criteria, aircraft: Aircraft) -> bool:
    if not _in_set(aircraft.squawk, criteria.squawks):
        return False
    if not _in_set(aircraft.category, criteria.categories):
        return False
    if criteria.military is True and aircraft.military is not True:
        return False
    if criteria.military is False and aircraft.military is True:
        return False
    return not criteria.emergency_only or is_emergency(aircraft)


def is_emergency(aircraft: Aircraft) -> bool:
    return aircraft.emergency is not None or aircraft.squawk in EMERGENCY_SQUAWKS


def _in_set(value: str | None, allowed: frozenset[str]) -> bool:
    if not allowed:
        return True
    return value is not None and value.upper() in allowed


def _in_range(value: float | None, low: float | None, high: float | None) -> bool:
    if low is None and high is None:
        return True
    if value is None:
        return False
    return (low is None or value >= low) and (high is None or value <= high)


def _normalize(value: str, *, registration: bool) -> str:
    value = value.strip().upper()
    return _REGISTRATION_NOISE.sub("", value) if registration else value


def _upper_set(values: list[str]) -> frozenset[str]:
    return frozenset(v.strip().upper() for v in values if v.strip())
