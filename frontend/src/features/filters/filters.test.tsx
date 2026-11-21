import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AppConfig, Channel } from "../../api/queries";
import { fakeBackend, renderApp } from "../../test/render";
import type { AreaMapProps } from "./AreaMap";
import { STORED } from "../../test/fixtures";

// Leaflet needs a real browser; the stub lets tests "click" a point.
vi.mock("./AreaMap", () => ({
  AreaMap: ({ onPick }: AreaMapProps) => (
    <button
      type="button"
      onClick={() => {
        onPick(50.03791, 368.56223);
      }}
    >
      Pick point
    </button>
  ),
}));

const CONFIG: AppConfig = {
  version: "1.2.3",
  fr24_enabled: false,
  providers: ["adsblol"],
  min_poll_interval_seconds: 60,
  categories: [
    { code: "A5", label: "Heavy" },
    { code: "A7", label: "Rotorcraft (helicopter)" },
  ],
};

const CHANNEL: Channel = {
  id: 2,
  name: "Phone",
  kind: "telegram",
  url_masked: "tgram://1...w/1/",
  enabled: true,
  filter_ids: [7],
  created_at: "2026-11-18T10:00:00Z",
  updated_at: "2026-11-18T10:00:00Z",
};

afterEach(cleanup);

describe("filter list", () => {
  it("shows the summary, source, channels and planner problems", async () => {
    fakeBackend({
      "GET /api/config": CONFIG,
      "GET /api/channels": [CHANNEL],
      "GET /api/filters": [
        STORED,
        { ...STORED, id: 8, name: "Broken", served_by: [], unplannable_reason: "Too large." },
      ],
    });
    renderApp("/filters");
    expect(await screen.findByText("Heavies near FRA")).toBeDefined();
    expect(screen.getAllByText("Within 30 nm of 50.0379, 8.5622")).toHaveLength(2);
    expect(screen.getByText("via adsb.lol")).toBeDefined();
    expect(await screen.findAllByText(/Notifies: Phone/)).toHaveLength(2);
    expect(screen.getByText("Not checked right now: Too large.")).toBeDefined();
  });

  it("disables a filter with an unchanged body", async () => {
    const requests = fakeBackend({
      "GET /api/config": CONFIG,
      "GET /api/channels": [],
      "GET /api/filters": [STORED],
      "PUT /api/filters/7": { ...STORED, enabled: false },
    });
    renderApp("/filters");
    await userEvent.click(await screen.findByRole("button", { name: "Disable" }));
    await waitFor(() => {
      expect(requests.find((r) => r.method === "PUT")?.body).toMatchObject({
        name: STORED.name,
        enabled: false,
        area: STORED.area,
        altitude_max_ft: 35000,
      });
    });
  });
});

describe("filter editor", () => {
  it("creates an area filter picked on the map", async () => {
    const requests = fakeBackend({
      "GET /api/config": CONFIG,
      "GET /api/channels": [CHANNEL],
      "GET /api/filters": [],
      "POST /api/filters": () => Response.json(STORED, { status: 201 }),
    });
    renderApp("/filters/new");
    await userEvent.type(await screen.findByLabelText("Name"), "Helicopters");
    await userEvent.click(await screen.findByRole("button", { name: "Pick point" }));
    expect(screen.getByLabelText<HTMLInputElement>("Longitude").value).toBe("8.5622");
    expect(screen.getByLabelText<HTMLInputElement>("Radius (nm)").value).toBe("25");
    await userEvent.click(screen.getByLabelText("Rotorcraft (helicopter)"));
    await userEvent.click(await screen.findByLabelText("Phone"));
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByRole("heading", { name: "Filters" });
    expect(requests.find((r) => r.method === "POST")?.body).toMatchObject({
      name: "Helicopters",
      area: { latitude: 50.0379, longitude: 8.5622, radius_nm: 25 },
      categories: ["A7"],
      channel_ids: [2],
    });
  });

  it("shows the reason when the backend rejects a filter", async () => {
    fakeBackend({
      "GET /api/config": CONFIG,
      "GET /api/channels": [],
      "POST /api/filters": () =>
        Response.json({ detail: "A worldwide filter needs exact values." }, { status: 422 }),
    });
    renderApp("/filters/new");
    await userEvent.type(await screen.findByLabelText("Name"), "Everything");
    await userEvent.click(screen.getByLabelText("Worldwide"));
    expect(screen.getByText(/A worldwide filter needs at least one exact/)).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("A worldwide filter needs exact values.")).toBeDefined();
  });

  it("validates before sending", async () => {
    const requests = fakeBackend({ "GET /api/config": CONFIG, "GET /api/channels": [] });
    renderApp("/filters/new");
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(screen.getByText("Enter a name.")).toBeDefined();
    expect(screen.getByText(/Pick a point on the map/)).toBeDefined();
    expect(requests.some((r) => r.path === "/api/filters")).toBe(false);
  });

  it("loads a stored filter and saves it unchanged", async () => {
    const requests = fakeBackend({
      "GET /api/config": CONFIG,
      "GET /api/channels": [CHANNEL],
      "GET /api/filters": [STORED],
      "GET /api/filters/7": STORED,
      "PUT /api/filters/7": STORED,
    });
    renderApp("/filters/7");
    expect((await screen.findByLabelText<HTMLInputElement>("Name")).value).toBe(STORED.name);
    expect(screen.getByLabelText<HTMLInputElement>("Aircraft types (ICAO)").value).toBe(
      "B744, A388",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByRole("heading", { name: "Filters" });
    const put = requests.find((r) => r.method === "PUT");
    expect(put?.body).toMatchObject({ area: STORED.area, military: false, categories: ["A5"] });
  });
});
