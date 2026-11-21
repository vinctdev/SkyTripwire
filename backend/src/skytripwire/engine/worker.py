"""Polling worker: plan, fetch, match, record, notify. Repeats on an interval derived from
the request budget.

Database access is synchronous and runs in worker threads, provider requests are async.
Requests are sent one after another to be gentle with the data sources.
"""

import logging
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from skytripwire.db.engine import session_scope
from skytripwire.db.models import AlertEvent, Filter, ProviderState
from skytripwire.engine import budget
from skytripwire.engine.dedup import merge_sightings, recently_alerted
from skytripwire.engine.matcher import Criteria, matches
from skytripwire.engine.planner import Plan, PlannedRequest, build_plan
from skytripwire.notify.base import Notifier
from skytripwire.providers.base import Aircraft, Provider, ProviderError

log = logging.getLogger(__name__)

SECONDS_PER_DAY = 86_400
MAX_ERROR_LENGTH = 500


def utcnow() -> datetime:
    return datetime.now(UTC)


def compute_interval(plan: Plan, budgets: Mapping[str, int], min_interval: float) -> float:
    """Seconds between cycles so that no provider exceeds its daily budget."""
    per_cycle = Counter(request.provider for request in plan.requests)
    needed = [count * SECONDS_PER_DAY / budgets[name] for name, count in per_cycle.items()]
    return max([min_interval, *needed])


@dataclass(frozen=True, slots=True)
class _ActiveFilter:
    criteria: Criteria
    channel_urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PendingAlert:
    event_id: int
    filter_name: str
    aircraft: Aircraft
    urls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CycleResult:
    plan: Plan
    requests_sent: int
    aircraft_seen: int
    new_alerts: int
    # Provider name -> why it was skipped or failed in this cycle.
    provider_issues: Mapping[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class WorkerStatus:
    last_cycle_started_at: datetime | None = None
    last_cycle_finished_at: datetime | None = None
    next_cycle_at: datetime | None = None
    interval_seconds: float | None = None
    last_result: CycleResult | None = None
    last_error: str | None = None


class Worker:
    def __init__(
        self,
        engine: Engine,
        providers: Sequence[Provider],
        notifier: Notifier,
        *,
        budgets: Mapping[str, int],
        min_interval: float,
        max_alerts_per_filter: int,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        missing = {p.name for p in providers} - budgets.keys()
        if missing:
            raise ValueError(f"no budget configured for: {', '.join(sorted(missing))}")
        self._engine = engine
        self._providers = {p.name: p for p in providers}
        self._provider_order = list(providers)
        self._notifier = notifier
        self._budgets = dict(budgets)
        self._min_interval = min_interval
        self._max_alerts = max_alerts_per_filter
        self._clock = clock
        self._wake = anyio.Event()
        self.status = WorkerStatus()

    def wake(self) -> None:
        """Start the next cycle early, e.g. after filters changed. Call from the event loop.

        The minimum interval is still respected.
        """
        self._wake.set()

    async def run(self) -> None:
        """Run cycles forever. Errors are logged, the loop never dies on its own."""
        while True:
            started = self._clock()
            self.status.last_cycle_started_at = started
            try:
                result = await self.run_cycle()
            except Exception as exc:
                log.exception("Polling cycle failed")
                self.status.last_error = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
                plan = self.status.last_result.plan if self.status.last_result else Plan()
            else:
                self.status.last_result = result
                self.status.last_error = None
                plan = result.plan
            self.status.last_cycle_finished_at = self._clock()

            interval = compute_interval(plan, self._budgets, self._min_interval)
            self.status.interval_seconds = interval
            self.status.next_cycle_at = started + timedelta(seconds=interval)
            await self._sleep(started, interval)

    async def _sleep(self, started: datetime, interval: float) -> None:
        remaining = (started + timedelta(seconds=interval) - self._clock()).total_seconds()
        with anyio.move_on_after(max(remaining, 0)):
            await self._wake.wait()
        if self._wake.is_set():
            self._wake = anyio.Event()
            elapsed = (self._clock() - started).total_seconds()
            await anyio.sleep(max(self._min_interval - elapsed, 0))

    async def run_cycle(self) -> CycleResult:
        active = await anyio.to_thread.run_sync(self._load_filters)
        plan = build_plan([f.criteria for f in active], self._provider_order)
        for item in plan.unplannable:
            log.warning("Filter %s cannot be served: %s", item.filter_id, item.reason)

        sightings, sent, issues = await self._execute(plan)
        aircraft = merge_sightings(sightings)
        pending = await anyio.to_thread.run_sync(self._record_matches, active, aircraft)
        await self._notify(pending)

        new_alerts = len(pending)
        log.info(
            "Cycle done: %d requests, %d aircraft, %d new alerts", sent, len(aircraft), new_alerts
        )
        return CycleResult(plan, sent, len(aircraft), new_alerts, issues)

    # --- fetching ---------------------------------------------------------

    async def _execute(self, plan: Plan) -> tuple[list[Aircraft], int, dict[str, str]]:
        sightings: list[Aircraft] = []
        issues: dict[str, str] = {}
        sent = 0
        for request in plan.requests:
            if request.provider in issues:
                continue
            reason = await anyio.to_thread.run_sync(self._reserve, request.provider)
            if reason is not None:
                log.info("Skipping %s: %s", request.provider, reason)
                issues[request.provider] = reason
                continue
            sent += 1
            error = await self._fetch(request, sightings)
            await anyio.to_thread.run_sync(self._record_outcome, request.provider, error)
            if error is not None:
                issues[request.provider] = f"{type(error).__name__}: {error}"
        return sightings, sent, issues

    async def _fetch(self, request: PlannedRequest, sink: list[Aircraft]) -> ProviderError | None:
        try:
            sink.extend(await self._providers[request.provider].fetch(request.query))
        except ProviderError as exc:
            log.warning("%s request %r failed: %s", request.provider, request.query, exc)
            return exc
        return None

    def _reserve(self, provider: str) -> str | None:
        """Check budget and pause; count the request if it may be sent."""
        now = self._clock()
        with session_scope(self._engine) as session:
            state = _provider_state(session, provider)
            reason = budget.skip_reason(state, self._budgets[provider], now)
            if reason is None:
                budget.record_request(state, now)
            session.add(state)
            return reason

    def _record_outcome(self, provider: str, error: ProviderError | None) -> None:
        now = self._clock()
        with session_scope(self._engine) as session:
            state = _provider_state(session, provider)
            if error is None:
                budget.record_success(state, now)
            else:
                budget.record_failure(state, error, now)
            session.add(state)

    # --- matching ---------------------------------------------------------

    def _load_filters(self) -> list[_ActiveFilter]:
        with Session(self._engine) as session:
            filters = session.exec(select(Filter).where(col(Filter.enabled).is_(True))).all()
            return [
                _ActiveFilter(
                    Criteria.from_filter(f),
                    tuple(c.url for c in f.channels if c.enabled),
                )
                for f in filters
            ]

    def _record_matches(
        self, active: list[_ActiveFilter], aircraft: list[Aircraft]
    ) -> list[_PendingAlert]:
        now = self._clock()
        created: list[tuple[AlertEvent, _ActiveFilter, Aircraft]] = []
        with session_scope(self._engine) as session:
            for item in active:
                c = item.criteria
                matched = [a for a in aircraft if matches(c, a)]
                if not matched or c.filter_id is None:
                    continue
                recent = recently_alerted(
                    session,
                    c.filter_id,
                    (a.identity for a in matched),
                    cooldown=timedelta(minutes=c.cooldown_minutes),
                    now=now,
                )
                new = [a for a in matched if a.identity not in recent]
                if len(new) > self._max_alerts:
                    log.warning(
                        "Filter %s matched %d new aircraft, alerting only %d this cycle",
                        c.filter_id,
                        len(new),
                        self._max_alerts,
                    )
                for a in new[: self._max_alerts]:
                    event = _alert_event(c, a, now, has_channels=bool(item.channel_urls))
                    session.add(event)
                    created.append((event, item, a))
            session.flush()
            return [
                _PendingAlert(event.id, item.criteria.name, a, item.channel_urls)
                for event, item, a in created
                if event.id is not None and item.channel_urls
            ]

    # --- notifying --------------------------------------------------------

    async def _notify(self, pending: list[_PendingAlert]) -> None:
        outcomes: dict[int, str | None] = {}
        for alert in pending:
            try:
                await self._notifier.send(alert.filter_name, alert.aircraft, alert.urls)
            except Exception as exc:
                log.warning("Notification for alert %d failed: %s", alert.event_id, exc)
                outcomes[alert.event_id] = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
            else:
                outcomes[alert.event_id] = None
        if outcomes:
            await anyio.to_thread.run_sync(self._store_outcomes, outcomes)

    def _store_outcomes(self, outcomes: Mapping[int, str | None]) -> None:
        with session_scope(self._engine) as session:
            for event_id, error in outcomes.items():
                event = session.get_one(AlertEvent, event_id)
                event.notification_status = "sent" if error is None else "failed"
                event.notification_error = error
                session.add(event)


def _provider_state(session: Session, provider: str) -> ProviderState:
    return session.get(ProviderState, provider) or ProviderState(provider=provider)


def _alert_event(c: Criteria, a: Aircraft, now: datetime, *, has_channels: bool) -> AlertEvent:
    return AlertEvent(
        filter_id=c.filter_id,
        filter_name=c.name,
        provider=a.provider,
        aircraft_identity=a.identity,
        hex=a.hex,
        callsign=a.callsign,
        registration=a.registration,
        type_code=a.type_code,
        latitude=a.latitude,
        longitude=a.longitude,
        altitude_ft=a.altitude_ft,
        ground_speed_kts=a.ground_speed_kts,
        squawk=a.squawk,
        origin_iata=a.origin_iata,
        destination_iata=a.destination_iata,
        seen_at=a.seen_at,
        notification_status="pending" if has_channels else "skipped",
        created_at=now,
    )
