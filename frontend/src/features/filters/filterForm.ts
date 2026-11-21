// Form state, conversion and validation of the filter editor. Pure functions, no React.
//
// The API uses feet, knots and nautical miles. The form shows the units the user picked and
// converts on submit. Values the user did not touch are sent back unchanged, so switching to
// metric and saving does not shift them by rounding.

import type { FilterInput, FilterItem } from "../../api/queries";
import {
  altitudeFromFeet,
  altitudeToFeet,
  distanceFromNm,
  distanceToNm,
  speedFromKnots,
  speedToKnots,
  type AltitudeUnit,
  type DistanceUnit,
  type SpeedUnit,
} from "../../settings/units";

export interface FilterUnits {
  altitude: AltitudeUnit;
  speed: SpeedUnit;
  distance: DistanceUnit;
}

export type Military = "any" | "only" | "exclude";

export interface FilterFormState {
  name: string;
  enabled: boolean;
  cooldownMinutes: string;
  channelIds: number[];
  worldwide: boolean;
  latitude: string;
  longitude: string;
  radius: string;
  typeCodes: string;
  registrations: string;
  callsigns: string;
  airlines: string;
  squawks: string;
  categories: string[];
  military: Military;
  emergencyOnly: boolean;
  includeOnGround: boolean;
  altitudeMin: string;
  altitudeMax: string;
  speedMin: string;
  speedMax: string;
  originAirports: string;
  destinationAirports: string;
}

export type FilterFormField =
  | "name"
  | "cooldownMinutes"
  | "latitude"
  | "longitude"
  | "radius"
  | "typeCodes"
  | "registrations"
  | "callsigns"
  | "airlines"
  | "squawks"
  | "altitude"
  | "speed"
  | "originAirports"
  | "destinationAirports";

export type FilterFormErrors = Partial<Record<FilterFormField, string>>;

/** Radius limit of adsb.lol. Larger areas need the FR24 provider (up to the API limit). */
export const MAX_RADIUS_NM = 250;
export const MAX_RADIUS_NM_FR24 = 5000;
export const DEFAULT_RADIUS_NM = 25;
const MAX_LIST_ITEMS = 50;

type ListField =
  | "typeCodes"
  | "registrations"
  | "callsigns"
  | "airlines"
  | "squawks"
  | "originAirports"
  | "destinationAirports";

// Same rules as the backend (api/schemas.py), checked here for immediate feedback.
const LIST_RULES: Record<ListField, { pattern: RegExp; hint: string }> = {
  typeCodes: { pattern: /^[A-Z0-9*?]{1,6}$/, hint: "ICAO type codes like B744 or A35*" },
  registrations: { pattern: /^[A-Z0-9*?-]{1,12}$/, hint: "registrations like D-ABYA" },
  callsigns: { pattern: /^[A-Z0-9*?]{1,8}$/, hint: "callsigns like DLH400 or DLH*" },
  airlines: { pattern: /^[A-Z]{3}$/, hint: "three-letter ICAO airline codes like DLH" },
  squawks: { pattern: /^[0-7]{4}$/, hint: "four octal digits like 7700" },
  originAirports: { pattern: /^[A-Z0-9]{3}$/, hint: "three-letter IATA codes like FRA" },
  destinationAirports: { pattern: /^[A-Z0-9]{3}$/, hint: "three-letter IATA codes like FRA" },
};

export function emptyFilterForm(): FilterFormState {
  return {
    name: "",
    enabled: true,
    cooldownMinutes: "60",
    channelIds: [],
    worldwide: false,
    latitude: "",
    longitude: "",
    radius: "",
    typeCodes: "",
    registrations: "",
    callsigns: "",
    airlines: "",
    squawks: "",
    categories: [],
    military: "any",
    emergencyOnly: false,
    includeOnGround: false,
    altitudeMin: "",
    altitudeMax: "",
    speedMin: "",
    speedMax: "",
    originAirports: "",
    destinationAirports: "",
  };
}

function numberText(value: number | null | undefined): string {
  return value == null ? "" : String(value);
}

export function filterToForm(filter: FilterItem | undefined, units: FilterUnits): FilterFormState {
  const form = emptyFilterForm();
  if (!filter) return form;
  const join = (values: string[]) => values.join(", ");
  return {
    ...form,
    name: filter.name,
    enabled: filter.enabled,
    cooldownMinutes: String(filter.cooldown_minutes),
    channelIds: [...filter.channel_ids],
    worldwide: filter.area == null,
    latitude: numberText(filter.area?.latitude),
    longitude: numberText(filter.area?.longitude),
    radius: filter.area ? String(distanceFromNm(filter.area.radius_nm, units.distance)) : "",
    typeCodes: join(filter.type_codes),
    registrations: join(filter.registrations),
    callsigns: join(filter.callsigns),
    airlines: join(filter.airlines),
    squawks: join(filter.squawks),
    categories: [...filter.categories],
    military: filter.military === true ? "only" : filter.military === false ? "exclude" : "any",
    emergencyOnly: filter.emergency_only,
    includeOnGround: filter.include_on_ground,
    altitudeMin: numberText(
      filter.altitude_min_ft == null
        ? null
        : altitudeFromFeet(filter.altitude_min_ft, units.altitude),
    ),
    altitudeMax: numberText(
      filter.altitude_max_ft == null
        ? null
        : altitudeFromFeet(filter.altitude_max_ft, units.altitude),
    ),
    speedMin: numberText(
      filter.ground_speed_min_kts == null
        ? null
        : speedFromKnots(filter.ground_speed_min_kts, units.speed),
    ),
    speedMax: numberText(
      filter.ground_speed_max_kts == null
        ? null
        : speedFromKnots(filter.ground_speed_max_kts, units.speed),
    ),
    originAirports: join(filter.origin_airports),
    destinationAirports: join(filter.destination_airports),
  };
}

/** Splits "b744, A388 a35*" into normalized, unique values. */
export function parseList(text: string): string[] {
  const values = text
    .split(/[\s,;]+/)
    .map((v) => v.trim().toUpperCase())
    .filter((v) => v !== "");
  return [...new Set(values)];
}

/** Empty text is `null`, otherwise a number (decimal comma accepted) or `NaN`. */
export function parseNumber(text: string): number | null {
  const trimmed = text.trim().replace(",", ".");
  if (trimmed === "") return null;
  return /^-?\d+(\.\d+)?$/.test(trimmed) ? Number(trimmed) : Number.NaN;
}

export interface FilterFormContext {
  units: FilterUnits;
  fr24Enabled: boolean;
  /** When editing: the stored filter and the form state it was loaded into. */
  original?: { filter: FilterItem; form: FilterFormState };
}

export interface FilterFormResult {
  errors: FilterFormErrors;
  body: FilterInput | undefined;
}

export function validateFilterForm(
  state: FilterFormState,
  { units, fr24Enabled, original }: FilterFormContext,
): FilterFormResult {
  const errors: FilterFormErrors = {};

  // Untouched converted values keep their stored value (no rounding drift).
  function converted(
    field: "altitudeMin" | "altitudeMax" | "speedMin" | "speedMax" | "radius",
    stored: number | null | undefined,
    convert: (value: number) => number,
  ): number | null {
    if (state[field] === original?.form[field] && stored != null) return stored;
    const value = parseNumber(state[field]);
    return value === null || Number.isNaN(value) ? value : convert(value);
  }

  const name = state.name.trim();
  if (name === "") errors.name = "Enter a name.";
  else if (name.length > 100) errors.name = "At most 100 characters.";

  const cooldown = parseNumber(state.cooldownMinutes);
  if (cooldown === null || !Number.isInteger(cooldown) || cooldown < 0 || cooldown > 10_080)
    errors.cooldownMinutes = "Enter whole minutes between 0 and 10080 (one week).";

  let area: FilterInput["area"] = null;
  if (!state.worldwide) {
    const latitude = parseNumber(state.latitude);
    const longitude = parseNumber(state.longitude);
    const maxRadius = fr24Enabled ? MAX_RADIUS_NM_FR24 : MAX_RADIUS_NM;
    const radiusNm = converted("radius", original?.filter.area?.radius_nm, (v) =>
      distanceToNm(v, units.distance),
    );
    if (latitude === null || Number.isNaN(latitude) || latitude < -90 || latitude > 90)
      errors.latitude = "Pick a point on the map or enter a latitude between -90 and 90.";
    if (longitude === null || Number.isNaN(longitude) || longitude < -180 || longitude > 180)
      errors.longitude = "Enter a longitude between -180 and 180.";
    if (radiusNm === null || Number.isNaN(radiusNm) || radiusNm <= 0)
      errors.radius = "Enter a radius greater than 0.";
    else if (radiusNm > maxRadius + 1e-9)
      errors.radius = `At most ${String(distanceFromNm(maxRadius, units.distance))} ${units.distance}${
        fr24Enabled ? "." : " (limit of adsb.lol; larger areas need the FR24 source)."
      }`;
    if (latitude !== null && longitude !== null && radiusNm !== null)
      area = { latitude, longitude, radius_nm: radiusNm };
  }

  const lists = {} as Record<ListField, string[]>;
  for (const field of Object.keys(LIST_RULES) as ListField[]) {
    const values = parseList(state[field]);
    const { pattern, hint } = LIST_RULES[field];
    const invalid = values.filter((v) => !pattern.test(v));
    if (invalid.length > 0) errors[field] = `Invalid: ${invalid.join(", ")}. Expected ${hint}.`;
    else if (values.length > MAX_LIST_ITEMS)
      errors[field] = `At most ${String(MAX_LIST_ITEMS)} values.`;
    lists[field] = values;
  }

  const altitudeMin = converted("altitudeMin", original?.filter.altitude_min_ft, (v) =>
    altitudeToFeet(v, units.altitude),
  );
  const altitudeMax = converted("altitudeMax", original?.filter.altitude_max_ft, (v) =>
    altitudeToFeet(v, units.altitude),
  );
  const speedMin = converted("speedMin", original?.filter.ground_speed_min_kts, (v) =>
    speedToKnots(v, units.speed),
  );
  const speedMax = converted("speedMax", original?.filter.ground_speed_max_kts, (v) =>
    speedToKnots(v, units.speed),
  );
  const outOfRange = (v: number | null, min: number, max: number) =>
    v !== null && (Number.isNaN(v) || v < min || v > max);
  if (outOfRange(altitudeMin, -2000, 100_000) || outOfRange(altitudeMax, -2000, 100_000))
    errors.altitude = "Enter altitudes between -2,000 and 100,000 ft (or the same in m).";
  else if (altitudeMin !== null && altitudeMax !== null && altitudeMin > altitudeMax)
    errors.altitude = "The minimum is greater than the maximum.";
  if (outOfRange(speedMin, 0, 5000) || outOfRange(speedMax, 0, 5000))
    errors.speed = "Enter speeds between 0 and 5,000 kts (or the same in km/h).";
  else if (speedMin !== null && speedMax !== null && speedMin > speedMax)
    errors.speed = "The minimum is greater than the maximum.";

  if (Object.keys(errors).length > 0) return { errors, body: undefined };

  return {
    errors,
    body: {
      name,
      enabled: state.enabled,
      area,
      type_codes: lists.typeCodes,
      registrations: lists.registrations,
      callsigns: lists.callsigns,
      airlines: lists.airlines,
      squawks: lists.squawks,
      categories: [...state.categories].sort(),
      military: state.military === "only" ? true : state.military === "exclude" ? false : null,
      emergency_only: state.emergencyOnly,
      include_on_ground: state.includeOnGround,
      altitude_min_ft: altitudeMin === null ? null : Math.round(altitudeMin),
      altitude_max_ft: altitudeMax === null ? null : Math.round(altitudeMax),
      ground_speed_min_kts: speedMin,
      ground_speed_max_kts: speedMax,
      origin_airports: lists.originAirports,
      destination_airports: lists.destinationAirports,
      cooldown_minutes: cooldown ?? 60,
      channel_ids: [...state.channelIds].sort((a, b) => a - b),
    },
  };
}

/** Request body that stores a filter unchanged, e.g. to toggle `enabled` from the list. */
export function filterToInput(filter: FilterItem): FilterInput {
  return {
    name: filter.name,
    enabled: filter.enabled,
    area: filter.area,
    type_codes: filter.type_codes,
    registrations: filter.registrations,
    callsigns: filter.callsigns,
    airlines: filter.airlines,
    squawks: filter.squawks,
    categories: filter.categories,
    military: filter.military,
    emergency_only: filter.emergency_only,
    include_on_ground: filter.include_on_ground,
    altitude_min_ft: filter.altitude_min_ft,
    altitude_max_ft: filter.altitude_max_ft,
    ground_speed_min_kts: filter.ground_speed_min_kts,
    ground_speed_max_kts: filter.ground_speed_max_kts,
    origin_airports: filter.origin_airports,
    destination_airports: filter.destination_airports,
    cooldown_minutes: filter.cooldown_minutes,
    channel_ids: filter.channel_ids,
  };
}

/** Whether a worldwide filter has something the data sources can look up directly. */
export function worldwideIsSearchable(state: FilterFormState, fr24Enabled: boolean): boolean {
  const exact = (text: string) => {
    const values = parseList(text);
    return values.length > 0 && values.every((v) => !/[*?]/.test(v));
  };
  return (
    exact(state.registrations) ||
    exact(state.callsigns) ||
    exact(state.typeCodes) ||
    parseList(state.squawks).length > 0 ||
    (fr24Enabled && parseList(state.airlines).length > 0) ||
    state.military === "only"
  );
}
