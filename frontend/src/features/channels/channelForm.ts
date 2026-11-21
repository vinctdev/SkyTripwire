// Form state and validation of the channel editor. Pure functions, no React.
//
// Channel URLs are write-only in the API: when editing, the stored credentials are not known.
// Leaving all credential fields empty keeps them (the request is sent without `url`).

export const CHANNEL_KINDS = ["telegram", "email", "apprise"] as const;
export type ChannelKind = (typeof CHANNEL_KINDS)[number];

export const KIND_LABELS: Record<ChannelKind, string> = {
  telegram: "Telegram",
  email: "E-mail",
  apprise: "Other (Apprise URL)",
};

export interface ChannelFormState {
  name: string;
  kind: ChannelKind;
  enabled: boolean;
  botToken: string;
  chatId: string;
  url: string;
}

export type ChannelFormField = "name" | "botToken" | "chatId" | "url";
export type ChannelFormErrors = Partial<Record<ChannelFormField, string>>;

export interface ChannelFormResult {
  errors: ChannelFormErrors;
  /** New URL built from the inputs, `undefined` if the stored one is kept. */
  url: string | undefined;
}

export function emptyChannelForm(): ChannelFormState {
  return { name: "", kind: "telegram", enabled: true, botToken: "", chatId: "", url: "" };
}

export function isChannelKind(value: string): value is ChannelKind {
  return (CHANNEL_KINDS as readonly string[]).includes(value);
}

// Bot token as issued by @BotFather: "<bot id>:<secret>".
const BOT_TOKEN = /^\d+:[A-Za-z0-9_-]+$/;
// Numeric chat id (negative for groups and channels) or the @name of a public channel.
const CHAT_ID = /^(-?\d+|@[A-Za-z0-9_]{5,32})$/;

/** Accepts the token also when copied from an API URL ("bot123:ABC"). */
export function normalizeBotToken(value: string): string {
  const token = value.trim();
  return /^bot\d+:/i.test(token) ? token.slice(3) : token;
}

export function buildTelegramUrl(botToken: string, chatId: string): string {
  return `tgram://${normalizeBotToken(botToken)}/${chatId.trim()}`;
}

/** Whether the user typed any credentials (otherwise the stored ones are kept on update). */
export function hasCredentials(state: ChannelFormState): boolean {
  if (state.kind === "telegram") return state.botToken.trim() !== "" || state.chatId.trim() !== "";
  return state.url.trim() !== "";
}

/**
 * Validates the form. `credentialsRequired` is true when creating a channel or when the kind
 * of an existing channel changes (the stored URL does not fit the new kind).
 */
export function validateChannelForm(
  state: ChannelFormState,
  credentialsRequired: boolean,
): ChannelFormResult {
  const errors: ChannelFormErrors = {};
  if (state.name.trim() === "") errors.name = "Enter a name.";
  else if (state.name.trim().length > 100) errors.name = "At most 100 characters.";

  if (!credentialsRequired && !hasCredentials(state)) return { errors, url: undefined };

  if (state.kind === "telegram") {
    const token = normalizeBotToken(state.botToken);
    const chatId = state.chatId.trim();
    if (token === "") errors.botToken = "Enter the bot token.";
    else if (!BOT_TOKEN.test(token))
      errors.botToken = "Expected the format 123456789:ABC... as sent by @BotFather.";
    if (chatId === "") errors.chatId = "Enter the chat ID.";
    else if (!CHAT_ID.test(chatId))
      errors.chatId = "Expected a number (e.g. 987654321 or -1001234567890) or @channelname.";
    return { errors, url: buildTelegramUrl(token, chatId) };
  }

  const url = state.url.trim();
  if (url === "") errors.url = "Enter the URL.";
  else if (url.length > 2000) errors.url = "At most 2000 characters.";
  else if (state.kind === "email" && !/^mailtos?:\/\//i.test(url))
    errors.url = "An e-mail URL starts with mailto:// or mailtos://.";
  else if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(url))
    errors.url = "Expected an Apprise URL like scheme://...";
  return { errors, url };
}

export function hasErrors(errors: ChannelFormErrors): boolean {
  return Object.keys(errors).length > 0;
}
