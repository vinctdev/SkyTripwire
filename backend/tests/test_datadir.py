import os
import stat
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skytripwire.app import create_app
from skytripwire.config import Settings
from skytripwire.datadir import secure_data_dir

pytestmark = pytest.mark.skipif(os.name != "posix", reason="POSIX permissions only")


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_creates_private_directory(tmp_path: Path) -> None:
    data_dir = tmp_path / "nested" / "data"
    secure_data_dir(data_dir)
    assert _mode(data_dir) == 0o700


def test_tightens_existing_directory_and_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o755)
    data_dir.chmod(0o755)
    database = data_dir / "skytripwire.db"
    database.write_bytes(b"")
    database.chmod(0o644)
    secure_data_dir(data_dir)
    assert _mode(data_dir) == 0o700
    assert _mode(database) == 0o600


def test_leaves_subdirectories_and_symlink_targets_alone(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    sub = data_dir / "backups"
    sub.mkdir(mode=0o755)
    sub.chmod(0o755)
    target = tmp_path / "outside.txt"
    target.write_bytes(b"")
    target.chmod(0o644)
    (data_dir / "link").symlink_to(target)
    secure_data_dir(data_dir)
    assert _mode(sub) == 0o755
    assert _mode(target) == 0o644


def test_failure_is_logged_not_raised(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o755)
    data_dir.chmod(0o755)

    def deny(self: Path, mode: int) -> None:
        raise PermissionError("not the owner")

    monkeypatch.setattr(Path, "chmod", deny)
    secure_data_dir(data_dir)
    assert _mode(data_dir) == 0o755


def test_app_start_restricts_new_database(settings: Settings) -> None:
    with TestClient(create_app(settings)):
        pass
    assert _mode(settings.data_dir) == 0o700
    assert _mode(settings.data_dir / "skytripwire.db") == 0o600
