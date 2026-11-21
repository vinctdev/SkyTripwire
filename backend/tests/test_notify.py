from datetime import UTC, datetime

import pytest

from skytripwire.notify.apprise_notifier import AppriseNotifier, is_valid_url, mask_url, redact
from skytripwire.notify.base import NotificationError
from skytripwire.notify.message import alert_message
from skytripwire.providers.base import Aircraft
from tests.conftest import SENT

pytestmark = pytest.mark.anyio


A319 = Aircraft(
    provider="adsblol",
    source_id="3c6444",
    hex="3c6444",
    latitude=50.1032,
    longitude=8.7741,
    altitude_ft=12025,
    ground_speed_kts=310.4,
    callsign="DLH4AB",
    registration="D-AIBD",
    type_code="A319",
    airline_icao="DLH",
    squawk="7700",
    emergency="general",
    military=False,
    seen_at=datetime(2026, 11, 18, 16, 0, 5, tzinfo=UTC),
)


def test_alert_message() -> None:
    message = alert_message("Near FRA", A319)
    assert message.title == "SkyTripwire: DLH4AB / D-AIBD / A319"
    assert message.body.splitlines() == [
        "Filter: Near FRA",
        "Callsign: DLH4AB",
        "Registration: D-AIBD",
        "Type: A319",
        "Airline: DLH",
        "Altitude: 12,025 ft",
        "Ground speed: 310 kts",
        "Squawk: 7700 (emergency)",
        "Emergency: general",
        "Position: 50.1032, 8.7741",
        "Track: https://globe.adsb.lol/?icao=3c6444",
        "Seen: 2026-11-18 16:00:05 UTC",
        "Source: adsb.lol",
    ]


def test_alert_message_minimal_fr24() -> None:
    aircraft = Aircraft(
        provider="fr24",
        source_id="3a1b2c3d",
        on_ground=True,
        origin_iata="FRA",
        seen_at=A319.seen_at,
    )
    message = alert_message("Departures", aircraft)
    assert message.title == "SkyTripwire: unknown aircraft"
    assert "Route: FRA to ?" in message.body
    assert "Altitude: on ground" in message.body
    assert "Track:" not in message.body
    assert "Source: Flightradar24 (unofficial)" in message.body


async def test_send_to_all_channels() -> None:
    await AppriseNotifier().send("Near FRA", A319, ["skytest://ok", "skytest://ok2"])
    # Apprise sends in parallel, the order is not fixed.
    assert sorted(s["host"] for s in SENT) == ["ok", "ok2"]
    assert SENT[0]["title"] == "SkyTripwire: DLH4AB / D-AIBD / A319"


async def test_send_failure_raises() -> None:
    with pytest.raises(NotificationError, match=r"1 of 2 channel\(s\) failed"):
        await AppriseNotifier().send("Near FRA", A319, ["skytest://ok", "skytest://failure"])


async def test_send_test_message() -> None:
    await AppriseNotifier().send_test("skytest://ok")
    assert SENT[0]["title"] == "SkyTripwire: test notification"


@pytest.mark.parametrize("urls", [[], ["bogus://nothing"]])
async def test_invalid_input(urls: list[str]) -> None:
    with pytest.raises(NotificationError):
        await AppriseNotifier().send("x", A319, urls)
    assert SENT == []


def test_is_valid_url() -> None:
    assert is_valid_url("tgram://123456:ABCdefSecret/987654")
    assert is_valid_url("mailtos://user:hunter2@example.org?to=me@example.org")
    assert not is_valid_url("bogus://x")
    assert not is_valid_url("not a url")


@pytest.mark.parametrize(
    ("url", "secret"),
    [
        ("tgram://123456:ABCdefSecret/987654", "ABCdefSecret"),
        ("mailtos://user:hunter2@example.org?to=me@example.org", "hunter2"),
        ("bogus://user:hunter2@host", "hunter2"),
    ],
)
def test_mask_url_hides_secrets(url: str, secret: str) -> None:
    masked = mask_url(url)
    assert secret not in masked
    assert masked.startswith(url.split("://", maxsplit=1)[0] + "://")
    assert "?" not in masked


def test_redact() -> None:
    url = "tgram://123456:ABCdefSecret/987654321"
    text = "POST https://api.telegram.org/bot123456:ABCdefSecret/sendMessage to 987654321 failed"
    redacted = redact(text, [url])
    assert "ABCdefSecret" not in redacted
    assert "123456" not in redacted
    assert "987654321" not in redacted
    assert "failed" in redacted
