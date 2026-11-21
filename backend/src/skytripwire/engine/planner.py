"""Turn the enabled filters into as few provider requests as possible. Pure, no I/O.

Strategy:
- Providers are tried in the given order (adsb.lol first). A provider is only eligible for a
  filter if it delivers the data the filter needs (e.g. airports need FR24).
- Area filters become circle queries. Circles of the same provider are merged greedily when
  one contains the other, or when the enclosing circle stays within 250 nm.
- Worldwide filters use the global query field that needs the fewest requests (one request
  per listed value). Wildcards cannot be enumerated, so such fields are not usable.
- Filters that cannot be served are reported with a reason instead of failing the plan.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from skytripwire.engine.geo import enclosing_circle
from skytripwire.engine.matcher import Criteria, Patterns
from skytripwire.providers.base import (
    AreaQuery,
    DataField,
    GlobalField,
    GlobalQuery,
    Provider,
    Query,
)

MAX_MERGED_RADIUS_NM = 250.0


@dataclass(frozen=True, slots=True)
class PlannedRequest:
    provider: str
    query: Query
    filter_ids: frozenset[int]


@dataclass(frozen=True, slots=True)
class Unplannable:
    filter_id: int
    reason: str


@dataclass(frozen=True, slots=True)
class Plan:
    requests: tuple[PlannedRequest, ...] = ()
    unplannable: tuple[Unplannable, ...] = ()


@dataclass(slots=True)
class _Circle:
    query: AreaQuery
    filter_ids: set[int]


def required_fields(criteria: Criteria) -> frozenset[DataField]:
    """Data a provider must deliver for this filter to be able to match at all."""
    required: set[DataField] = set()
    if criteria.origin_airports or criteria.destination_airports:
        required.add(DataField.ROUTE)
    if criteria.military is True:
        required.add(DataField.MILITARY)
    if criteria.categories:
        required.add(DataField.CATEGORY)
    return frozenset(required)


def build_plan(criteria: Iterable[Criteria], providers: Sequence[Provider]) -> Plan:
    by_name = {p.name: p for p in providers}
    global_requests: dict[tuple[str, Query], set[int]] = {}
    circles: dict[str, list[_Circle]] = {}
    unplannable: list[Unplannable] = []

    for c in criteria:
        if c.filter_id is None:
            raise ValueError(f"filter {c.name!r} has no id")
        required = required_fields(c)
        eligible = [p for p in providers if required <= p.provides]
        if not eligible:
            names = ", ".join(sorted(required))
            unplannable.append(
                Unplannable(c.filter_id, f"No enabled data source delivers: {names}.")
            )
            continue

        if c.area is not None:
            query = AreaQuery(c.area.latitude, c.area.longitude, c.area.radius_nm)
            provider = next((p for p in eligible if p.supports(query)), None)
            if provider is None:
                unplannable.append(
                    Unplannable(c.filter_id, "Area radius is too large for the enabled sources.")
                )
                continue
            circles.setdefault(provider.name, []).append(_Circle(query, {c.filter_id}))
            continue

        choice = _cheapest_global(c, eligible)
        if choice is None:
            unplannable.append(
                Unplannable(
                    c.filter_id,
                    "A worldwide filter needs exact registrations, callsigns, types, squawks, "
                    "airlines (FR24 only) or 'only military'. Otherwise set an area.",
                )
            )
            continue
        for provider_name, global_query in choice:
            global_requests.setdefault((provider_name, global_query), set()).add(c.filter_id)

    requests = [
        PlannedRequest(name, query, frozenset(ids))
        for (name, query), ids in global_requests.items()
    ]
    for name, provider_circles in circles.items():
        requests.extend(
            PlannedRequest(name, circle.query, frozenset(circle.filter_ids))
            for circle in _merge_circles(provider_circles, by_name[name])
        )
    return Plan(tuple(requests), tuple(unplannable))


def _global_candidates(c: Criteria) -> list[tuple[GlobalField, tuple[str, ...]]]:
    """Usable (field, values) pairs, most selective field first."""
    candidates: list[tuple[GlobalField, tuple[str, ...]]] = []
    for field, patterns in (
        (GlobalField.REGISTRATION, c.registrations),
        (GlobalField.CALLSIGN, c.callsigns),
        (GlobalField.TYPE, c.type_codes),
    ):
        if _enumerable(patterns):
            candidates.append((field, patterns.originals))
    if c.squawks:
        candidates.append((GlobalField.SQUAWK, tuple(sorted(c.squawks))))
    if c.airlines:
        candidates.append((GlobalField.AIRLINE, tuple(sorted(c.airlines))))
    if c.military is True:
        candidates.append((GlobalField.MILITARY, ("",)))
    return candidates


def _enumerable(patterns: Patterns) -> bool:
    return bool(patterns.originals) and not patterns.wildcards


def _cheapest_global(
    c: Criteria, eligible: Sequence[Provider]
) -> list[tuple[str, GlobalQuery]] | None:
    best: list[tuple[str, GlobalQuery]] | None = None
    for field, values in _global_candidates(c):
        try:
            queries = [GlobalQuery(field, value) for value in values]
        except ValueError:
            continue  # e.g. an invalid squawk; the API validates input separately
        provider = next((p for p in eligible if all(p.supports(q) for q in queries)), None)
        if provider is not None and (best is None or len(queries) < len(best)):
            best = [(provider.name, q) for q in queries]
    return best


def _merge_circles(circles: list[_Circle], provider: Provider) -> list[_Circle]:
    """Greedily merge the pair with the smallest enclosing circle until nothing fits."""
    circles = list(circles)
    while True:
        best: tuple[int, int, AreaQuery] | None = None
        for i in range(len(circles)):
            for j in range(i + 1, len(circles)):
                merged = _try_merge(circles[i].query, circles[j].query, provider)
                if merged is not None and (best is None or merged.radius_nm < best[2].radius_nm):
                    best = (i, j, merged)
        if best is None:
            return circles
        i, j, merged = best
        combined = _Circle(merged, circles[i].filter_ids | circles[j].filter_ids)
        circles = [c for k, c in enumerate(circles) if k not in (i, j)]
        circles.insert(i, combined)


def _try_merge(a: AreaQuery, b: AreaQuery, provider: Provider) -> AreaQuery | None:
    circle_a = (a.latitude, a.longitude, a.radius_nm)
    circle_b = (b.latitude, b.longitude, b.radius_nm)
    lat, lon, radius = enclosing = enclosing_circle(circle_a, circle_b)
    contained = enclosing in (circle_a, circle_b)
    if not contained and radius > MAX_MERGED_RADIUS_NM:
        return None
    merged = AreaQuery(lat, lon, radius)
    return merged if provider.supports(merged) else None
