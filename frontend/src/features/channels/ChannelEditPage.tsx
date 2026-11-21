import { useState, type SubmitEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import {
  useChannel,
  useCreateChannel,
  useTestChannel,
  useUpdateChannel,
  type Channel,
} from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import {
  Button,
  buttonClass,
  Checkbox,
  ExternalLink,
  Field,
  Loading,
  Notice,
  Select,
  TextInput,
} from "../../components/ui";
import {
  CHANNEL_KINDS,
  emptyChannelForm,
  hasCredentials,
  hasErrors,
  isChannelKind,
  KIND_LABELS,
  validateChannelForm,
  type ChannelFormField,
  type ChannelFormState,
} from "./channelForm";
import { TestResult } from "./ChannelsPage";
import { TelegramHelp } from "./TelegramHelp";

export function NewChannelPage() {
  return (
    <>
      <PageHeader title="Add channel" />
      <ChannelEditor />
    </>
  );
}

export function EditChannelPage() {
  const id = Number(useParams().channelId);
  const channel = useChannel(id);
  return (
    <>
      <PageHeader title="Edit channel" />
      {channel.isPending && <Loading />}
      {channel.isError && <Notice tone="error">{channel.error.message}</Notice>}
      {channel.data && <ChannelEditor key={channel.data.id} channel={channel.data} />}
    </>
  );
}

function initialState(channel: Channel | undefined): ChannelFormState {
  if (!channel) return emptyChannelForm();
  return {
    ...emptyChannelForm(),
    name: channel.name,
    kind: isChannelKind(channel.kind) ? channel.kind : "apprise",
    enabled: channel.enabled,
  };
}

function ChannelEditor({ channel }: { channel?: Channel }) {
  const navigate = useNavigate();
  const create = useCreateChannel();
  const update = useUpdateChannel(channel?.id ?? 0);
  const test = useTestChannel();
  const [state, setState] = useState(() => initialState(channel));
  const [submitted, setSubmitted] = useState(false);

  // A new channel, or a changed kind, needs credentials: the stored URL would not fit.
  const credentialsRequired = channel?.kind !== state.kind;
  const { errors, url } = validateChannelForm(state, credentialsRequired);
  const save = channel ? update : create;

  function set<K extends keyof ChannelFormState>(key: K, value: ChannelFormState[K]) {
    setState((current) => ({ ...current, [key]: value }));
    if (key !== "name" && key !== "enabled") test.reset();
  }

  function errorFor(field: ChannelFormField): string | undefined {
    return submitted ? errors[field] : undefined;
  }

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (hasErrors(errors)) return;
    const base = { name: state.name.trim(), kind: state.kind, enabled: state.enabled };
    const done = { onSuccess: () => void navigate("/channels") };
    if (channel) update.mutate(url === undefined ? base : { ...base, url }, done);
    else if (url !== undefined) create.mutate({ ...base, url }, done);
  }

  function onTest() {
    if (channel && !hasCredentials(state) && !credentialsRequired) {
      test.mutate({ id: channel.id });
      return;
    }
    setSubmitted(true);
    const credentialErrors = Object.keys(errors).filter((key) => key !== "name");
    if (credentialErrors.length > 0 || url === undefined) return;
    test.mutate({ kind: state.kind, url });
  }

  const inputProps = (field: ChannelFormField) => ({
    id: `channel-${field}`,
    "aria-invalid": errorFor(field) !== undefined,
    "aria-describedby": errorFor(field) ? `channel-${field}-error` : undefined,
  });

  return (
    <form noValidate onSubmit={onSubmit} className="max-w-xl space-y-5">
      <Field id="channel-name" label="Name" error={errorFor("name")}>
        <TextInput
          {...inputProps("name")}
          value={state.name}
          maxLength={100}
          placeholder="e.g. My phone"
          onChange={(e) => {
            set("name", e.target.value);
          }}
        />
      </Field>

      <Field id="channel-kind" label="Type">
        <Select
          id="channel-kind"
          value={state.kind}
          onChange={(e) => {
            if (isChannelKind(e.target.value)) set("kind", e.target.value);
          }}
        >
          {CHANNEL_KINDS.map((kind) => (
            <option key={kind} value={kind}>
              {KIND_LABELS[kind]}
            </option>
          ))}
        </Select>
      </Field>

      {channel && (
        <Notice>
          {credentialsRequired
            ? "The type changed, so new credentials are required."
            : `Stored credentials: ${channel.url_masked}. Leave the fields below empty to keep them.`}
        </Notice>
      )}

      {state.kind === "telegram" ? (
        <>
          <TelegramHelp />
          <Field id="channel-botToken" label="Bot token" error={errorFor("botToken")}>
            <TextInput
              {...inputProps("botToken")}
              value={state.botToken}
              autoComplete="off"
              spellCheck={false}
              placeholder="123456789:AAH..."
              onChange={(e) => {
                set("botToken", e.target.value);
              }}
            />
          </Field>
          <Field
            id="channel-chatId"
            label="Chat ID"
            hint="Your own chat ID is a positive number, group IDs are negative."
            error={errorFor("chatId")}
          >
            <TextInput
              {...inputProps("chatId")}
              value={state.chatId}
              autoComplete="off"
              spellCheck={false}
              placeholder="987654321"
              onChange={(e) => {
                set("chatId", e.target.value);
              }}
            />
          </Field>
        </>
      ) : (
        <Field
          id="channel-url"
          label={state.kind === "email" ? "E-mail URL" : "Apprise URL"}
          error={errorFor("url")}
          hint={
            state.kind === "email" ? (
              <>
                Format: <code>mailtos://user:password@example.com?to=you@example.com</code>. See the{" "}
                <ExternalLink href="https://github.com/caronc/apprise/wiki/Notify_email">
                  Apprise e-mail documentation
                </ExternalLink>{" "}
                for other providers and SMTP settings.
              </>
            ) : (
              <>
                Any service supported by Apprise, see the{" "}
                <ExternalLink href="https://github.com/caronc/apprise/wiki">
                  list of services
                </ExternalLink>
                .
              </>
            )
          }
        >
          <TextInput
            {...inputProps("url")}
            type="password"
            value={state.url}
            autoComplete="off"
            spellCheck={false}
            placeholder={state.kind === "email" ? "mailtos://..." : "scheme://..."}
            onChange={(e) => {
              set("url", e.target.value);
            }}
          />
        </Field>
      )}

      <Checkbox
        id="channel-enabled"
        label="Enabled"
        checked={state.enabled}
        onChange={(checked) => {
          set("enabled", checked);
        }}
      />

      {test.isError && <Notice tone="error">{test.error.message}</Notice>}
      {test.data && <TestResult ok={test.data.ok} error={test.data.error} />}
      {save.isError && <Notice tone="error">{save.error.message}</Notice>}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" disabled={save.isPending}>
          {save.isPending ? "Saving..." : "Save"}
        </Button>
        <Button disabled={test.isPending} onClick={onTest}>
          {test.isPending ? "Sending..." : "Send test message"}
        </Button>
        <Link to="/channels" className={buttonClass("ghost")}>
          Cancel
        </Link>
      </div>
    </form>
  );
}
