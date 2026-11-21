from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from skytripwire.db.models import Filter
from skytripwire.engine.geo import distance_nm
from skytripwire.engine.matcher import Criteria, matches
from skytripwire.providers.base import Aircraft

FRA = (50.0379, 8.5622)

BASE = Aircraft(
    provider="adsblol",
    source_id="3c6444",
    hex="3c6444",
    latitude=50.1032,
    longitude=8.7741,
    altitude_ft=12025,
    ground_speed_kts=310.4,
    callsign="DLH4AB",
    registration="D-AIBD",
    type_code="A319",
    airline_icao="DLH",
    squawk="1000",
    category="A3",
    military=False,
    seen_at=datetime(2026, 11, 18, 16, tzinfo=UTC),
)


def criteria(**kwargs: Any) -> Criteria:
    return Criteria.from_filter(Filter(id=1, name="test", **kwargs))


def aircraft(**changes: Any) -> Aircraft:
    return replace(BASE, **changes)


def test_empty_filter_matches_everything_airborne() -> None:
    assert matches(criteria(), BASE)


def test_distance() -> None:
    # FRA to MUC is about 162 nm.
    assert distance_nm(*FRA, 48.3538, 11.7861) == pytest.approx(162, abs=1)
    assert distance_nm(*FRA, *FRA) == 0


@pytest.mark.parametrize(("radius", "expected"), [(10, True), (9, False)])
def test_area(radius: float, expected: bool) -> None:
    # BASE is about 9.8 nm from the FRA reference point.
    c = criteria(area_latitude=FRA[0], area_longitude=FRA[1], area_radius_nm=radius)
    assert matches(c, BASE) is expected


def test_area_needs_position() -> None:
    c = criteria(area_latitude=FRA[0], area_longitude=FRA[1], area_radius_nm=100)
    assert not matches(c, aircraft(latitude=None, longitude=None))


def test_ground_aircraft_excluded_by_default() -> None:
    on_ground = aircraft(on_ground=True, altitude_ft=0)
    assert not matches(criteria(), on_ground)
    assert matches(criteria(include_on_ground=True), on_ground)


@pytest.mark.parametrize(
    ("field", "values", "expected"),
    [
        ("type_codes", ["A319", "A320"], True),
        ("type_codes", ["a31?"], True),
        ("type_codes", ["B738"], False),
        ("registrations", ["DAIBD"], True),
        ("registrations", ["d-aib*"], True),
        ("registrations", ["D-AIBE"], False),
        ("callsigns", ["DLH*"], True),
        ("callsigns", ["DLH4AB"], True),
        ("callsigns", ["DLH4A"], False),
        ("airlines", ["dlh", "EWG"], True),
        ("airlines", ["EWG"], False),
        ("squawks", ["1000"], True),
        ("squawks", ["7700"], False),
        ("categories", ["A3"], True),
        ("categories", ["A7", "B1"], False),
        ("type_codes", [" ", ""], True),
    ],
)
def test_list_criteria(field: str, values: list[str], expected: bool) -> None:
    assert matches(criteria(**{field: values}), BASE) is expected


@pytest.mark.parametrize(
    ("field", "values", "attribute"),
    [
        ("type_codes", ["A319"], "type_code"),
        ("registrations", ["D-AIBD"], "registration"),
        ("callsigns", ["DLH*"], "callsign"),
        ("airlines", ["DLH"], "airline_icao"),
        ("categories", ["A3"], "category"),
        ("origin_airports", ["FRA"], "origin_iata"),
    ],
)
def test_unknown_value_does_not_match(field: str, values: list[str], attribute: str) -> None:
    assert not matches(criteria(**{field: values}), aircraft(**{attribute: None}))


def test_fields_are_combined_with_and() -> None:
    assert matches(criteria(type_codes=["A319"], airlines=["DLH"]), BASE)
    assert not matches(criteria(type_codes=["A319"], airlines=["EWG"]), BASE)


@pytest.mark.parametrize(
    ("military_filter", "military_aircraft", "expected"),
    [
        (None, True, True),
        (None, None, True),
        (True, True, True),
        (True, False, False),
        (True, None, False),
        (False, True, False),
        (False, False, True),
        (False, None, True),
    ],
)
def test_military(
    military_filter: bool | None, military_aircraft: bool | None, expected: bool
) -> None:
    assert matches(criteria(military=military_filter), aircraft(military=military_aircraft)) is (
        expected
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({}, False),
        ({"squawk": "7700"}, True),
        ({"squawk": "7500"}, True),
        ({"emergency": "lifeguard"}, True),
    ],
)
def test_emergency_only(changes: dict[str, Any], expected: bool) -> None:
    assert matches(criteria(emergency_only=True), aircraft(**changes)) is expected


@pytest.mark.parametrize(
    ("low", "high", "altitude", "expected"),
    [
        (10000, 15000, 12025, True),
        (12025, 12025, 12025, True),
        (13000, None, 12025, False),
        (None, 12000, 12025, False),
        (None, 5000, None, False),
    ],
)
def test_altitude_range(
    low: int | None, high: int | None, altitude: int | None, expected: bool
) -> None:
    c = criteria(altitude_min_ft=low, altitude_max_ft=high)
    assert matches(c, aircraft(altitude_ft=altitude)) is expected


@pytest.mark.parametrize(
    ("low", "high", "expected"),
    [(300, 320, True), (311, None, False), (None, 300, False)],
)
def test_speed_range(low: float | None, high: float | None, expected: bool) -> None:
    c = criteria(ground_speed_min_kts=low, ground_speed_max_kts=high)
    assert matches(c, BASE) is expected


def test_route() -> None:
    fr24 = aircraft(origin_iata="FRA", destination_iata="MUC")
    assert matches(criteria(origin_airports=["fra"], destination_airports=["MUC", "BER"]), fr24)
    assert not matches(criteria(destination_airports=["BER"]), fr24)


def test_criteria_from_filter() -> None:
    c = criteria(
        area_latitude=FRA[0],
        area_longitude=FRA[1],
        area_radius_nm=30,
        registrations=["D-AIMA", "N1*"],
        cooldown_minutes=15,
    )
    assert c.filter_id == 1
    assert c.area is not None
    assert c.area.radius_nm == 30
    assert c.registrations.exact == frozenset({"DAIMA"})
    assert c.registrations.wildcards == ("N1*",)
    assert c.cooldown_minutes == 15
    assert criteria().area is None
