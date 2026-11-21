"""Health, status (worker, request budget, unplannable filters) and UI configuration."""

from collections import Counter
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import col, select

from skytripwire import __version__
from skytripwire.api.deps import ProvidersDep, SessionDep, SettingsDep, WorkerDep
from skytripwire.api.schemas import (
    EMITTER_CATEGORIES,
    CategoryOut,
    ConfigOut,
    ProviderStatus,
    StatusOut,
    UnplannableFilter,
    WorkerStatusOut,
)
from skytripwire.db.models import Filter, ProviderState
from skytripwire.engine import budget
from skytripwire.engine.matcher import Criteria
from skytripwire.engine.planner import build_plan
from skytripwire.engine.worker import utcnow

router = APIRouter(tags=["status"])


class Health(BaseModel):
    status: Literal["ok"]
    version: str


@router.get("/health")
def health() -> Health:
    return Health(status="ok", version=__version__)


@router.get("/status")
def get_status(
    session: SessionDep, settings: SettingsDep, providers: ProvidersDep, worker: WorkerDep
) -> StatusOut:
    filters = session.exec(select(Filter).where(col(Filter.enabled).is_(True))).all()
    names = {f.id: f.name for f in filters}
    plan = build_plan([Criteria.from_filter(f) for f in filters], providers)
    per_cycle = Counter(r.provider for r in plan.requests)
    budgets = settings.daily_budgets()
    now = utcnow()

    provider_status = []
    for provider in providers:
        state = session.get(ProviderState, provider.name) or ProviderState(provider=provider.name)
        budget.roll_window(state, now)  # display only, not persisted
        provider_status.append(
            ProviderStatus(
                name=provider.name,
                provides=sorted(provider.provides),
                daily_budget=budgets[provider.name],
                requests_in_window=state.requests_in_window,
                window_started_at=state.window_started_at,
                planned_requests_per_cycle=per_cycle[provider.name],
                blocked_until=state.blocked_until
                if state.blocked_until and state.blocked_until > now
                else None,
                last_success_at=state.last_success_at,
                last_error_at=state.last_error_at,
                last_error=state.last_error,
            )
        )
    session.rollback()  # discard the window roll

    w = worker.status
    result = w.last_result
    return StatusOut(
        worker=WorkerStatusOut(
            enabled=settings.worker_enabled,
            last_cycle_started_at=w.last_cycle_started_at,
            last_cycle_finished_at=w.last_cycle_finished_at,
            next_cycle_at=w.next_cycle_at,
            interval_seconds=w.interval_seconds,
            last_error=w.last_error,
            last_requests_sent=result.requests_sent if result else None,
            last_aircraft_seen=result.aircraft_seen if result else None,
            last_new_alerts=result.new_alerts if result else None,
            provider_issues=dict(result.provider_issues) if result else {},
        ),
        providers=provider_status,
        unplannable=[
            UnplannableFilter(
                filter_id=u.filter_id, filter_name=names[u.filter_id], reason=u.reason
            )
            for u in plan.unplannable
        ],
    )


@router.get("/config")
def get_config(settings: SettingsDep, providers: ProvidersDep) -> ConfigOut:
    """Static information the UI needs to build its forms."""
    return ConfigOut(
        version=__version__,
        fr24_enabled=settings.fr24_enabled,
        providers=[p.name for p in providers],
        min_poll_interval_seconds=settings.poll_min_interval_seconds,
        categories=[CategoryOut(code=k, label=v) for k, v in EMITTER_CATEGORIES.items()],
    )
