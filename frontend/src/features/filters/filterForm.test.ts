import { describe, expect, it } from "vitest";

import { STORED } from "../../test/fixtures";
import {
  emptyFilterForm,
  filterToForm,
  filterToInput,
  parseList,
  parseNumber,
  validateFilterForm,
  worldwideIsSearchable,
  type FilterFormState,
  type FilterUnits,
} from "./filterForm";

const IMPERIAL: FilterUnits = { altitude: "ft", speed: "kts", distance: "nm" };
const METRIC: FilterUnits = { altitude: "m", speed: "kmh", distance: "km" };

function form(overrides: Partial<FilterFormState>): FilterFormState {
  return {
    ...emptyFilterForm(),
    name: "Test",
    latitude: "50",
    longitude: "8",
    radius: "20",
    ...overrides,
  };
}

describe("parsing", () => {
  it("splits, uppercases and deduplicates lists", () => {
    expect(parseList(" b744, A388;a35*  b744\n")).toEqual(["B744", "A388", "A35*"]);
    expect(parseList("  ")).toEqual([]);
  });

  it("parses numbers with decimal point or comma", () => {
    expect(parseNumber("")).toBeNull();
    expect(parseNumber("50,5")).toBe(50.5);
    expect(parseNumber("-8.25")).toBe(-8.25);
    expect(parseNumber("12abc")).toBeNaN();
  });
});

describe("validateFilterForm", () => {
  it("builds the request body in API units", () => {
    const { errors, body } = validateFilterForm(
      form({
        typeCodes: "b744",
        military: "only",
        altitudeMin: "3048",
        speedMax: "926",
        radius: "92.6",
        channelIds: [3, 1],
      }),
      { units: METRIC, fr24Enabled: false },
    );
    expect(errors).toEqual({});
    expect(body).toMatchObject({
      name: "Test",
      area: { latitude: 50, longitude: 8 },
      type_codes: ["B744"],
      military: true,
      altitude_min_ft: 10000,
      altitude_max_ft: null,
      ground_speed_max_kts: 500,
      channel_ids: [1, 3],
    });
    expect(body?.area?.radius_nm).toBeCloseTo(50, 5);
  });

  it("sends null as area for worldwide filters", () => {
    const { body } = validateFilterForm(form({ worldwide: true, registrations: "D-ABYA" }), {
      units: IMPERIAL,
      fr24Enabled: false,
    });
    expect(body?.area).toBeNull();
  });

  it("limits the radius to 250 nm without FR24", () => {
    const tooLarge = form({ radius: "251" });
    expect(
      validateFilterForm(tooLarge, { units: IMPERIAL, fr24Enabled: false }).errors.radius,
    ).toMatch(/250 nm/);
    expect(validateFilterForm(tooLarge, { units: IMPERIAL, fr24Enabled: true }).errors).toEqual({});
  });

  it("reports invalid values per field", () => {
    const { errors, body } = validateFilterForm(
      form({
        name: " ",
        latitude: "91",
        radius: "0",
        squawks: "7800",
        airlines: "LH",
        altitudeMin: "5000",
        altitudeMax: "1000",
        cooldownMinutes: "1.5",
      }),
      { units: IMPERIAL, fr24Enabled: false },
    );
    expect(body).toBeUndefined();
    expect(Object.keys(errors).sort()).toEqual([
      "airlines",
      "altitude",
      "cooldownMinutes",
      "latitude",
      "name",
      "radius",
      "squawks",
    ]);
    expect(errors.squawks).toMatch(/7800/);
  });

  it("keeps untouched values of a stored filter exactly", () => {
    const loaded = filterToForm(STORED, METRIC);
    expect(loaded.altitudeMax).toBe("10668");
    expect(loaded.radius).toBe("55.6");
    const { body } = validateFilterForm(loaded, {
      units: METRIC,
      fr24Enabled: false,
      original: { filter: STORED, form: loaded },
    });
    expect(body).toEqual(filterToInput(STORED));
  });

  it("converts values the user changed", () => {
    const loaded = filterToForm(STORED, METRIC);
    const { body } = validateFilterForm(
      { ...loaded, altitudeMax: "3000" },
      { units: METRIC, fr24Enabled: false, original: { filter: STORED, form: loaded } },
    );
    expect(body?.altitude_max_ft).toBe(9843);
    expect(body?.altitude_min_ft).toBe(1000);
  });
});

describe("worldwideIsSearchable", () => {
  it("needs an exact value or only military", () => {
    const base = form({ worldwide: true });
    expect(worldwideIsSearchable(base, false)).toBe(false);
    expect(worldwideIsSearchable({ ...base, typeCodes: "A38*" }, false)).toBe(false);
    expect(worldwideIsSearchable({ ...base, typeCodes: "A388" }, false)).toBe(true);
    expect(worldwideIsSearchable({ ...base, military: "only" }, false)).toBe(true);
    expect(worldwideIsSearchable({ ...base, airlines: "DLH" }, false)).toBe(false);
    expect(worldwideIsSearchable({ ...base, airlines: "DLH" }, true)).toBe(true);
  });
});
