"""Text of an alert notification. Plain text, so it reads well in Telegram and e-mail."""

from dataclasses import dataclass

from skytripwire.engine.matcher import EMERGENCY_SQUAWKS
from skytripwire.providers.base import Aircraft

PROVIDER_LABELS = {"adsblol": "adsb.lol", "fr24": "Flightradar24 (unofficial)"}


@dataclass(frozen=True, slots=True)
class Message:
    title: str
    body: str


def alert_message(filter_name: str, aircraft: Aircraft) -> Message:
    headline = " / ".join(
        part for part in (aircraft.callsign, aircraft.registration, aircraft.type_code) if part
    )
    lines = [f"Filter: {filter_name}"]
    lines += _line("Callsign", aircraft.callsign)
    lines += _line("Registration", aircraft.registration)
    lines += _line("Type", aircraft.type_code)
    lines += _line("Airline", aircraft.airline_icao)
    if aircraft.origin_iata or aircraft.destination_iata:
        lines.append(f"Route: {aircraft.origin_iata or '?'} to {aircraft.destination_iata or '?'}")
    if aircraft.on_ground:
        lines.append("Altitude: on ground")
    elif aircraft.altitude_ft is not None:
        lines.append(f"Altitude: {aircraft.altitude_ft:,} ft")
    if aircraft.ground_speed_kts is not None:
        lines.append(f"Ground speed: {aircraft.ground_speed_kts:.0f} kts")
    if aircraft.squawk:
        emergency = " (emergency)" if aircraft.squawk in EMERGENCY_SQUAWKS else ""
        lines.append(f"Squawk: {aircraft.squawk}{emergency}")
    lines += _line("Emergency", aircraft.emergency)
    if aircraft.military:
        lines.append("Military: yes")
    if aircraft.latitude is not None and aircraft.longitude is not None:
        lines.append(f"Position: {aircraft.latitude:.4f}, {aircraft.longitude:.4f}")
    if aircraft.hex and not aircraft.hex.startswith("~"):
        lines.append(f"Track: https://globe.adsb.lol/?icao={aircraft.hex}")
    lines.append(f"Seen: {aircraft.seen_at:%Y-%m-%d %H:%M:%S} UTC")
    lines.append(f"Source: {PROVIDER_LABELS.get(aircraft.provider, aircraft.provider)}")
    return Message(title=f"SkyTripwire: {headline or 'unknown aircraft'}", body="\n".join(lines))


def channel_test_message() -> Message:
    return Message(
        title="SkyTripwire: test notification",
        body="This channel is set up correctly. Alerts will arrive like this message.",
    )


def _line(label: str, value: str | None) -> list[str]:
    return [f"{label}: {value}"] if value else []
