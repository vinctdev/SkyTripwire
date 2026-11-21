from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from skytripwire.db.engine import session_scope
from skytripwire.db.models import AlertEvent, Filter
from tests.conftest import SENT

SECRET = "ABCdefSecret"
TELEGRAM = f"tgram://123456:{SECRET}/987654"
FRA_AREA = {"latitude": 50.0379, "longitude": 8.5622, "radius_nm": 30}


@pytest.fixture
def wakes(client: TestClient) -> list[None]:
    calls: list[None] = []
    client.app.state.worker.wake = lambda: calls.append(None)  # type: ignore[attr-defined]
    return calls


def engine_of(client: TestClient) -> Engine:
    engine: Engine = client.app.state.engine  # type: ignore[attr-defined]
    return engine


def create_filter(client: TestClient, **data: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Near FRA", "area": FRA_AREA} | data
    response = client.post("/api/filters", json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def create_channel(client: TestClient, url: str = TELEGRAM, kind: str = "telegram") -> int:
    response = client.post("/api/channels", json={"name": "Phone", "kind": kind, "url": url})
    assert response.status_code == 201, response.text
    channel_id: int = response.json()["id"]
    return channel_id


# --- filters ----------------------------------------------------------------


def test_create_filter_normalizes_input(client: TestClient, wakes: list[None]) -> None:
    f = create_filter(
        client,
        type_codes=[" a388", "A388", "b74?", ""],
        registrations=["d-aima"],
        categories=["a7"],
        altitude_min_ft=1000,
    )
    assert f["type_codes"] == ["A388", "B74?"]
    assert f["registrations"] == ["D-AIMA"]
    assert f["categories"] == ["A7"]
    assert f["area"] == FRA_AREA
    assert f["served_by"] == ["adsblol"]
    assert f["unplannable_reason"] is None
    assert len(wakes) == 1


def test_filter_crud(client: TestClient, wakes: list[None]) -> None:
    channel_id = create_channel(client)
    f = create_filter(client, channel_ids=[channel_id])
    assert f["channel_ids"] == [channel_id]

    assert client.get(f"/api/filters/{f['id']}").json() == f
    assert [x["id"] for x in client.get("/api/filters").json()] == [f["id"]]

    updated = client.put(
        f"/api/filters/{f['id']}",
        json={"name": "Military", "military": True, "area": None, "enabled": False},
    ).json()
    assert updated["name"] == "Military"
    assert updated["area"] is None
    assert updated["channel_ids"] == []
    assert updated["served_by"] == ["adsblol"]
    assert updated["updated_at"] >= f["updated_at"]

    assert client.delete(f"/api/filters/{f['id']}").status_code == 204
    assert client.get(f"/api/filters/{f['id']}").status_code == 404
    assert client.put(f"/api/filters/{f['id']}", json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/filters/{f['id']}").status_code == 404
    assert len(wakes) == 3


@pytest.mark.parametrize(
    "data",
    [
        {"name": ""},
        {"squawks": ["7800"]},
        {"categories": ["Z9"]},
        {"airlines": ["LH"]},
        {"callsigns": ["DLH 4AB"]},
        {"altitude_min_ft": 5000, "altitude_max_ft": 1000},
        {"ground_speed_min_kts": 300, "ground_speed_max_kts": 100},
        {"area": {"latitude": 91, "longitude": 0, "radius_nm": 10}},
        {"area": {"latitude": 50, "longitude": 8, "radius_nm": 0}},
        {"cooldown_minutes": -1},
        {"type_codes": [f"T{i}" for i in range(51)]},
        {"unknown_field": True},
    ],
)
def test_filter_validation(client: TestClient, data: dict[str, Any]) -> None:
    body = {"name": "x", "area": FRA_AREA} | data
    response = client.post("/api/filters", json=body)
    assert response.status_code == 422
    for error in response.json()["detail"]:
        assert set(error) <= {"type", "loc", "msg"}


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        ({"area": None}, "worldwide"),
        ({"area": None, "callsigns": ["DLH*"]}, "worldwide"),
        ({"destination_airports": ["JFK"]}, "route"),
        ({"area": FRA_AREA | {"radius_nm": 400}}, "too large"),
    ],
)
def test_unplannable_filter_is_rejected(
    client: TestClient, data: dict[str, Any], reason: str
) -> None:
    response = client.post("/api/filters", json={"name": "x", "area": FRA_AREA} | data)
    assert response.status_code == 422
    assert reason in response.json()["detail"]


def test_unknown_channel_is_rejected(client: TestClient) -> None:
    response = client.post("/api/filters", json={"name": "x", "area": FRA_AREA, "channel_ids": [9]})
    assert response.status_code == 422
    assert "unknown channel" in response.json()["detail"]


# --- channels ---------------------------------------------------------------


def test_channel_url_is_never_returned(client: TestClient) -> None:
    channel_id = create_channel(client)
    for response in (
        client.get("/api/channels"),
        client.get(f"/api/channels/{channel_id}"),
        client.put(
            f"/api/channels/{channel_id}",
            json={"name": "Renamed", "kind": "telegram", "enabled": False},
        ),
    ):
        assert response.status_code == 200
        assert SECRET not in response.text
    channel = client.get(f"/api/channels/{channel_id}").json()
    assert "url" not in channel
    assert channel["url_masked"].startswith("tgram://")
    assert channel["name"] == "Renamed"
    assert channel["enabled"] is False


@pytest.mark.parametrize(
    ("kind", "url"),
    [
        ("email", TELEGRAM),
        ("telegram", f"mailtos://user:{SECRET}@example.org"),
        ("apprise", f"bogus://user:{SECRET}@host"),
    ],
)
def test_invalid_channel_url_is_not_echoed(client: TestClient, kind: str, url: str) -> None:
    response = client.post("/api/channels", json={"name": "x", "kind": kind, "url": url})
    assert response.status_code == 422
    assert SECRET not in response.text


def test_channel_update_keeps_or_replaces_url(client: TestClient) -> None:
    channel_id = create_channel(client, url="skytest://ok", kind="apprise")
    client.put(f"/api/channels/{channel_id}", json={"name": "x", "kind": "apprise"})
    assert client.post(f"/api/channels/{channel_id}/test").json() == {"ok": True, "error": None}
    assert SENT[-1]["host"] == "ok"

    client.put(
        f"/api/channels/{channel_id}",
        json={"name": "x", "kind": "apprise", "url": "skytest://failing"},
    )
    result = client.post(f"/api/channels/{channel_id}/test").json()
    assert result["ok"] is False
    assert "failed" in result["error"]

    response = client.put(f"/api/channels/{channel_id}", json={"name": "x", "kind": "telegram"})
    assert response.status_code == 422


def test_test_message_before_saving(client: TestClient) -> None:
    response = client.post("/api/channels/test", json={"kind": "apprise", "url": "skytest://ok"})
    assert response.json() == {"ok": True, "error": None}
    assert SENT[0]["title"] == "SkyTripwire: test notification"


def test_delete_channel(client: TestClient) -> None:
    channel_id = create_channel(client)
    f = create_filter(client, channel_ids=[channel_id])
    assert client.get(f"/api/channels/{channel_id}").json()["filter_ids"] == [f["id"]]
    assert client.delete(f"/api/channels/{channel_id}").status_code == 204
    assert client.get(f"/api/channels/{channel_id}").status_code == 404
    assert client.post(f"/api/channels/{channel_id}/test").status_code == 404
    assert client.get(f"/api/filters/{f['id']}").json()["channel_ids"] == []


# --- alerts -----------------------------------------------------------------


def add_alerts(client: TestClient, filter_id: int, count: int) -> None:
    with session_scope(engine_of(client)) as session:
        for i in range(count):
            session.add(
                AlertEvent(
                    filter_id=filter_id,
                    filter_name="f",
                    provider="adsblol",
                    aircraft_identity=f"3c{i:04x}",
                    seen_at=datetime(2026, 11, 18, tzinfo=UTC),
                )
            )


def test_alerts_paging_and_clear(client: TestClient) -> None:
    first, second = create_filter(client)["id"], create_filter(client)["id"]
    add_alerts(client, first, 3)
    add_alerts(client, second, 2)

    page = client.get("/api/alerts", params={"limit": 2}).json()
    assert [a["id"] for a in page] == [5, 4]
    page = client.get("/api/alerts", params={"limit": 2, "before_id": 4}).json()
    assert [a["id"] for a in page] == [3, 2]
    only_first = client.get("/api/alerts", params={"filter_id": first}).json()
    assert [a["id"] for a in only_first] == [3, 2, 1]
    assert only_first[0]["seen_at"].startswith("2026-11-18T00:00:00")

    assert client.get("/api/alerts", params={"limit": 0}).status_code == 422
    assert client.delete("/api/alerts").status_code == 204
    assert client.get("/api/alerts").json() == []


# --- status and config --------------------------------------------------------


def test_status(client: TestClient) -> None:
    create_filter(client)
    create_filter(client, area=FRA_AREA | {"radius_nm": 10})  # merged into the first
    # A filter that became unplannable, e.g. FR24 was disabled after it was saved.
    with session_scope(engine_of(client)) as session:
        session.add(
            Filter(
                name="Departures",
                origin_airports=["FRA"],
                area_latitude=50.0,
                area_longitude=8.5,
                area_radius_nm=20,
            )
        )

    status = client.get("/api/status").json()
    [adsblol] = status["providers"]
    assert adsblol["name"] == "adsblol"
    assert adsblol["daily_budget"] == 450
    assert adsblol["planned_requests_per_cycle"] == 1
    assert adsblol["requests_in_window"] == 0
    assert adsblol["blocked_until"] is None
    assert [u["filter_name"] for u in status["unplannable"]] == ["Departures"]
    assert status["worker"]["enabled"] is False
    assert status["worker"]["last_new_alerts"] is None


def test_config(client: TestClient) -> None:
    config = client.get("/api/config").json()
    assert config["fr24_enabled"] is False
    assert config["providers"] == ["adsblol"]
    assert {"code": "A7", "label": "Rotorcraft (helicopter)"} in config["categories"]
