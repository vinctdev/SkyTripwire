import logging
from collections.abc import Iterator

import pytest

from skytripwire.__main__ import configure_logging
from skytripwire.notify.apprise_notifier import AppriseNotifier
from skytripwire.notify.base import NotificationError

SECRET_URL = "skytest://failure/TopSecretToken123"


@pytest.fixture
def configured() -> Iterator[None]:
    """Apply configure_logging and undo its changes to the global loggers afterwards."""
    names = ["", "alembic", "apprise", "urllib3", "requests_oauthlib", "oauthlib"]
    saved = {
        name: (logging.getLogger(name).level, logging.getLogger(name).propagate) for name in names
    }
    # basicConfig does nothing when pytest has already set up the root logger.
    logging.getLogger().setLevel(logging.DEBUG)
    configure_logging("debug")
    yield
    for name, (level, propagate) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).propagate = propagate


@pytest.mark.usefixtures("configured")
def test_libraries_that_log_urls_stay_above_debug() -> None:
    for name in ("urllib3", "requests_oauthlib", "oauthlib"):
        assert logging.getLogger(name).getEffectiveLevel() == logging.INFO


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.mark.usefixtures("configured")
@pytest.mark.anyio
async def test_apprise_messages_stay_out_of_the_log() -> None:
    # Like the console handler basicConfig installs on the root logger. (caplog does not
    # work here: pytest attaches it to non-propagating loggers directly.)
    output = _Collect()
    logging.getLogger().addHandler(output)
    try:
        with pytest.raises(NotificationError) as info:
            await AppriseNotifier().send_test(SECRET_URL)
    finally:
        logging.getLogger().removeHandler(output)
    # Apprise still collects the warning for the error message, which is redacted.
    assert "skytest refused" in str(info.value)
    assert "TopSecretToken123" not in str(info.value)
    # Nothing from Apprise reaches the log output.
    assert not [r for r in output.records if r.name.startswith("apprise")]
