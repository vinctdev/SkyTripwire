"""Notification channel CRUD and test messages. URLs are write-only and never returned."""

from fastapi import APIRouter, HTTPException, status
from sqlmodel import Session, col, select

from skytripwire.api.deps import NotifierDep, SessionDep
from skytripwire.api.schemas import (
    ChannelIn,
    ChannelOut,
    ChannelTest,
    ChannelTestResult,
    ChannelUpdate,
)
from skytripwire.db.models import Channel, utcnow
from skytripwire.notify.apprise_notifier import AppriseNotifier, mask_url
from skytripwire.notify.base import NotificationError

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("")
def list_channels(session: SessionDep) -> list[ChannelOut]:
    return [_to_out(c) for c in session.exec(select(Channel).order_by(col(Channel.id))).all()]


@router.get("/{channel_id}")
def get_channel(channel_id: int, session: SessionDep) -> ChannelOut:
    return _to_out(_get_or_404(session, channel_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_channel(data: ChannelIn, session: SessionDep) -> ChannelOut:
    channel = Channel(name=data.name, kind=data.kind, url=data.url, enabled=data.enabled)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _to_out(channel)


@router.put("/{channel_id}")
def update_channel(channel_id: int, data: ChannelUpdate, session: SessionDep) -> ChannelOut:
    channel = _get_or_404(session, channel_id)
    if data.url is None and data.kind != channel.kind:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "changing the kind needs a new URL"
        )
    channel.name = data.name
    channel.kind = data.kind
    channel.enabled = data.enabled
    if data.url is not None:
        channel.url = data.url
    channel.updated_at = utcnow()
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _to_out(channel)


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(channel_id: int, session: SessionDep) -> None:
    session.delete(_get_or_404(session, channel_id))
    session.commit()


@router.post("/test")
async def test_new_channel(data: ChannelTest, notifier: NotifierDep) -> ChannelTestResult:
    """Send a test message to a URL before saving it."""
    return await _send_test(notifier, data.url)


@router.post("/{channel_id}/test")
async def test_channel(
    channel_id: int, session: SessionDep, notifier: NotifierDep
) -> ChannelTestResult:
    channel = _get_or_404(session, channel_id)
    return await _send_test(notifier, channel.url)


async def _send_test(notifier: AppriseNotifier, url: str) -> ChannelTestResult:
    try:
        await notifier.send_test(url)
    except NotificationError as exc:
        return ChannelTestResult(ok=False, error=str(exc))
    return ChannelTestResult(ok=True)


def _get_or_404(session: Session, channel_id: int) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "channel not found")
    return channel


def _to_out(channel: Channel) -> ChannelOut:
    if channel.id is None:
        raise ValueError("only persisted channels can be returned")
    return ChannelOut(
        id=channel.id,
        name=channel.name,
        kind=channel.kind,
        url_masked=mask_url(channel.url),
        enabled=channel.enabled,
        filter_ids=sorted(f.id for f in channel.filters if f.id is not None),
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )
