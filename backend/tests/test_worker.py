from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import anyio
import pytest
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from skytripwire.db import migrate
from skytripwire.db.engine import make_engine, session_scope
from skytripwire.db.models import AlertEvent, Channel, Filter, ProviderState
from skytripwire.engine.planner import Plan, PlannedRequest
from skytripwire.engine.worker import Worker, compute_interval
from skytripwire.notify.base import NotificationError
from skytripwire.providers.base import (
    Aircraft,
    AreaQuery,
    DataField,
    GlobalField,
    GlobalQuery,
    Query,
    RateLimitedError,
)

pytestmark = pytest.mark.anyio

START = datetime(2026, 11, 18, 16, tzinfo=UTC)
FRA = (50.0379, 8.5622)

A319 = Aircraft(
    provider="adsblol",
    source_id="3c6444",
    hex="3c6444",
    latitude=50.1032,
    longitude=8.7741,
    altitude_ft=12025,
    callsign="DLH4AB",
    registration="D-AIBD",
    type_code="A319",
    military=False,
    seen_at=START,
)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)


class FakeProvider:
    def __init__(self, name: str = "adsblol", aircraft: Sequence[Aircraft] = (A319,)) -> None:
        self._name = name
        self.aircraft = list(aircraft)
        self.errors: list[Exception] = []
        self.calls: list[Query] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def provides(self) -> frozenset[DataField]:
        return frozenset(DataField)

    def supports(self, query: Query) -> bool:
        return True

    async def fetch(self, query: Query) -> list[Aircraft]:
        self.calls.append(query)
        if self.errors:
            raise self.errors.pop(0)
        return list(self.aircraft)

    async def aclose(self) -> None:
        pass


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, tuple[str, ...]]] = []
        self.fail = False

    async def send(self, filter_name: str, aircraft: Aircraft, urls: Sequence[str]) -> None:
        if self.fail:
            raise NotificationError("telegram: 401 unauthorized")
        self.sent.append((filter_name, aircraft.identity, tuple(urls)))


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    migrate.upgrade(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


def make_worker(
    engine: Engine,
    provider: FakeProvider,
    notifier: FakeNotifier,
    clock: Clock,
    **kwargs: Any,
) -> Worker:
    options: dict[str, Any] = {
        "budgets": {"adsblol": 450},
        "min_interval": 60,
        "max_alerts_per_filter": 10,
    } | kwargs
    return Worker(engine, [provider], notifier, clock=clock, **options)


def add_filter(engine: Engine, *, channel: bool | None = True, **kwargs: Any) -> int:
    options: dict[str, Any] = {
        "name": "Near FRA",
        "area_latitude": FRA[0],
        "area_longitude": FRA[1],
        "area_radius_nm": 30,
    } | kwargs
    with session_scope(engine) as session:
        f = Filter(**options)
        if channel is not None:
            f.channels = [Channel(name="tg", kind="telegram", url="tgram://t/c", enabled=channel)]
        session.add(f)
        session.flush()
        assert f.id is not None
        return f.id


def alerts(engine: Engine) -> list[AlertEvent]:
    with Session(engine) as session:
        return list(session.exec(select(AlertEvent).order_by(col(AlertEvent.id))).all())


def provider_state(engine: Engine) -> ProviderState:
    with Session(engine) as session:
        return session.get_one(ProviderState, "adsblol")


async def test_cycle_records_and_notifies(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    filter_id = add_filter(engine)
    result = await make_worker(engine, provider, notifier, clock).run_cycle()

    assert provider.calls == [AreaQuery(*FRA, 30)]
    assert (result.requests_sent, result.aircraft_seen, result.new_alerts) == (1, 1, 1)
    assert notifier.sent == [("Near FRA", "3c6444", ("tgram://t/c",))]
    [event] = alerts(engine)
    assert event.filter_id == filter_id
    assert event.registration == "D-AIBD"
    assert event.notification_status == "sent"
    assert event.created_at == START
    state = provider_state(engine)
    assert state.requests_in_window == 1
    assert state.last_success_at == START


async def test_cooldown(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine, cooldown_minutes=60)
    worker = make_worker(engine, provider, notifier, clock)
    await worker.run_cycle()
    clock.advance(minutes=30)
    assert (await worker.run_cycle()).new_alerts == 0
    clock.advance(minutes=31)
    assert (await worker.run_cycle()).new_alerts == 1
    assert len(notifier.sent) == 2


@pytest.mark.parametrize("channel", [None, False])
async def test_without_enabled_channel_alert_is_skipped(
    engine: Engine,
    provider: FakeProvider,
    notifier: FakeNotifier,
    clock: Clock,
    channel: bool | None,
) -> None:
    add_filter(engine, channel=channel)
    await make_worker(engine, provider, notifier, clock).run_cycle()
    assert notifier.sent == []
    assert [e.notification_status for e in alerts(engine)] == ["skipped"]


async def test_failed_notification_is_recorded(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine)
    notifier.fail = True
    await make_worker(engine, provider, notifier, clock).run_cycle()
    [event] = alerts(engine)
    assert event.notification_status == "failed"
    assert event.notification_error == "NotificationError: telegram: 401 unauthorized"


async def test_disabled_filters_cause_no_requests(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine, enabled=False)
    result = await make_worker(engine, provider, notifier, clock).run_cycle()
    assert result.plan == Plan()
    assert provider.calls == []


async def test_filters_share_requests_and_match_independently(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine, name="A319", type_codes=["A319"])
    add_filter(engine, name="A388", type_codes=["A388"])
    result = await make_worker(engine, provider, notifier, clock).run_cycle()
    assert len(provider.calls) == 1
    assert result.new_alerts == 1
    assert [e.filter_name for e in alerts(engine)] == ["A319"]


async def test_max_alerts_per_filter(engine: Engine, notifier: FakeNotifier, clock: Clock) -> None:
    fleet = [replace(A319, hex=f"3c{i:04x}", source_id=str(i)) for i in range(5)]
    add_filter(engine)
    worker = make_worker(
        engine, FakeProvider(aircraft=fleet), notifier, clock, max_alerts_per_filter=3
    )
    assert (await worker.run_cycle()).new_alerts == 3
    clock.advance(minutes=1)
    assert (await worker.run_cycle()).new_alerts == 2


async def test_rate_limit_pauses_provider(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine)
    provider.errors.append(RateLimitedError("quota", retry_after=600))
    worker = make_worker(engine, provider, notifier, clock)

    result = await worker.run_cycle()
    assert result.new_alerts == 0
    assert "RateLimitedError" in result.provider_issues["adsblol"]
    assert provider_state(engine).blocked_until == START + timedelta(minutes=10)

    clock.advance(minutes=5)
    result = await worker.run_cycle()
    assert len(provider.calls) == 1
    assert result.requests_sent == 0
    assert result.provider_issues["adsblol"].startswith("paused until")

    clock.advance(minutes=6)
    assert (await worker.run_cycle()).new_alerts == 1
    assert len(provider.calls) == 2


async def test_budget_is_never_exceeded(
    engine: Engine, provider: FakeProvider, notifier: FakeNotifier, clock: Clock
) -> None:
    add_filter(engine)
    worker = make_worker(engine, provider, notifier, clock, budgets={"adsblol": 2})
    for _ in range(4):
        await worker.run_cycle()
        clock.advance(minutes=1)
    assert len(provider.calls) == 2
    clock.advance(hours=24)
    await worker.run_cycle()
    assert len(provider.calls) == 3


def test_compute_interval() -> None:
    def plan(*providers: str) -> Plan:
        return Plan(
            tuple(
                PlannedRequest(p, GlobalQuery(GlobalField.MILITARY), frozenset({1}))
                for p in providers
            )
        )

    budgets = {"adsblol": 450, "fr24": 1440}
    assert compute_interval(Plan(), budgets, 60) == 60
    assert compute_interval(plan("adsblol"), budgets, 60) == 192
    assert compute_interval(plan("adsblol", "adsblol", "fr24"), budgets, 60) == 384
    assert compute_interval(plan("fr24"), budgets, 60) == 60


def test_missing_budget_is_rejected(engine: Engine, notifier: FakeNotifier) -> None:
    with pytest.raises(ValueError, match="fr24"):
        Worker(
            engine,
            [FakeProvider("fr24")],
            notifier,
            budgets={"adsblol": 450},
            min_interval=60,
            max_alerts_per_filter=10,
        )


async def test_run_loop_survives_errors_and_wakes_early(
    engine: Engine, notifier: FakeNotifier
) -> None:
    add_filter(engine)
    provider = FakeProvider()
    worker = Worker(
        engine,
        [provider],
        notifier,
        budgets={"adsblol": 1_000_000},
        min_interval=0.05,
        max_alerts_per_filter=10,
    )

    async def broken_cycle() -> Any:
        raise RuntimeError("boom")

    real_cycle = worker.run_cycle
    worker.run_cycle = broken_cycle  # type: ignore[method-assign]
    async with anyio.create_task_group() as tg:
        tg.start_soon(worker.run)
        with anyio.fail_after(5):
            while worker.status.last_error is None:  # noqa: ASYNC110
                await anyio.sleep(0.01)
            assert worker.status.last_error == "RuntimeError: boom"
            worker.run_cycle = real_cycle  # type: ignore[method-assign]
            while worker.status.last_result is None:  # noqa: ASYNC110
                await anyio.sleep(0.01)
        assert worker.status.last_error is None
        assert worker.status.interval_seconds is not None
        assert worker.status.next_cycle_at is not None
        tg.cancel_scope.cancel()
    assert len(notifier.sent) == 1
