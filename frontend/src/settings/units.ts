// The API always uses feet and knots (like ADS-B). Conversion happens only for display and input.

export const ALTITUDE_UNITS = ["ft", "m"] as const;
export const SPEED_UNITS = ["kts", "kmh"] as const;

export type AltitudeUnit = (typeof ALTITUDE_UNITS)[number];
export type SpeedUnit = (typeof SPEED_UNITS)[number];

const METERS_PER_FOOT = 0.3048;
const KMH_PER_KNOT = 1.852;

export const UNIT_LABELS: Record<AltitudeUnit | SpeedUnit, string> = {
  ft: "ft",
  m: "m",
  kts: "kts",
  kmh: "km/h",
};

export function altitudeFromFeet(feet: number, unit: AltitudeUnit): number {
  return unit === "m" ? Math.round(feet * METERS_PER_FOOT) : feet;
}

export function altitudeToFeet(value: number, unit: AltitudeUnit): number {
  return unit === "m" ? Math.round(value / METERS_PER_FOOT) : value;
}

export function speedFromKnots(knots: number, unit: SpeedUnit): number {
  return unit === "kmh" ? Math.round(knots * KMH_PER_KNOT) : knots;
}

export function speedToKnots(value: number, unit: SpeedUnit): number {
  return unit === "kmh" ? Math.round(value / KMH_PER_KNOT) : value;
}

// Distances (area radius) follow the speed unit: knots go with nautical miles, km/h with km.
export type DistanceUnit = "nm" | "km";
const KM_PER_NM = 1.852;

export function distanceUnitFor(speedUnit: SpeedUnit): DistanceUnit {
  return speedUnit === "kmh" ? "km" : "nm";
}

export function distanceFromNm(nm: number, unit: DistanceUnit): number {
  return unit === "km" ? Math.round(nm * KM_PER_NM * 10) / 10 : nm;
}

export function distanceToNm(value: number, unit: DistanceUnit): number {
  return unit === "km" ? value / KM_PER_NM : value;
}

export function formatDistance(nm: number, unit: DistanceUnit): string {
  return `${distanceFromNm(nm, unit).toLocaleString("en-US")} ${unit}`;
}

export function formatAltitude(feet: number | null | undefined, unit: AltitudeUnit): string {
  if (feet == null) return "-";
  return `${altitudeFromFeet(feet, unit).toLocaleString("en-US")} ${UNIT_LABELS[unit]}`;
}

export function formatSpeed(knots: number | null | undefined, unit: SpeedUnit): string {
  if (knots == null) return "-";
  return `${speedFromKnots(knots, unit).toLocaleString("en-US")} ${UNIT_LABELS[unit]}`;
}
