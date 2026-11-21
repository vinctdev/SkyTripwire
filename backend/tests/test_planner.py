from typing import Any

import pytest

from skytripwire.db.models import Filter
from skytripwire.engine.geo import distance_nm, enclosing_circle
from skytripwire.engine.matcher import Criteria
from skytripwire.engine.planner import Plan, PlannedRequest, build_plan
from skytripwire.providers.adsblol import AdsbLolProvider
from skytripwire.providers.base import AreaQuery, GlobalField, GlobalQuery, Provider
from skytripwire.providers.fr24 import Fr24Provider

FRA = (50.0379, 8.5622)
MUC = (48.3538, 11.7861)
FCO = (41.8003, 12.2389)
JFK = (40.6413, -73.7781)

ADSBLOL = AdsbLolProvider()
FR24 = Fr24Provider(client_factory=lambda: None)  # type: ignore[arg-type, return-value]
BOTH: list[Provider] = [ADSBLOL, FR24]
ONLY_ADSBLOL: list[Provider] = [ADSBLOL]

_ids = iter(range(1, 1_000_000))


def crit(**kwargs: Any) -> Criteria:
    return Criteria.from_filter(Filter(id=next(_ids), name="f", **kwargs))


def area(center: tuple[float, float], radius: float, **kwargs: Any) -> Criteria:
    return crit(area_latitude=center[0], area_longitude=center[1], area_radius_nm=radius, **kwargs)


def single(plan: Plan) -> PlannedRequest:
    assert not plan.unplannable
    assert len(plan.requests) == 1
    return plan.requests[0]


def test_empty() -> None:
    assert build_plan([], BOTH) == Plan()


def test_area_uses_adsblol_first() -> None:
    f = area(FRA, 30)
    request = single(build_plan([f], BOTH))
    assert request.provider == "adsblol"
    assert request.query == AreaQuery(*FRA, 30)
    assert request.filter_ids == {f.filter_id}


def test_identical_areas_are_shared() -> None:
    a, b = area(FRA, 30), area(FRA, 30, type_codes=["A388"])
    assert single(build_plan([a, b], BOTH)).filter_ids == {a.filter_id, b.filter_id}


def test_contained_area_is_merged_into_larger_one() -> None:
    big, small = area(FRA, 100), area((50.1, 8.7), 10)
    request = single(build_plan([small, big], ONLY_ADSBLOL))
    assert request.query == AreaQuery(*FRA, 100)


def test_nearby_areas_are_merged_into_enclosing_circle() -> None:
    fra, muc = area(FRA, 30), area(MUC, 30)
    request = single(build_plan([fra, muc], ONLY_ADSBLOL))
    assert isinstance(request.query, AreaQuery)
    q = request.query
    for center in (FRA, MUC):
        assert distance_nm(q.latitude, q.longitude, *center) + 30 <= q.radius_nm + 0.01
    assert q.radius_nm <= 250
    assert request.filter_ids == {fra.filter_id, muc.filter_id}


def test_distant_areas_are_not_merged() -> None:
    plan = build_plan([area(FRA, 30), area(JFK, 30)], ONLY_ADSBLOL)
    assert len(plan.requests) == 2


def test_greedy_merging_of_three_areas() -> None:
    # FRA + MUC fit into 250 nm, adding Rome would exceed it. (FRA + MUC + HAM would fit.)
    plan = build_plan([area(FRA, 20), area(MUC, 20), area(FCO, 20)], ONLY_ADSBLOL)
    assert len(plan.requests) == 2


def test_large_area_falls_back_to_fr24_or_is_unplannable() -> None:
    f = area(FRA, 400)
    assert single(build_plan([f], BOTH)).provider == "fr24"
    plan = build_plan([f], ONLY_ADSBLOL)
    assert plan.requests == ()
    assert plan.unplannable[0].filter_id == f.filter_id
    assert "too large" in plan.unplannable[0].reason


def test_route_filter_needs_fr24() -> None:
    f = area(FRA, 30, destination_airports=["JFK"])
    assert single(build_plan([f], BOTH)).provider == "fr24"
    plan = build_plan([f], ONLY_ADSBLOL)
    assert "route" in plan.unplannable[0].reason


def test_route_and_military_conflict() -> None:
    plan = build_plan([area(FRA, 30, origin_airports=["FRA"], military=True)], BOTH)
    assert plan.requests == ()
    assert "military, route" in plan.unplannable[0].reason


def test_areas_of_different_providers_are_not_merged() -> None:
    plan = build_plan([area(FRA, 30), area(FRA, 30, origin_airports=["FRA"])], BOTH)
    assert {r.provider for r in plan.requests} == {"adsblol", "fr24"}


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"registrations": ["D-AIMA"]}, [GlobalQuery(GlobalField.REGISTRATION, "D-AIMA")]),
        (
            {"callsigns": ["DLH400", "DLH401"], "type_codes": ["A388"]},
            [GlobalQuery(GlobalField.TYPE, "A388")],
        ),
        ({"military": True, "type_codes": ["C17", "A400"]}, [GlobalQuery(GlobalField.MILITARY)]),
        ({"squawks": ["7700"]}, [GlobalQuery(GlobalField.SQUAWK, "7700")]),
        (
            {"type_codes": ["A388", "B748"]},
            [GlobalQuery(GlobalField.TYPE, "A388"), GlobalQuery(GlobalField.TYPE, "B748")],
        ),
        # Wildcards cannot be enumerated: fall back to the exact type.
        (
            {"callsigns": ["DLH*"], "type_codes": ["A388"]},
            [GlobalQuery(GlobalField.TYPE, "A388")],
        ),
    ],
)
def test_worldwide_picks_cheapest_field(
    kwargs: dict[str, Any], expected: list[GlobalQuery]
) -> None:
    plan = build_plan([crit(**kwargs)], BOTH)
    assert not plan.unplannable
    assert [r.query for r in plan.requests] == expected
    assert {r.provider for r in plan.requests} == {"adsblol"}


def test_worldwide_airline_needs_fr24() -> None:
    f = crit(airlines=["DLH"])
    request = single(build_plan([f], BOTH))
    assert request.provider == "fr24"
    assert request.query == GlobalQuery(GlobalField.AIRLINE, "DLH")
    assert build_plan([f], ONLY_ADSBLOL).unplannable[0].filter_id == f.filter_id


def test_shared_global_queries() -> None:
    a, b = crit(type_codes=["A388"]), crit(type_codes=["A388"], altitude_min_ft=30000)
    assert single(build_plan([a, b], BOTH)).filter_ids == {a.filter_id, b.filter_id}


@pytest.mark.parametrize(
    "kwargs",
    [{}, {"callsigns": ["DLH*"]}, {"categories": ["A7"]}, {"altitude_min_ft": 40000}],
)
def test_worldwide_without_enumerable_field_is_unplannable(kwargs: dict[str, Any]) -> None:
    plan = build_plan([crit(**kwargs)], BOTH)
    assert plan.requests == ()
    assert "worldwide" in plan.unplannable[0].reason


def test_filter_without_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="no id"):
        build_plan([Criteria.from_filter(Filter(name="unsaved"))], BOTH)


def test_enclosing_circle_containment() -> None:
    big, small = (*FRA, 100.0), (50.1, 8.7, 10.0)
    assert enclosing_circle(big, small) == big
    assert enclosing_circle(small, big) == big
