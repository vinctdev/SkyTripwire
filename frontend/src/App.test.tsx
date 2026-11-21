import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { fakeBackend, renderApp } from "./test/render";

afterEach(() => {
  cleanup();
  document.documentElement.className = "";
});

describe("App", () => {
  it("redirects to the filters page and shows the backend version", async () => {
    fakeBackend({});
    renderApp();
    expect(screen.getByRole("heading", { name: "Filters" })).toBeDefined();
    expect(await screen.findByText(/v1\.2\.3/)).toBeDefined();
  });

  it("navigates between pages", async () => {
    fakeBackend({ "GET /api/channels": [] });
    renderApp();
    await userEvent.click(screen.getByRole("link", { name: "Channels" }));
    expect(screen.getByRole("heading", { name: "Channels" })).toBeDefined();
  });

  it("starts in dark mode and toggles to light mode", async () => {
    fakeBackend({});
    renderApp();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Light mode" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
