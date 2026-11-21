import { cleanup, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { Channel } from "../../api/queries";
import { fakeBackend, renderApp } from "../../test/render";

const TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw";

const PHONE: Channel = {
  id: 1,
  name: "Phone",
  kind: "telegram",
  url_masked: "tgram://1...w/987654321/",
  enabled: true,
  filter_ids: [3, 4],
  created_at: "2026-11-18T10:00:00Z",
  updated_at: "2026-11-18T10:00:00Z",
};

afterEach(cleanup);

describe("channel list", () => {
  it("shows channels with masked URL and usage", async () => {
    fakeBackend({ "GET /api/channels": [PHONE] });
    renderApp("/channels");
    expect(await screen.findByText("Phone")).toBeDefined();
    expect(screen.getByText(PHONE.url_masked)).toBeDefined();
    expect(screen.getByText("Used by 2 filters")).toBeDefined();
  });

  it("shows a hint when there are no channels", async () => {
    fakeBackend({ "GET /api/channels": [] });
    renderApp("/channels");
    expect(await screen.findByText(/No channels yet/)).toBeDefined();
  });

  it("sends a test message to a stored channel", async () => {
    const requests = fakeBackend({
      "GET /api/channels": [PHONE],
      "POST /api/channels/1/test": { ok: false, error: "Unauthorized" },
    });
    renderApp("/channels");
    await userEvent.click(await screen.findByRole("button", { name: "Send test" }));
    expect(await screen.findByText(/Test message failed: Unauthorized/)).toBeDefined();
    expect(requests.some((r) => r.method === "POST" && r.path === "/api/channels/1/test")).toBe(
      true,
    );
  });

  it("deletes after confirmation", async () => {
    const requests = fakeBackend({
      "GET /api/channels": [PHONE],
      "DELETE /api/channels/1": () => new Response(null, { status: 204 }),
    });
    renderApp("/channels");
    await userEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByText(/Filters using it will no longer notify/)).toBeDefined();
    const confirm = screen.getAllByRole("button", { name: "Delete" }).at(-1);
    if (!confirm) throw new Error("confirm button missing");
    await userEvent.click(confirm);
    await waitFor(() => {
      expect(requests.some((r) => r.method === "DELETE")).toBe(true);
    });
  });
});

describe("channel editor", () => {
  it("builds the Telegram URL from token and chat id", async () => {
    const requests = fakeBackend({
      "GET /api/channels": [],
      "POST /api/channels": () => Response.json(PHONE, { status: 201 }),
    });
    renderApp("/channels/new");
    await userEvent.type(screen.getByLabelText("Name"), "Phone");
    await userEvent.type(screen.getByLabelText("Bot token"), TOKEN);
    await userEvent.type(screen.getByLabelText("Chat ID"), "987654321");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByRole("heading", { name: "Channels" });
    const create = requests.find((r) => r.method === "POST" && r.path === "/api/channels");
    expect(create?.body).toEqual({
      name: "Phone",
      kind: "telegram",
      enabled: true,
      url: `tgram://${TOKEN}/987654321`,
    });
  });

  it("shows validation errors and sends nothing", async () => {
    const requests = fakeBackend({});
    renderApp("/channels/new");
    await userEvent.type(screen.getByLabelText("Chat ID"), "@me");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Enter a name.")).toBeDefined();
    expect(screen.getByText("Enter the bot token.")).toBeDefined();
    expect(screen.getByText(/Expected a number/)).toBeDefined();
    expect(requests.filter((r) => r.path.startsWith("/api/channels"))).toEqual([]);
  });

  it("tests unsaved credentials", async () => {
    const requests = fakeBackend({ "POST /api/channels/test": { ok: true, error: null } });
    renderApp("/channels/new");
    await userEvent.type(screen.getByLabelText("Bot token"), TOKEN);
    await userEvent.type(screen.getByLabelText("Chat ID"), "-1001234567890");
    await userEvent.click(screen.getByRole("button", { name: "Send test message" }));
    expect(await screen.findByText(/Test message sent/)).toBeDefined();
    expect(requests.find((r) => r.path === "/api/channels/test")?.body).toEqual({
      kind: "telegram",
      url: `tgram://${TOKEN}/-1001234567890`,
    });
  });

  it("keeps stored credentials when editing without new ones", async () => {
    const requests = fakeBackend({
      "GET /api/channels": [PHONE],
      "GET /api/channels/1": PHONE,
      "PUT /api/channels/1": { ...PHONE, name: "Old phone" },
    });
    renderApp("/channels/1");
    const name = await screen.findByLabelText("Name");
    expect(screen.getByText(/Leave the fields below empty/)).toBeDefined();
    await userEvent.clear(name);
    await userEvent.type(name, "Old phone");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByRole("heading", { name: "Channels" });
    const put = requests.find((r) => r.method === "PUT");
    expect(put?.body).toEqual({ name: "Old phone", kind: "telegram", enabled: true });
  });
});
