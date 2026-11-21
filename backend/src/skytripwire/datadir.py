"""Data directory handling. The database holds channel URLs with credentials, so only the
owner may read it: directory 700, files 600."""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DIR_MODE = 0o700
FILE_MODE = 0o600


def secure_data_dir(path: Path) -> None:
    """Create the data directory if needed and restrict it and its files to the owner.

    Runs on every start, so existing installations created with looser modes are fixed too.
    Failures (e.g. a mounted directory owned by another user) are logged, not fatal.
    """
    path.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
    _restrict(path, DIR_MODE)
    for child in path.iterdir():
        if child.is_file() and not child.is_symlink():
            _restrict(child, FILE_MODE)


def restrict_umask() -> None:
    """Files created later by this process (SQLite journals, new databases) get mode 600."""
    os.umask(0o077)


def _restrict(path: Path, mode: int) -> None:
    if os.name != "posix":
        return
    try:
        if path.stat().st_mode & 0o777 != mode:
            path.chmod(mode)
    except OSError as exc:
        log.warning("Cannot restrict permissions of %s to %o: %s", path, mode, exc)
