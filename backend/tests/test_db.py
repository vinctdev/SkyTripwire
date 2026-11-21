from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from sqlalchemy import Engine, inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import Session, select

from skytripwire.db import migrate
from skytripwire.db.engine import make_engine, session_scope
from skytripwire.db.models import AlertEvent, Channel, Filter, FilterChannelLink, ProviderState

TABLES = {"filters", "channels", "filter_channels", "alert_events", "provider_states"}


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate.upgrade(engine)
    yield engine
    engine.dispose()


def alert(filter_: Filter, identity: str = "3c6444") -> AlertEvent:
    return AlertEvent(
        filter_id=filter_.id,
        filter_name=filter_.name,
        provider="adsblol",
        aircraft_identity=identity,
        seen_at=datetime.now(UTC),
    )


def test_migrations_create_all_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) >= TABLES


def test_migrations_match_models(engine: Engine) -> None:
    # Fails if a model changed without a new migration.
    command.check(migrate.alembic_config(engine))


def test_upgrade_is_idempotent_and_downgrade_works(engine: Engine) -> None:
    migrate.upgrade(engine)
    command.downgrade(migrate.alembic_config(engine), "base")
    assert not TABLES & set(inspect(engine).get_table_names())
    migrate.upgrade(engine)
    assert set(inspect(engine).get_table_names()) >= TABLES


def test_pragmas(engine: Engine) -> None:
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"


def test_filter_roundtrip_with_channels(engine: Engine) -> None:
    with session_scope(engine) as session:
        channel = Channel(name="Telegram", kind="telegram", url="tgram://token/chat")
        session.add(
            Filter(
                name="A380 near FRA",
                area_latitude=50.0379,
                area_longitude=8.5622,
                area_radius_nm=30,
                type_codes=["A388"],
                categories=["A7", "B1"],
                channels=[channel],
            )
        )

    with Session(engine) as session:
        stored = session.exec(select(Filter)).one()
        assert stored.type_codes == ["A388"]
        assert stored.categories == ["A7", "B1"]
        assert stored.registrations == []
        assert stored.military is None
        assert stored.cooldown_minutes == 60
        assert [c.name for c in stored.channels] == ["Telegram"]
        assert stored.created_at.tzinfo is UTC


def test_datetimes_are_stored_as_utc(engine: Engine) -> None:
    cest = timezone(timedelta(hours=2))
    with session_scope(engine) as session:
        session.add(
            ProviderState(
                provider="adsblol", window_started_at=datetime(2026, 11, 18, 14, tzinfo=cest)
            )
        )

    with Session(engine) as session:
        state = session.get_one(ProviderState, "adsblol")
        assert state.window_started_at == datetime(2026, 11, 18, 12, tzinfo=UTC)
        assert state.window_started_at.tzinfo is UTC


def test_naive_datetimes_are_rejected(engine: Engine) -> None:
    with pytest.raises(StatementError, match="naive datetimes"), session_scope(engine) as session:
        session.add(ProviderState(provider="adsblol", window_started_at=datetime(2026, 11, 18)))


def test_incomplete_area_is_rejected(engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="area_complete"), session_scope(engine) as session:
        session.add(Filter(name="broken", area_latitude=50.0))


def test_deleting_channel_removes_link(engine: Engine) -> None:
    with session_scope(engine) as session:
        channel = Channel(name="Mail", kind="email", url="mailto://user:pass@example.org")
        session.add(Filter(name="Military", military=True, channels=[channel]))

    with session_scope(engine) as session:
        session.delete(session.exec(select(Channel)).one())

    with Session(engine) as session:
        assert session.exec(select(FilterChannelLink)).all() == []
        assert session.exec(select(Filter)).one().channels == []


def test_deleting_filter_keeps_alert_history(engine: Engine) -> None:
    with session_scope(engine) as session:
        filter_ = Filter(name="Helicopters", categories=["A7"])
        session.add(filter_)
        session.flush()
        session.add(alert(filter_))

    with session_scope(engine) as session:
        session.delete(session.exec(select(Filter)).one())

    with Session(engine) as session:
        event = session.exec(select(AlertEvent)).one()
        assert event.filter_id is None
        assert event.filter_name == "Helicopters"
