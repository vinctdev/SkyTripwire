import type { FilterItem } from "../../api/queries";
import {
  formatAltitude,
  formatDistance,
  formatSpeed,
  type AltitudeUnit,
  type DistanceUnit,
  type SpeedUnit,
} from "../../settings/units";

export interface SummaryUnits {
  altitude: AltitudeUnit;
  speed: SpeedUnit;
  distance: DistanceUnit;
}

function range(min: string | null, max: string | null): string | null {
  if (min && max) return `${min} to ${max}`;
  if (min) return `at least ${min}`;
  if (max) return `at most ${max}`;
  return null;
}

/** Short human readable lines describing what a filter matches. */
export function describeFilter(
  filter: FilterItem,
  units: SummaryUnits,
  categoryLabels: Record<string, string> = {},
): string[] {
  const lines: string[] = [];
  const area = filter.area;
  lines.push(
    area
      ? `Within ${formatDistance(area.radius_nm, units.distance)} of ${area.latitude.toFixed(4)}, ${area.longitude.toFixed(4)}`
      : "Worldwide",
  );
  const lists: [string, string[]][] = [
    ["Type", filter.type_codes],
    ["Registration", filter.registrations],
    ["Callsign", filter.callsigns],
    ["Airline", filter.airlines],
    ["Squawk", filter.squawks],
    ["From", filter.origin_airports],
    ["To", filter.destination_airports],
  ];
  for (const [label, values] of lists) {
    if (values.length > 0) lines.push(`${label}: ${values.join(", ")}`);
  }
  if (filter.categories.length > 0)
    lines.push(`Category: ${filter.categories.map((c) => categoryLabels[c] ?? c).join(", ")}`);
  if (filter.military === true) lines.push("Military only");
  if (filter.military === false) lines.push("No military");
  if (filter.emergency_only) lines.push("Emergencies only");

  const altitude = range(
    filter.altitude_min_ft == null ? null : formatAltitude(filter.altitude_min_ft, units.altitude),
    filter.altitude_max_ft == null ? null : formatAltitude(filter.altitude_max_ft, units.altitude),
  );
  if (altitude) lines.push(`Altitude ${altitude}`);
  const speed = range(
    filter.ground_speed_min_kts == null
      ? null
      : formatSpeed(filter.ground_speed_min_kts, units.speed),
    filter.ground_speed_max_kts == null
      ? null
      : formatSpeed(filter.ground_speed_max_kts, units.speed),
  );
  if (speed) lines.push(`Ground speed ${speed}`);
  if (filter.include_on_ground) lines.push("Including aircraft on the ground");
  return lines;
}
