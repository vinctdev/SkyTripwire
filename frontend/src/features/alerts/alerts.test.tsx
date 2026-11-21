import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { ALERTS_PAGE_SIZE, type Alert } from "../../api/queries";
import { STORED } from "../../test/fixtures";
import { fakeBackend, renderApp } from "../../test/render";

function alert(id: number, overrides: Partial<Alert> = {}): Alert {
  return {
    id,
    filter_id: 7,
    filter_name: "Heavies near FRA",
    provider: "adsblol",
    aircraft_identity: "3c6444",
    hex: "3c6444",
    callsign: "DLH400",
    registration: "D-ABYA",
    type_code: "B748",
    latitude: 50.1,
    longitude: 8.6,
    altitude_ft: 10000,
    ground_speed_kts: 250,
    squawk: "1000",
    origin_iata: null,
    destination_iata: null,
    seen_at: "2026-11-18T10:00:00Z",
    notification_status: "sent",
    notification_error: null,
    created_at: "2026-11-18T10:00:01Z",
    ...overrides,
  };
}

afterEach(cleanup);

describe("alert history", () => {
  it("shows alert details, notification state and a tracking link", async () => {
    fakeBackend({
      "GET /api/filters": [STORED],
      "GET /api/alerts": [
        alert(2, { squawk: "7700", notification_status: "failed", notification_error: "Timeout" }),
        alert(1, { filter_id: null, hex: "~0001", callsign: null, notification_status: "skipped" }),
      ],
    });
    renderApp("/alerts");
    expect(await screen.findByText("DLH400")).toBeDefined();
    expect(screen.getByText("Squawk 7700 (emergency)")).toBeDefined();
    expect(screen.getByText("Notification failed")).toBeDefined();
    expect(screen.getByText("Timeout")).toBeDefined();
    expect(screen.getAllByText("10,000 ft")).toHaveLength(2);
    expect(screen.getByText("No channel")).toBeDefined();
    expect(screen.getByText(/Heavies near FRA \(deleted\)/)).toBeDefined();
    // Only the ICAO address gets a link, the TIS-B one (~) does not.
    const links = screen.getAllByRole("link", { name: "Track on globe.adsb.lol" });
    expect(links).toHaveLength(1);
    expect(links[0]?.getAttribute("href")).toBe("https://globe.adsb.lol/?icao=3c6444");
  });

  it("pages with before_id and filters by filter_id", async () => {
    const firstPage = Array.from({ length: ALERTS_PAGE_SIZE }, (_, i) => alert(100 - i));
    const requests = fakeBackend({
      "GET /api/filters": [STORED],
      "GET /api/alerts": (request) => {
        const before = new URL(request.url).searchParams.get("before_id");
        return Response.json(before ? [alert(1, { callsign: "OLDEST" })] : firstPage);
      },
    });
    renderApp("/alerts?filter=7");
    await userEvent.click(await screen.findByRole("button", { name: "Show older alerts" }));
    expect(await screen.findByText("OLDEST")).toBeDefined();
    expect(screen.queryByRole("button", { name: "Show older alerts" })).toBeNull();

    const queries = requests
      .filter((r) => r.path === "/api/alerts")
      .map((r) => Object.fromEntries(new URL(r.url).searchParams));
    expect(queries).toContainEqual({ limit: "50", filter_id: "7" });
    expect(queries).toContainEqual({ limit: "50", filter_id: "7", before_id: "51" });
  });

  it("clears the history after confirmation", async () => {
    const requests = fakeBackend({
      "GET /api/filters": [],
      "GET /api/alerts": [alert(1)],
      "DELETE /api/alerts": () => new Response(null, { status: 204 }),
    });
    renderApp("/alerts");
    await userEvent.click(await screen.findByRole("button", { name: "Clear history" }));
    expect(screen.getByText(/resets the cooldowns/)).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Delete all" }));
    await waitFor(() => {
      expect(requests.some((r) => r.method === "DELETE" && r.path === "/api/alerts")).toBe(true);
    });
  });

  it("shows a hint when there are no alerts", async () => {
    fakeBackend({ "GET /api/filters": [], "GET /api/alerts": [] });
    renderApp("/alerts");
    expect(await screen.findByText(/No alerts yet/)).toBeDefined();
  });
});
