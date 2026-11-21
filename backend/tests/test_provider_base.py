from datetime import UTC, datetime

import pytest

from skytripwire.providers.base import (
    Aircraft,
    AreaQuery,
    GlobalField,
    GlobalQuery,
    airline_from_callsign,
)


@pytest.mark.parametrize(
    ("callsign", "expected"),
    [
        ("DLH4AB", "DLH"),
        ("RYR123", "RYR"),
        ("DEXYZ", None),
        ("N123AB", None),
        ("", None),
        (None, None),
    ],
)
def test_airline_from_callsign(callsign: str | None, expected: str | None) -> None:
    assert airline_from_callsign(callsign) == expected


def test_global_query_normalizes_value() -> None:
    assert GlobalQuery(GlobalField.REGISTRATION, " d-aibd ").value == "D-AIBD"
    assert GlobalQuery(GlobalField.HEX, "3C6444").value == "3c6444"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (GlobalField.TYPE, ""),
        (GlobalField.MILITARY, "x"),
        (GlobalField.SQUAWK, "7800"),
        (GlobalField.SQUAWK, "770"),
    ],
)
def test_global_query_rejects_invalid(field: GlobalField, value: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        GlobalQuery(field, value)


@pytest.mark.parametrize(
    ("lat", "lon", "radius"),
    [(91, 0, 10), (0, 181, 10), (0, 0, 0), (0, 0, float("inf"))],
)
def test_area_query_rejects_invalid(lat: float, lon: float, radius: float) -> None:
    with pytest.raises(ValueError, match=r"."):
        AreaQuery(lat, lon, radius)


def test_identity_prefers_hex() -> None:
    seen = datetime(2026, 11, 18, tzinfo=UTC)
    with_hex = Aircraft(provider="fr24", source_id="3a1b2c3d", hex="3c6444", seen_at=seen)
    without_hex = Aircraft(provider="fr24", source_id="3a1b2c3d", seen_at=seen)
    assert with_hex.identity == "3c6444"
    assert without_hex.identity == "fr24:3a1b2c3d"
