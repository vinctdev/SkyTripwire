"""Alert history."""

from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlmodel import col, delete, select

from skytripwire.api.deps import SessionDep
from skytripwire.api.schemas import AlertOut
from skytripwire.db.models import AlertEvent

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
def list_alerts(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before_id: Annotated[
        int | None, Query(ge=1, description="Page: alerts older than this id")
    ] = None,
    filter_id: int | None = None,
) -> list[AlertOut]:
    """Newest first. For the next page pass the smallest id seen as ``before_id``."""
    statement = select(AlertEvent).order_by(col(AlertEvent.id).desc()).limit(limit)
    if before_id is not None:
        statement = statement.where(col(AlertEvent.id) < before_id)
    if filter_id is not None:
        statement = statement.where(AlertEvent.filter_id == filter_id)
    return [AlertOut.model_validate(event) for event in session.exec(statement).all()]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def clear_alerts(session: SessionDep) -> None:
    """Delete the whole history. Also resets the cooldown of all filters."""
    session.exec(delete(AlertEvent))
    session.commit()
