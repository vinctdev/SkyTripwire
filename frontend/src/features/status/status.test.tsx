import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { Status } from "../../api/queries";
import { fakeBackend, renderApp } from "../../test/render";
import { budgetLevel } from "./BudgetMeter";

const STATUS: Status = {
  worker: {
    enabled: true,
    last_cycle_started_at: new Date(Date.now() - 125_000).toISOString(),
    last_cycle_finished_at: new Date(Date.now() - 120_000).toISOString(),
    next_cycle_at: new Date(Date.now() + 182_000).toISOString(),
    interval_seconds: 300,
    last_error: null,
    last_requests_sent: 2,
    last_aircraft_seen: 41,
    last_new_alerts: 1,
    provider_issues: {},
  },
  providers: [
    {
      name: "adsblol",
      provides: [],
      daily_budget: 450,
      requests_in_window: 380,
      window_started_at: "2026-11-18T00:00:00Z",
      planned_requests_per_cycle: 2,
      blocked_until: null,
      last_success_at: new Date(Date.now() - 120_000).toISOString(),
      last_error_at: null,
      last_error: null,
    },
  ],
  unplannable: [{ filter_id: 8, filter_name: "Broken", reason: "Area radius is too large." }],
};

afterEach(cleanup);

describe("budgetLevel", () => {
  it("marks near and full budgets", () => {
    expect(budgetLevel(100, 450)).toBe("normal");
    expect(budgetLevel(360, 450)).toBe("near");
    expect(budgetLevel(450, 450)).toBe("full");
    expect(budgetLevel(0, 0)).toBe("full");
  });
});

describe("status page", () => {
  it("shows worker, budget and unplannable filters", async () => {
    fakeBackend({ "GET /api/status": STATUS });
    renderApp("/status");
    expect(await screen.findByText("Data source: adsb.lol")).toBeDefined();
    // Last check and last success of the provider.
    expect(screen.getAllByText("2 min ago")).toHaveLength(2);
    expect(screen.getByText("in 3 min")).toBeDefined();
    expect(screen.getByText("every 5 min")).toBeDefined();
    expect(screen.getByText("41 aircraft, 1 new alert")).toBeDefined();
    expect(screen.getByText("380 of 450 requests (84%)")).toBeDefined();
    expect(screen.getByText("Near limit")).toBeDefined();
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("380");
    expect(screen.getByText("about 576")).toBeDefined();
    expect(screen.getByRole("link", { name: "Broken" }).getAttribute("href")).toBe("/filters/8");
  });

  it("warns when the worker is disabled or a source is paused", async () => {
    const provider = STATUS.providers[0];
    if (!provider) throw new Error("fixture");
    fakeBackend({
      "GET /api/status": {
        ...STATUS,
        worker: { ...STATUS.worker, enabled: false },
        providers: [
          {
            ...provider,
            blocked_until: new Date(Date.now() + 900_000).toISOString(),
            last_error: "HTTP 429",
          },
        ],
      },
    });
    renderApp("/status");
    expect(await screen.findByText(/polling worker is disabled/)).toBeDefined();
    expect(screen.getByText(/Paused until/)).toBeDefined();
    expect(screen.getByText("Last error message: HTTP 429")).toBeDefined();
  });

  it("states the usage terms of the FR24 source", async () => {
    const provider = STATUS.providers[0];
    if (!provider) throw new Error("fixture");
    fakeBackend({
      "GET /api/status": { ...STATUS, providers: [provider, { ...provider, name: "fr24" }] },
    });
    renderApp("/status");
    expect(await screen.findByText("Data source: FR24 (unofficial)")).toBeDefined();
    // Only once: the adsb.lol card has no such notice.
    expect(screen.getAllByText(/For personal and educational use only/)).toHaveLength(1);
  });
});
