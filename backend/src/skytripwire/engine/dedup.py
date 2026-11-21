"""Deduplication: merge sightings of one aircraft, and the per-filter alert cooldown."""

from collections.abc import Iterable
from dataclasses import fields, replace
from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from skytripwire.db.models import AlertEvent
from skytripwire.providers.base import Aircraft

_MERGEABLE = tuple(
    f.name for f in fields(Aircraft) if f.name not in {"provider", "source_id", "seen_at"}
)


def merge_sightings(sightings: Iterable[Aircraft]) -> list[Aircraft]:
    """Collapse sightings with the same identity into one record.

    The most recent sighting wins; fields it does not know are filled from the others.
    Typical case: adsb.lol knows "military", FR24 knows origin and destination.
    Order of first appearance is kept.
    """
    merged: dict[str, Aircraft] = {}
    for aircraft in sightings:
        current = merged.get(aircraft.identity)
        merged[aircraft.identity] = aircraft if current is None else _merge(current, aircraft)
    return list(merged.values())


def _merge(a: Aircraft, b: Aircraft) -> Aircraft:
    newer, older = (b, a) if b.seen_at > a.seen_at else (a, b)
    missing = {
        name: getattr(older, name)
        for name in _MERGEABLE
        if getattr(newer, name) is None and getattr(older, name) is not None
    }
    return replace(newer, **missing) if missing else newer


def recently_alerted(
    session: Session,
    filter_id: int,
    identities: Iterable[str],
    *,
    cooldown: timedelta,
    now: datetime,
) -> set[str]:
    """Identities that already triggered this filter within the cooldown. One query."""
    wanted = set(identities)
    if not wanted or cooldown <= timedelta(0):
        return set()
    statement = select(AlertEvent.aircraft_identity).where(
        AlertEvent.filter_id == filter_id,
        col(AlertEvent.aircraft_identity).in_(wanted),
        AlertEvent.created_at > now - cooldown,
    )
    return set(session.exec(statement).all())
