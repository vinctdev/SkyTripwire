"""Entry point: ``python -m skytripwire`` or ``skytripwire``."""

import logging

import uvicorn

from skytripwire.app import create_app
from skytripwire.config import get_settings
from skytripwire.datadir import restrict_umask

# Loggers of libraries that write URLs with channel secrets (bot tokens, ntfy topics, ...) at
# DEBUG. Capped at INFO, so even SKYTRIPWIRE_LOG_LEVEL=debug does not leak them.
_URL_LOGGING_LIBRARIES = ("urllib3", "requests_oauthlib", "oauthlib")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Alembic reports every migration step on INFO, which is noise on each start.
    logging.getLogger("alembic").setLevel(logging.WARNING)
    for name in _URL_LOGGING_LIBRARIES:
        library = logging.getLogger(name)
        if library.getEffectiveLevel() < logging.INFO:
            library.setLevel(logging.INFO)
    # Apprise puts channel URLs into some messages, even on INFO and WARNING. Keep them out of
    # the log output. Failures still reach it redacted, through NotificationError, and Apprise
    # still collects them for the API, with its own handler on this logger.
    logging.getLogger("apprise").propagate = False


def main() -> None:
    restrict_umask()
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    main()
