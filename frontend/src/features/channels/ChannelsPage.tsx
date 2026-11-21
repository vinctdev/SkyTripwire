import { useState } from "react";
import { Link } from "react-router";

import { useChannels, useDeleteChannel, useTestChannel, type Channel } from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import { Badge, Button, buttonClass, Card, Loading, Notice } from "../../components/ui";
import { isChannelKind, KIND_LABELS } from "./channelForm";

export function ChannelsPage() {
  const channels = useChannels();

  return (
    <>
      <PageHeader
        title="Channels"
        description="Where alerts are sent. Each filter picks one or more channels."
      >
        <Link to="/channels/new" className={buttonClass("primary")}>
          Add channel
        </Link>
      </PageHeader>
      {channels.isPending && <Loading />}
      {channels.isError && <Notice tone="error">{channels.error.message}</Notice>}
      {channels.data?.length === 0 && (
        <Notice>No channels yet. Add a Telegram bot or an e-mail address to receive alerts.</Notice>
      )}
      {channels.data && channels.data.length > 0 && (
        <ul className="space-y-4">
          {channels.data.map((channel) => (
            <ChannelRow key={channel.id} channel={channel} />
          ))}
        </ul>
      )}
    </>
  );
}

function ChannelRow({ channel }: { channel: Channel }) {
  const test = useTestChannel();
  const remove = useDeleteChannel();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const used = channel.filter_ids.length;
  const kindLabel = isChannelKind(channel.kind) ? KIND_LABELS[channel.kind] : channel.kind;

  return (
    <Card as="li">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{channel.name}</h2>
            <Badge>{kindLabel}</Badge>
            {!channel.enabled && <Badge tone="warning">Disabled</Badge>}
          </div>
          <p className="font-mono text-sm break-all text-fg-muted">{channel.url_masked}</p>
          <p className="text-sm text-fg-subtle">
            {used === 0
              ? "Not used by any filter"
              : `Used by ${String(used)} filter${used === 1 ? "" : "s"}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={test.isPending}
            onClick={() => {
              test.mutate({ id: channel.id });
            }}
          >
            {test.isPending ? "Sending..." : "Send test"}
          </Button>
          <Link to={`/channels/${String(channel.id)}`} className={buttonClass()}>
            Edit
          </Link>
          {!confirmDelete && (
            <Button
              variant="ghost"
              onClick={() => {
                setConfirmDelete(true);
              }}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      {confirmDelete && (
        <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-danger-line bg-danger-soft px-4 py-3 text-danger-text">
          <span className="mr-auto">
            Delete this channel?
            {used > 0 && " Filters using it will no longer notify through it."}
          </span>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(channel.id);
            }}
          >
            Delete
          </Button>
          <Button
            onClick={() => {
              setConfirmDelete(false);
            }}
          >
            Cancel
          </Button>
        </div>
      )}

      <div className="mt-3 space-y-2 empty:hidden">
        {remove.isError && <Notice tone="error">{remove.error.message}</Notice>}
        {test.isError && <Notice tone="error">{test.error.message}</Notice>}
        {test.data && <TestResult ok={test.data.ok} error={test.data.error} />}
      </div>
    </Card>
  );
}

export function TestResult({ ok, error }: { ok: boolean; error?: string | null | undefined }) {
  return ok ? (
    <Notice tone="success">Test message sent. Check that it arrived.</Notice>
  ) : (
    <Notice tone="error">Test message failed: {error ?? "unknown error"}</Notice>
  );
}
