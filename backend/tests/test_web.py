from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skytripwire.app import create_app
from skytripwire.config import Settings
from skytripwire.web import find_frontend_dir

INDEX = '<!doctype html><div id="root"></div>'


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text(INDEX, encoding="utf-8")
    (directory / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (directory / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return directory


@pytest.fixture
def web_client(settings: Settings, dist: Path) -> Iterator[TestClient]:
    settings.frontend_dir = dist
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/filters", "/filters/7", "/channels/new"])
def test_client_routes_return_index(web_client: TestClient, path: str) -> None:
    response = web_client.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["cache-control"] == "no-cache"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert "https://tile.openstreetmap.org" in response.headers["content-security-policy"]
    assert response.headers["x-frame-options"] == "DENY"


def test_hashed_assets_are_cached(web_client: TestClient) -> None:
    response = web_client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert web_client.get("/assets/missing.js").status_code == 404


def test_other_files_in_the_build_are_served(web_client: TestClient) -> None:
    response = web_client.get("/favicon.svg")
    assert response.text == "<svg/>"
    assert "immutable" not in response.headers.get("cache-control", "")


def test_api_is_not_shadowed(web_client: TestClient) -> None:
    assert web_client.get("/api/health").json()["status"] == "ok"
    for path in ("/api", "/api/unknown", "/api/filters/x/y"):
        response = web_client.get(path)
        assert response.status_code == 404, path
        assert response.json() == {"detail": "Not Found"}
    assert web_client.get("/openapi.json").status_code == 200
    assert web_client.get("/docs").status_code == 200


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"]
)
def test_no_files_outside_the_build(web_client: TestClient, path: str) -> None:
    response = web_client.get(path)
    assert "outside" not in response.text


def test_without_a_build_only_the_api_is_served(settings: Settings, tmp_path: Path) -> None:
    settings.frontend_dir = tmp_path / "missing"
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_find_frontend_dir(tmp_path: Path, dist: Path) -> None:
    assert find_frontend_dir(dist) == dist.resolve()
    assert find_frontend_dir(tmp_path / "missing") is None
