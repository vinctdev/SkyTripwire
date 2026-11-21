import { describe, expect, it } from "vitest";

import { STORED } from "../../test/fixtures";
import { describeFilter } from "./filterSummary";

describe("describeFilter", () => {
  it("lists the set criteria in the chosen units", () => {
    expect(
      describeFilter(STORED, { altitude: "ft", speed: "kts", distance: "nm" }, { A5: "Heavy" }),
    ).toEqual([
      "Within 30 nm of 50.0379, 8.5622",
      "Type: B744, A388",
      "Category: Heavy",
      "No military",
      "Altitude 1,000 ft to 35,000 ft",
      "Ground speed at most 450 kts",
    ]);
  });

  it("describes a worldwide filter in metric units", () => {
    const lines = describeFilter(
      {
        ...STORED,
        area: null,
        military: true,
        altitude_max_ft: null,
        ground_speed_max_kts: null,
        include_on_ground: true,
      },
      { altitude: "m", speed: "kmh", distance: "km" },
    );
    expect(lines[0]).toBe("Worldwide");
    expect(lines).toContain("Category: A5");
    expect(lines).toContain("Military only");
    expect(lines).toContain("Altitude at least 305 m");
    expect(lines).toContain("Including aircraft on the ground");
  });
});
