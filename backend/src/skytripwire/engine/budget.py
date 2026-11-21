"""Request budget and backoff per provider, applied to a :class:`ProviderState` row."""

from datetime import datetime, timedelta

from skytripwire.db.models import ProviderState
from skytripwire.providers.base import ProviderBlockedError, ProviderError, RateLimitedError

# adsb.lol counts unkeyed traffic in a fixed 24 h bucket, we use the same window everywhere.
WINDOW = timedelta(hours=24)

RATE_LIMIT_DEFAULT_PAUSE = timedelta(minutes=15)
ERROR_BASE_PAUSE = timedelta(minutes=1)
ERROR_MAX_PAUSE = timedelta(hours=1)
BLOCKED_BASE_PAUSE = timedelta(hours=1)
BLOCKED_MAX_PAUSE = timedelta(hours=24)
MAX_ERROR_LENGTH = 500


def roll_window(state: ProviderState, now: datetime) -> None:
    if state.window_started_at is None or now - state.window_started_at >= WINDOW:
        state.window_started_at = now
        state.requests_in_window = 0


def skip_reason(state: ProviderState, budget: int, now: datetime) -> str | None:
    """Why no request may be sent right now, or None if it may."""
    roll_window(state, now)
    if state.blocked_until is not None and state.blocked_until > now:
        return f"paused until {state.blocked_until.isoformat(timespec='seconds')}"
    if state.requests_in_window >= budget:
        return "daily request budget used up"
    return None


def record_request(state: ProviderState, now: datetime) -> None:
    roll_window(state, now)
    state.requests_in_window += 1


def record_success(state: ProviderState, now: datetime) -> None:
    state.consecutive_failures = 0
    state.blocked_until = None
    state.last_success_at = now


def record_failure(state: ProviderState, error: ProviderError, now: datetime) -> None:
    state.consecutive_failures += 1
    state.last_error_at = now
    state.last_error = f"{type(error).__name__}: {error}"[:MAX_ERROR_LENGTH]
    state.blocked_until = now + backoff(error, state.consecutive_failures)


def backoff(error: ProviderError, failures: int) -> timedelta:
    """Pause after a failure. Exponential in the number of consecutive failures."""
    if isinstance(error, RateLimitedError):
        if error.retry_after is not None:
            return timedelta(seconds=error.retry_after)
        return RATE_LIMIT_DEFAULT_PAUSE
    factor = 1 << min(max(failures - 1, 0), 16)
    if isinstance(error, ProviderBlockedError):
        return min(BLOCKED_BASE_PAUSE * factor, BLOCKED_MAX_PAUSE)
    return min(ERROR_BASE_PAUSE * factor, ERROR_MAX_PAUSE)
