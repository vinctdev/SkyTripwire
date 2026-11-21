import { describe, expect, it } from "vitest";

import {
  altitudeFromFeet,
  altitudeToFeet,
  distanceFromNm,
  distanceToNm,
  distanceUnitFor,
  formatAltitude,
  formatDistance,
  formatSpeed,
  speedFromKnots,
  speedToKnots,
} from "./units";

describe("units", () => {
  it("keeps feet and knots unchanged", () => {
    expect(altitudeFromFeet(35000, "ft")).toBe(35000);
    expect(altitudeToFeet(35000, "ft")).toBe(35000);
    expect(speedFromKnots(450, "kts")).toBe(450);
    expect(speedToKnots(450, "kts")).toBe(450);
  });

  it("converts to metric and rounds", () => {
    expect(altitudeFromFeet(10000, "m")).toBe(3048);
    expect(altitudeToFeet(3048, "m")).toBe(10000);
    expect(speedFromKnots(100, "kmh")).toBe(185);
    expect(speedToKnots(185, "kmh")).toBe(100);
  });

  it("derives the distance unit from the speed unit", () => {
    expect(distanceUnitFor("kts")).toBe("nm");
    expect(distanceUnitFor("kmh")).toBe("km");
    expect(distanceFromNm(50, "km")).toBe(92.6);
    expect(distanceToNm(92.6, "km")).toBeCloseTo(50, 5);
    expect(formatDistance(250, "nm")).toBe("250 nm");
  });

  it("formats values and missing values", () => {
    expect(formatAltitude(35000, "ft")).toBe("35,000 ft");
    expect(formatAltitude(10000, "m")).toBe("3,048 m");
    expect(formatSpeed(100, "kmh")).toBe("185 km/h");
    expect(formatSpeed(null, "kts")).toBe("-");
    expect(formatAltitude(undefined, "m")).toBe("-");
  });
});
