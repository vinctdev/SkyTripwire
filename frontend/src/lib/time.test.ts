import { describe, expect, it } from "vitest";

import { formatDuration, formatRelative } from "./time";

describe("formatDuration", () => {
  it.each([
    [0, "0 s"],
    [59.6, "1 min"],
    [61, "1 min"],
    [3600, "1 h"],
    [3900, "1 h 5 min"],
    [86400 * 2 + 3600 * 4, "2 d 4 h"],
    [-5, "0 s"],
  ])("%d seconds is %s", (seconds, expected) => {
    expect(formatDuration(seconds)).toBe(expected);
  });
});

describe("formatRelative", () => {
  const now = new Date("2026-11-18T12:00:00Z");

  it("describes past and future times", () => {
    expect(formatRelative("2026-11-18T11:55:00Z", now)).toBe("5 min ago");
    expect(formatRelative("2026-11-18T12:02:00Z", now)).toBe("in 2 min");
    expect(formatRelative("2026-11-18T12:00:05Z", now)).toBe("just now");
    expect(formatRelative(null, now)).toBe("-");
  });
});
