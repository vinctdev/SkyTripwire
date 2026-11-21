import { describe, expect, it } from "vitest";

import {
  buildTelegramUrl,
  emptyChannelForm,
  hasCredentials,
  normalizeBotToken,
  validateChannelForm,
  type ChannelFormState,
} from "./channelForm";

const TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw";

function form(overrides: Partial<ChannelFormState>): ChannelFormState {
  return { ...emptyChannelForm(), name: "Phone", ...overrides };
}

describe("telegram", () => {
  it("builds the Apprise URL from token and chat id", () => {
    expect(buildTelegramUrl(` ${TOKEN} `, " 987654321 ")).toBe(`tgram://${TOKEN}/987654321`);
  });

  it("strips the bot prefix of a token copied from an API URL", () => {
    expect(normalizeBotToken(`bot${TOKEN}`)).toBe(TOKEN);
  });

  it.each(["987654321", "-1001234567890", "@my_channel"])("accepts chat id %s", (chatId) => {
    const result = validateChannelForm(form({ botToken: TOKEN, chatId }), true);
    expect(result.errors).toEqual({});
    expect(result.url).toBe(`tgram://${TOKEN}/${chatId}`);
  });

  it("rejects a username instead of a chat id and a malformed token", () => {
    const result = validateChannelForm(form({ botToken: "abc", chatId: "Username" }), true);
    expect(Object.keys(result.errors).sort()).toEqual(["botToken", "chatId"]);
  });

  it("requires both fields once one is filled when editing", () => {
    const result = validateChannelForm(form({ chatId: "987654321" }), false);
    expect(result.errors.botToken).toBeDefined();
  });
});

describe("validateChannelForm", () => {
  it("requires a name and credentials for a new channel", () => {
    const result = validateChannelForm(emptyChannelForm(), true);
    expect(Object.keys(result.errors).sort()).toEqual(["botToken", "chatId", "name"]);
  });

  it("keeps the stored URL when editing without credentials", () => {
    const state = form({ kind: "email" });
    expect(hasCredentials(state)).toBe(false);
    expect(validateChannelForm(state, false)).toEqual({ errors: {}, url: undefined });
  });

  it("checks the scheme of e-mail URLs", () => {
    const bad = validateChannelForm(form({ kind: "email", url: "smtp://x" }), true);
    expect(bad.errors.url).toMatch(/mailto/);
    const good = validateChannelForm(
      form({ kind: "email", url: "mailtos://user:pw@example.com?to=me@example.com" }),
      true,
    );
    expect(good.errors).toEqual({});
  });

  it("accepts any scheme for generic Apprise URLs", () => {
    const result = validateChannelForm(form({ kind: "apprise", url: "ntfy://topic" }), true);
    expect(result).toEqual({ errors: {}, url: "ntfy://topic" });
    const bad = validateChannelForm(form({ kind: "apprise", url: "no scheme" }), true);
    expect(bad.errors.url).toBeDefined();
  });
});
