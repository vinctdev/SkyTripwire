import pytest
from fastapi.testclient import TestClient

from skytripwire import __version__
from skytripwire.app import create_app
from skytripwire.config import Settings


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_lifespan_creates_data_dir(client: TestClient, settings: Settings) -> None:
    assert settings.data_dir.is_dir()


def test_defaults_bind_to_localhost() -> None:
    settings = Settings(_env_file=None)
    assert settings.host == "127.0.0.1"
    assert settings.fr24_enabled is False
    assert settings.adsblol_api_key is None


def test_app_starts_and_stops_worker(settings: Settings) -> None:
    # No filters, so the worker plans no requests and sends nothing.
    settings.worker_enabled = True
    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/api/health").status_code == 200
        assert test_client.app.state.worker.status.last_cycle_started_at is not None  # type: ignore[attr-defined]


def test_trusted_hosts_default_to_localhost() -> None:
    assert Settings(_env_file=None).trusted_hosts == ["127.0.0.1", "localhost"]


def test_allowed_hosts_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKYTRIPWIRE_ALLOWED_HOSTS", " skytripwire.example.org, localhost ")
    assert Settings(_env_file=None).trusted_hosts == [
        "127.0.0.1",
        "localhost",
        "skytripwire.example.org",
    ]


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "localhost"])
def test_local_host_headers_are_accepted(client: TestClient, host: str) -> None:
    assert client.get("/api/health", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["attacker.example", "attacker.example:8000", "127.0.0.1.nip.io"])
def test_other_host_headers_are_rejected(client: TestClient, host: str) -> None:
    # DNS rebinding: the browser sends the attacker's host name to 127.0.0.1.
    response = client.get("/api/filters", headers={"Host": host})
    assert response.status_code == 400


def test_host_check_can_be_turned_off(settings: Settings) -> None:
    settings.allowed_hosts = ["*"]
    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/api/health", headers={"Host": "any.example"})
        assert response.status_code == 200


@pytest.mark.parametrize("origin", ["https://attacker.example", "null", "http://127.0.0.1.nip.io"])
def test_cross_site_writes_are_rejected(client: TestClient, origin: str) -> None:
    # A POST without body is a "simple request": browsers send it without CORS preflight.
    response = client.post("/api/channels/1/test", headers={"Origin": origin})
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8000", None])
def test_same_site_and_non_browser_writes_pass(client: TestClient, origin: str | None) -> None:
    headers = {"Origin": origin} if origin else {}
    response = client.post("/api/channels/1/test", headers=headers)
    assert response.status_code == 404  # passed the check, the channel does not exist


def test_cross_site_reads_are_not_checked(client: TestClient) -> None:
    # The browser does not let the other site read the response (no CORS headers).
    response = client.get("/api/health", headers={"Origin": "https://attacker.example"})
    assert response.status_code == 200


def test_wildcard_hosts_also_apply_to_the_origin_check(settings: Settings) -> None:
    settings.allowed_hosts = ["*.example.org"]
    with TestClient(create_app(settings), base_url="http://sky.example.org") as test_client:
        ok = test_client.post("/api/channels/1/test", headers={"Origin": "https://sky.example.org"})
        assert ok.status_code == 404  # passed both checks, the channel does not exist
        evil = test_client.post(
            "/api/channels/1/test", headers={"Origin": "https://example.org.evil"}
        )
        assert evil.status_code == 403


def test_loopback_stays_allowed_with_a_custom_domain(settings: Settings) -> None:
    # The container health check calls http://127.0.0.1:8000/api/health.
    settings.allowed_hosts = ["sky.example.org"]
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8000") as test_client:
        assert test_client.get("/api/health").status_code == 200


def test_empty_allowed_hosts_mean_loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKYTRIPWIRE_ALLOWED_HOSTS", " , ")
    assert Settings(_env_file=None).trusted_hosts == ["127.0.0.1", "localhost"]
