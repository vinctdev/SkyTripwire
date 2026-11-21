"""Filter CRUD. Filters the request planner cannot serve are rejected with the reason."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

import anyio.from_thread
from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, col, select

from skytripwire.api.deps import ProvidersDep, SessionDep, WorkerDep
from skytripwire.api.schemas import Area, FilterIn, FilterOut
from skytripwire.db.models import Channel, Filter, utcnow
from skytripwire.engine.matcher import Criteria
from skytripwire.engine.planner import build_plan
from skytripwire.engine.worker import Worker
from skytripwire.providers.base import Provider

router = APIRouter(prefix="/filters", tags=["filters"])

_UNSAVED_ID = 0


@dataclass(frozen=True, slots=True)
class PlanInfo:
    served_by: dict[int, list[str]]
    reasons: dict[int, str]


def plan_info(filters: Sequence[Filter], providers: Sequence[Provider]) -> PlanInfo:
    plan = build_plan([Criteria.from_filter(f) for f in filters if f.id is not None], providers)
    served: dict[int, set[str]] = defaultdict(set)
    for request in plan.requests:
        for filter_id in request.filter_ids:
            served[filter_id].add(request.provider)
    return PlanInfo(
        served_by={k: sorted(v) for k, v in served.items()},
        reasons={u.filter_id: u.reason for u in plan.unplannable},
    )


@router.get("")
def list_filters(session: SessionDep, providers: ProvidersDep) -> list[FilterOut]:
    filters = session.exec(select(Filter).order_by(col(Filter.id))).all()
    info = plan_info(filters, providers)
    return [_to_out(f, info) for f in filters]


@router.get("/{filter_id}")
def get_filter(filter_id: int, session: SessionDep, providers: ProvidersDep) -> FilterOut:
    f = _get_or_404(session, filter_id)
    return _to_out(f, plan_info([f], providers))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_filter(
    data: FilterIn, session: SessionDep, providers: ProvidersDep, worker: WorkerDep
) -> FilterOut:
    f = Filter(name=data.name)
    _apply(session, f, data, providers)
    session.add(f)
    session.commit()
    session.refresh(f)
    _wake(worker)
    return _to_out(f, plan_info([f], providers))


@router.put("/{filter_id}")
def update_filter(
    filter_id: int,
    data: FilterIn,
    session: SessionDep,
    providers: ProvidersDep,
    worker: WorkerDep,
) -> FilterOut:
    f = _get_or_404(session, filter_id)
    _apply(session, f, data, providers)
    f.updated_at = utcnow()
    session.add(f)
    session.commit()
    session.refresh(f)
    _wake(worker)
    return _to_out(f, plan_info([f], providers))


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter(filter_id: int, session: SessionDep, worker: WorkerDep) -> None:
    session.delete(_get_or_404(session, filter_id))
    session.commit()
    _wake(worker)


def _get_or_404(session: Session, filter_id: int) -> Filter:
    f = session.get(Filter, filter_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "filter not found")
    return f


def _apply(session: Session, f: Filter, data: FilterIn, providers: Sequence[Provider]) -> None:
    for key, value in data.model_dump(exclude={"area", "channel_ids"}).items():
        setattr(f, key, value)
    f.area_latitude = data.area.latitude if data.area else None
    f.area_longitude = data.area.longitude if data.area else None
    f.area_radius_nm = data.area.radius_nm if data.area else None

    channels = list(session.exec(select(Channel).where(col(Channel.id).in_(data.channel_ids))))
    missing = set(data.channel_ids) - {c.id for c in channels}
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown channel id(s): {', '.join(map(str, sorted(missing)))}",
        )
    f.channels = channels

    criteria = Criteria.from_filter(f)
    if criteria.filter_id is None:
        criteria = replace(criteria, filter_id=_UNSAVED_ID)
    plan = build_plan([criteria], providers)
    if plan.unplannable:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, plan.unplannable[0].reason)


def _to_out(f: Filter, info: PlanInfo) -> FilterOut:
    if f.id is None:
        raise ValueError("only persisted filters can be returned")
    area = None
    if f.area_latitude is not None and f.area_longitude is not None and f.area_radius_nm:
        area = Area(
            latitude=f.area_latitude, longitude=f.area_longitude, radius_nm=f.area_radius_nm
        )
    return FilterOut(
        **f.model_dump(exclude={"area_latitude", "area_longitude", "area_radius_nm"}),
        area=area,
        channel_ids=sorted(c.id for c in f.channels if c.id is not None),
        served_by=info.served_by.get(f.id, []),
        unplannable_reason=info.reasons.get(f.id),
    )


def _wake(worker: Worker) -> None:
    # Endpoints run in a worker thread; the worker's event must be set on the event loop.
    anyio.from_thread.run_sync(worker.wake)
