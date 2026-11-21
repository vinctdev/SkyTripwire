from datetime import UTC, datetime, timedelta

import pytest

from skytripwire.db.models import ProviderState
from skytripwire.engine import budget
from skytripwire.providers.base import (
    ProviderBlockedError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitedError,
)

NOW = datetime(2026, 11, 18, 16, tzinfo=UTC)


def test_window_and_budget() -> None:
    state = ProviderState(provider="adsblol")
    assert budget.skip_reason(state, 2, NOW) is None
    budget.record_request(state, NOW)
    budget.record_request(state, NOW + timedelta(hours=1))
    assert budget.skip_reason(state, 2, NOW + timedelta(hours=23)) == "daily request budget used up"
    assert budget.skip_reason(state, 2, NOW + timedelta(hours=24)) is None
    assert state.requests_in_window == 0
    assert state.window_started_at == NOW + timedelta(hours=24)


def test_pause_after_failure_and_reset_on_success() -> None:
    state = ProviderState(provider="adsblol")
    budget.record_failure(state, ProviderUnavailableError("timeout"), NOW)
    assert state.consecutive_failures == 1
    assert state.last_error == "ProviderUnavailableError: timeout"
    assert state.blocked_until == NOW + timedelta(minutes=1)
    assert budget.skip_reason(state, 100, NOW + timedelta(seconds=30)) is not None
    assert budget.skip_reason(state, 100, NOW + timedelta(minutes=1)) is None

    budget.record_success(state, NOW + timedelta(minutes=2))
    assert state.consecutive_failures == 0
    assert state.blocked_until is None
    assert state.last_success_at == NOW + timedelta(minutes=2)


@pytest.mark.parametrize(
    ("error", "failures", "expected"),
    [
        (RateLimitedError("quota", retry_after=3600), 1, timedelta(hours=1)),
        (RateLimitedError("quota"), 5, timedelta(minutes=15)),
        (ProviderUnavailableError("x"), 1, timedelta(minutes=1)),
        (ProviderUnavailableError("x"), 3, timedelta(minutes=4)),
        (ProviderError("x"), 10, timedelta(hours=1)),
        (ProviderBlockedError("x"), 1, timedelta(hours=1)),
        (ProviderBlockedError("x"), 2, timedelta(hours=2)),
        (ProviderBlockedError("x"), 50, timedelta(hours=24)),
    ],
)
def test_backoff(error: ProviderError, failures: int, expected: timedelta) -> None:
    assert budget.backoff(error, failures) == expected
