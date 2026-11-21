import { useState } from "react";
import { Link, useSearchParams } from "react-router";

import { providerLabel } from "../../api/labels";
import { useAlerts, useClearAlerts, useFilters, type Alert } from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import {
  Badge,
  Button,
  Card,
  ExternalLink,
  linkClass,
  Loading,
  Notice,
  Select,
  type BadgeTone,
} from "../../components/ui";
import { formatDateTime } from "../../lib/time";
import { usePreferences } from "../../settings/preferences";
import { formatAltitude, formatSpeed } from "../../settings/units";

const EMERGENCY_SQUAWKS: Record<string, string> = {
  "7500": "hijack",
  "7600": "radio failure",
  "7700": "emergency",
};

const NOTIFICATION_BADGES: Record<string, { label: string; tone: BadgeTone }> = {
  sent: { label: "Notified", tone: "success" },
  failed: { label: "Notification failed", tone: "danger" },
  skipped: { label: "No channel", tone: "neutral" },
  pending: { label: "Sending", tone: "info" },
};

export function AlertsPage() {
  const [params, setParams] = useSearchParams();
  const filterParam = params.get("filter");
  const filterId = filterParam && /^\d+$/.test(filterParam) ? Number(filterParam) : undefined;
  const filters = useFilters();
  const alerts = useAlerts(filterId);
  const clear = useClearAlerts();
  const [confirmClear, setConfirmClear] = useState(false);

  const items = alerts.data?.pages.flat() ?? [];

  return (
    <>
      <PageHeader title="Alerts">
        {!confirmClear && (
          <Button
            disabled={items.length === 0}
            onClick={() => {
              setConfirmClear(true);
            }}
          >
            Clear history
          </Button>
        )}
      </PageHeader>

      {confirmClear && (
        <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-danger-line bg-danger-soft px-4 py-3 text-danger-text">
          <span className="mr-auto">
            Delete all alerts of all filters? This also resets the cooldowns, so aircraft that are
            still in range will alert again.
          </span>
          <Button
            variant="danger"
            disabled={clear.isPending}
            onClick={() => {
              clear.mutate(undefined, {
                onSuccess: () => {
                  setConfirmClear(false);
                },
              });
            }}
          >
            Delete all
          </Button>
          <Button
            onClick={() => {
              setConfirmClear(false);
            }}
          >
            Cancel
          </Button>
        </div>
      )}
      {clear.isError && <Notice tone="error">{clear.error.message}</Notice>}

      <div className="mb-5 max-w-xs">
        <label htmlFor="alerts-filter" className="sr-only">
          Show alerts of
        </label>
        <Select
          id="alerts-filter"
          value={filterId === undefined ? "" : String(filterId)}
          onChange={(e) => {
            setParams(e.target.value ? { filter: e.target.value } : {});
          }}
        >
          <option value="">All filters</option>
          {filters.data?.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </Select>
      </div>

      {alerts.isPending && <Loading />}
      {alerts.isError && <Notice tone="error">{alerts.error.message}</Notice>}
      {alerts.isSuccess && items.length === 0 && (
        <Notice>
          No alerts yet. They appear here as soon as an aircraft matches one of your filters.
        </Notice>
      )}
      {items.length > 0 && (
        <ul className="space-y-4">
          {items.map((alert) => (
            <AlertRow key={alert.id} alert={alert} />
          ))}
        </ul>
      )}
      {alerts.hasNextPage && (
        <div className="mt-5">
          <Button
            disabled={alerts.isFetchingNextPage}
            onClick={() => {
              void alerts.fetchNextPage();
            }}
          >
            {alerts.isFetchingNextPage ? "Loading..." : "Show older alerts"}
          </Button>
        </div>
      )}
    </>
  );
}

function AlertRow({ alert }: { alert: Alert }) {
  const prefs = usePreferences();
  const title = alert.callsign ?? alert.registration ?? alert.hex ?? alert.aircraft_identity;
  const identity = [
    alert.registration && alert.registration !== title ? alert.registration : null,
    alert.type_code,
    alert.hex ? `hex ${alert.hex.toUpperCase()}` : null,
  ].filter(Boolean);
  const badge = NOTIFICATION_BADGES[alert.notification_status] ?? {
    label: alert.notification_status,
    tone: "neutral" as const,
  };
  const emergency = alert.squawk ? EMERGENCY_SQUAWKS[alert.squawk] : undefined;
  const route =
    alert.origin_iata || alert.destination_iata
      ? `${alert.origin_iata ?? "?"} to ${alert.destination_iata ?? "?"}`
      : null;
  // Non-ICAO addresses (TIS-B, prefixed with ~) cannot be looked up on the map.
  const trackable = alert.hex && !alert.hex.startsWith("~");

  return (
    <Card as="li">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-mono text-lg font-semibold">{title}</h2>
            <Badge tone={badge.tone}>{badge.label}</Badge>
            {emergency && (
              <Badge tone="alarm">
                Squawk {alert.squawk} ({emergency})
              </Badge>
            )}
          </div>
          {identity.length > 0 && <p className="text-fg-muted">{identity.join(" · ")}</p>}
        </div>
        <time dateTime={alert.seen_at} className="text-sm text-fg-subtle tabular-nums">
          {formatDateTime(alert.seen_at)}
        </time>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Detail label="Altitude" value={formatAltitude(alert.altitude_ft, prefs.altitudeUnit)} />
        <Detail label="Speed" value={formatSpeed(alert.ground_speed_kts, prefs.speedUnit)} />
        {alert.squawk && !emergency && <Detail label="Squawk" value={alert.squawk} />}
        {route && <Detail label="Route" value={route} />}
        <Detail label="Source" value={providerLabel(alert.provider)} />
      </dl>

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 border-t border-line pt-3 text-sm text-fg-subtle">
        <span>
          Filter:{" "}
          {alert.filter_id === null ? (
            `${alert.filter_name} (deleted)`
          ) : (
            <Link to={`/filters/${String(alert.filter_id)}`} className={linkClass}>
              {alert.filter_name}
            </Link>
          )}
        </span>
        {trackable && (
          <ExternalLink
            href={`https://globe.adsb.lol/?icao=${encodeURIComponent(alert.hex ?? "")}`}
          >
            Track on globe.adsb.lol
          </ExternalLink>
        )}
      </div>
      {alert.notification_status === "failed" && alert.notification_error && (
        <p className="mt-2 text-sm text-danger-text">{alert.notification_error}</p>
      )}
    </Card>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-fg-subtle">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}
