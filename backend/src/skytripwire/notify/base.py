"""Notifier interface used by the polling worker."""

from collections.abc import Sequence
from typing import Protocol

from skytripwire.providers.base import Aircraft


class NotificationError(Exception):
    """Sending to at least one channel failed."""


class Notifier(Protocol):
    async def send(self, filter_name: str, aircraft: Aircraft, urls: Sequence[str]) -> None:
        """Send one alert to all given channel URLs. Raises NotificationError on failure."""
        ...
