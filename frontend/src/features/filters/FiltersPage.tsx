import { useState } from "react";
import { Link } from "react-router";

import { providerLabel } from "../../api/labels";
import {
  useChannels,
  useConfig,
  useDeleteFilter,
  useFilters,
  useUpdateFilter,
  type FilterItem,
} from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import { Badge, Button, buttonClass, Card, Loading, Notice } from "../../components/ui";
import { usePreferences } from "../../settings/preferences";
import { distanceUnitFor } from "../../settings/units";
import { filterToInput } from "./filterForm";
import { describeFilter } from "./filterSummary";

export function FiltersPage() {
  const filters = useFilters();

  return (
    <>
      <PageHeader
        title="Filters"
        description="Each filter describes the aircraft you want to be alerted about."
      >
        <Link to="/filters/new" className={buttonClass("primary")}>
          Add filter
        </Link>
      </PageHeader>
      {filters.isPending && <Loading />}
      {filters.isError && <Notice tone="error">{filters.error.message}</Notice>}
      {filters.data?.length === 0 && (
        <Notice>No filters yet. Add one, e.g. all helicopters within 20 nm of your home.</Notice>
      )}
      {filters.data && filters.data.length > 0 && (
        <ul className="space-y-4">
          {filters.data.map((filter) => (
            <FilterRow key={filter.id} filter={filter} />
          ))}
        </ul>
      )}
    </>
  );
}

function FilterRow({ filter }: { filter: FilterItem }) {
  const prefs = usePreferences();
  const config = useConfig();
  const channels = useChannels();
  const update = useUpdateFilter();
  const remove = useDeleteFilter();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const labels = Object.fromEntries((config.data?.categories ?? []).map((c) => [c.code, c.label]));
  const lines = describeFilter(
    filter,
    {
      altitude: prefs.altitudeUnit,
      speed: prefs.speedUnit,
      distance: distanceUnitFor(prefs.speedUnit),
    },
    labels,
  );
  const channelNames = filter.channel_ids.map(
    (id) => channels.data?.find((c) => c.id === id)?.name ?? `#${String(id)}`,
  );

  return (
    <Card as="li">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">{filter.name}</h2>
            {!filter.enabled && <Badge tone="warning">Disabled</Badge>}
            {filter.enabled &&
              filter.served_by.map((provider) => (
                <Badge key={provider}>via {providerLabel(provider)}</Badge>
              ))}
          </div>
          <ul className="text-fg-muted">
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p className="text-sm text-fg-subtle">
            {channelNames.length > 0
              ? `Notifies: ${channelNames.join(", ")}`
              : "No channel: matches only appear under Alerts"}
            {` · Cooldown ${String(filter.cooldown_minutes)} min`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/alerts?filter=${String(filter.id)}`} className={buttonClass()}>
            Alerts
          </Link>
          <Link to={`/filters/${String(filter.id)}`} className={buttonClass()}>
            Edit
          </Link>
          <Button
            disabled={update.isPending}
            onClick={() => {
              update.mutate({
                id: filter.id,
                body: { ...filterToInput(filter), enabled: !filter.enabled },
              });
            }}
          >
            {filter.enabled ? "Disable" : "Enable"}
          </Button>
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
          <span className="mr-auto">Delete this filter? Its past alerts stay in the history.</span>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              remove.mutate(filter.id);
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
        {filter.unplannable_reason && (
          <Notice tone="error">Not checked right now: {filter.unplannable_reason}</Notice>
        )}
        {update.isError && <Notice tone="error">{update.error.message}</Notice>}
        {remove.isError && <Notice tone="error">{remove.error.message}</Notice>}
      </div>
    </Card>
  );
}
