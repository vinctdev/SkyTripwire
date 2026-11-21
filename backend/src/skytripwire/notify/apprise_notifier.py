"""Notifications via Apprise (Telegram, e-mail and everything else Apprise supports).

Channel URLs contain secrets (bot tokens, passwords). They are never logged, never
returned by the API (only masked) and are redacted from error messages.
"""

import re
from collections.abc import Iterable, Sequence

import apprise
from apprise import NotifyFormat

from skytripwire.notify.base import NotificationError
from skytripwire.notify.message import Message, alert_message, channel_test_message
from skytripwire.providers.base import Aircraft

_ERROR_LEVELS = frozenset({"WARNING", "ERROR", "CRITICAL"})
_URL_PARTS = re.compile(r"[/:@?&=#]+")
_MIN_SECRET_LENGTH = 6
_MAX_ERROR_LENGTH = 500
REDACTED = "****"


class AppriseNotifier:
    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout

    async def send(self, filter_name: str, aircraft: Aircraft, urls: Sequence[str]) -> None:
        await self._deliver(alert_message(filter_name, aircraft), urls)

    async def send_test(self, url: str) -> None:
        """Send a test notification to one channel. Raises NotificationError on failure."""
        await self._deliver(channel_test_message(), [url])

    async def _deliver(self, message: Message, urls: Sequence[str]) -> None:
        if not urls:
            raise NotificationError("no channel to send to")
        manager = apprise.Apprise()
        for url in urls:
            if not manager.add(url):
                raise NotificationError(f"invalid channel URL: {mask_url(url)}")
        with await manager.async_notify(
            body=message.body,
            title=message.title,
            body_format=NotifyFormat.TEXT,
            timeout=self._timeout,
        ) as result:
            if result:
                return
            details = [entry.message for entry in result.logs() if entry.level in _ERROR_LEVELS]
            summary = f"{result.failed_count} of {len(result)} channel(s) failed"
            text = "; ".join([summary, *dict.fromkeys(details)])
        raise NotificationError(redact(text, urls)[:_MAX_ERROR_LENGTH])


def is_valid_url(url: str) -> bool:
    return apprise.Apprise.instantiate(url) is not None


def mask_url(url: str) -> str:
    """Channel URL with secrets hidden, safe to show in the UI and logs."""
    plugin = apprise.Apprise.instantiate(url)
    if plugin is None:
        scheme = url.split("://", 1)[0] if "://" in url else ""
        return f"{scheme}://{REDACTED}" if scheme else REDACTED
    masked: str = plugin.url(privacy=True)  # type: ignore[no-untyped-call]
    return masked.split("?", 1)[0]


def redact(text: str, urls: Iterable[str]) -> str:
    """Replace anything that looks like a part of a channel URL (tokens, passwords, ...).

    Over-redacts on purpose: hostnames and long ids are hidden as well.
    """
    secrets: set[str] = set()
    for url in urls:
        rest = url.split("://", 1)[-1]
        secrets.update(p for p in _URL_PARTS.split(rest) if len(p) >= _MIN_SECRET_LENGTH)
        secrets.add(rest)
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return text
