from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from skytripwire.db import migrate
from skytripwire.db.engine import make_engine, session_scope
from skytripwire.db.models import AlertEvent, Filter
from skytripwire.engine.dedup import merge_sightings, recently_alerted
from skytripwire.providers.base import Aircraft

NOW = datetime(2026, 11, 18, 16, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate.upgrade(engine)
    yield engine
    engine.dispose()


def sighting(provider: str, seconds_ago: float, **fields: object) -> Aircraft:
    values: dict[str, object] = {"hex": "3c6444", "source_id": f"{provider}-id"} | fields
    return Aircraft(provider=provider, seen_at=NOW - timedelta(seconds=seconds_ago), **values)  # type: ignore[arg-type]


def test_merge_prefers_newest_and_fills_gaps() -> None:
    adsb = sighting("adsblol", 1, altitude_ft=12000, military=False, category="A3")
    fr24 = sighting("fr24", 10, altitude_ft=11500, origin_iata="FRA", destination_iata="MUC")
    [merged] = merge_sightings([fr24, adsb])
    assert merged.provider == "adsblol"
    assert merged.altitude_ft == 12000
    assert merged.military is False
    assert merged.origin_iata == "FRA"
    assert merged.destination_iata == "MUC"


def test_merge_keeps_distinct_aircraft_in_order() -> None:
    a = sighting("adsblol", 1, hex="aaaaaa")
    b = sighting("adsblol", 1, hex="bbbbbb")
    no_hex = sighting("fr24", 1, hex=None, source_id="3a1b2c3d")
    assert [x.identity for x in merge_sightings([a, b, no_hex, a])] == [
        "aaaaaa",
        "bbbbbb",
        "fr24:3a1b2c3d",
    ]


def add_alert(session: Session, filter_id: int, identity: str, minutes_ago: int) -> None:
    session.add(
        AlertEvent(
            filter_id=filter_id,
            filter_name="f",
            provider="adsblol",
            aircraft_identity=identity,
            seen_at=NOW,
            created_at=NOW - timedelta(minutes=minutes_ago),
        )
    )


def test_recently_alerted(engine: Engine) -> None:
    with session_scope(engine) as session:
        first, second = Filter(name="first"), Filter(name="second")
        session.add_all([first, second])
        session.flush()
        assert first.id is not None
        assert second.id is not None
        add_alert(session, first.id, "aaaaaa", minutes_ago=10)
        add_alert(session, first.id, "bbbbbb", minutes_ago=90)
        add_alert(session, second.id, "cccccc", minutes_ago=1)
        first_id = first.id

    with Session(engine) as session:
        identities = ["aaaaaa", "bbbbbb", "cccccc", "dddddd"]
        hour = timedelta(minutes=60)
        assert recently_alerted(session, first_id, identities, cooldown=hour, now=NOW) == {"aaaaaa"}
        assert recently_alerted(
            session, first_id, identities, cooldown=timedelta(hours=2), now=NOW
        ) == {"aaaaaa", "bbbbbb"}
        assert (
            recently_alerted(session, first_id, identities, cooldown=timedelta(0), now=NOW) == set()
        )
        assert recently_alerted(session, first_id, [], cooldown=hour, now=NOW) == set()
