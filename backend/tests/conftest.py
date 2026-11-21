import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from apprise.decorators import notify
from fastapi.testclient import TestClient

from skytripwire.app import create_app
from skytripwire.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"

# Messages delivered to the fake Apprise service below.
SENT: list[dict[str, Any]] = []


# Fake Apprise service for tests: "skytest://ok" succeeds, "skytest://fail..." fails.
# Registered globally once, so no test ever talks to a real notification service.
@notify(on="skytest")  # type: ignore[no-untyped-call, untyped-decorator]
def _skytest(body: str, title: str, notify_type: str, meta: dict[str, Any], **_: Any) -> bool:
    host = str(meta.get("host", ""))
    SENT.append({"title": title, "body": body, "host": host})
    if host.startswith("fail"):
        # Like real Apprise plugins, which may put the URL with its secrets into the message.
        logging.getLogger("apprise").warning("skytest refused %s", meta.get("url"))
        return False
    return True


@pytest.fixture(autouse=True)
def _clear_sent() -> None:
    SENT.clear()


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        worker_enabled=False,
        # Host header of Starlette's TestClient.
        allowed_hosts=["testserver"],
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client
