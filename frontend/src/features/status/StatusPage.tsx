import type { ReactNode } from "react";
import { Link } from "react-router";

import { FR24_NOTICE, providerLabel } from "../../api/labels";
import { useStatus, type ProviderStatus, type Status } from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import { Card as Panel, linkClass, Loading, Notice } from "../../components/ui";
import { formatDateTime, formatDuration, formatRelative } from "../../lib/time";
import { BudgetMeter } from "./BudgetMeter";

export function StatusPage() {
  const status = useStatus();
  return (
    <>
      <PageHeader title="Status" />
      {status.isPending && <Loading />}
      {status.isError && <Notice tone="error">{status.error.message}</Notice>}
      {status.data && <StatusView status={status.data} />}
    </>
  );
}

function Card({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <Panel as="section" className="space-y-4">
      <h2 className="text-lg font-semibold">{title}</h2>
      {children}
    </Panel>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-sm text-fg-subtle">{label}</dt>
      <dd className="font-medium tabular-nums">{children}</dd>
    </div>
  );
}

function plural(count: number, noun: string): string {
  return `${String(count)} ${noun}${count === 1 ? "" : "s"}`;
}

function StatusView({ status }: { status: Status }) {
  const { worker, providers, unplannable } = status;
  const issues = Object.entries(worker.provider_issues);

  return (
    <div className="space-y-5">
      <Card title="Polling">
        {!worker.enabled && (
          <Notice tone="error">
            The polling worker is disabled (SKYTRIPWIRE_WORKER_ENABLED=false). No aircraft are
            checked.
          </Notice>
        )}
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Item label="Last check">
            <span title={formatDateTime(worker.last_cycle_finished_at)}>
              {worker.last_cycle_finished_at
                ? formatRelative(worker.last_cycle_finished_at)
                : "Not yet"}
            </span>
          </Item>
          <Item label="Next check">
            <span title={formatDateTime(worker.next_cycle_at)}>
              {worker.next_cycle_at ? formatRelative(worker.next_cycle_at) : "-"}
            </span>
          </Item>
          <Item label="Interval">
            {worker.interval_seconds == null
              ? "-"
              : `every ${formatDuration(worker.interval_seconds)}`}
          </Item>
          <Item label="Last check found">
            {worker.last_aircraft_seen == null
              ? "-"
              : `${String(worker.last_aircraft_seen)} aircraft, ${plural(worker.last_new_alerts ?? 0, "new alert")}`}
          </Item>
        </dl>
        {worker.last_error && <Notice tone="error">Last check failed: {worker.last_error}</Notice>}
        {issues.length > 0 && (
          <Notice tone="error">
            <ul>
              {issues.map(([provider, issue]) => (
                <li key={provider}>
                  {providerLabel(provider)}: {issue}
                </li>
              ))}
            </ul>
          </Notice>
        )}
      </Card>

      {providers.map((provider) => (
        <ProviderCard
          key={provider.name}
          provider={provider}
          intervalSeconds={worker.interval_seconds}
        />
      ))}

      {unplannable.length > 0 && (
        <Card title="Filters that are not checked">
          <ul className="space-y-2">
            {unplannable.map((item) => (
              <li key={item.filter_id}>
                <Link to={`/filters/${String(item.filter_id)}`} className={linkClass}>
                  {item.filter_name}
                </Link>
                : {item.reason}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ProviderCard({
  provider,
  intervalSeconds,
}: {
  provider: ProviderStatus;
  intervalSeconds: number | null | undefined;
}) {
  const perDay =
    intervalSeconds && intervalSeconds > 0
      ? Math.round((provider.planned_requests_per_cycle * 86400) / intervalSeconds)
      : null;

  return (
    <Card title={`Data source: ${providerLabel(provider.name)}`}>
      {provider.name === "fr24" && <p className="text-sm text-fg-muted">{FR24_NOTICE}</p>}
      {provider.blocked_until && (
        <Notice tone="error">
          Paused until {formatDateTime(provider.blocked_until)} (
          {formatRelative(provider.blocked_until)}) after errors or rate limiting.
        </Notice>
      )}
      <div>
        <p className="mb-1.5 text-sm text-fg-subtle">Requests in the last 24 hours</p>
        <BudgetMeter
          used={provider.requests_in_window}
          budget={provider.daily_budget}
          label={`Request budget of ${providerLabel(provider.name)}`}
        />
      </div>
      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Item label="Requests per check">{String(provider.planned_requests_per_cycle)}</Item>
        <Item label="Expected per day">
          {perDay === null ? "-" : `about ${perDay.toLocaleString("en-US")}`}
        </Item>
        <Item label="Last success">
          <span title={formatDateTime(provider.last_success_at)}>
            {provider.last_success_at ? formatRelative(provider.last_success_at) : "Never"}
          </span>
        </Item>
        <Item label="Last error">
          <span title={formatDateTime(provider.last_error_at)}>
            {provider.last_error_at ? formatRelative(provider.last_error_at) : "None"}
          </span>
        </Item>
      </dl>
      {provider.last_error && (
        <p className="text-sm break-words text-fg-muted">
          Last error message: {provider.last_error}
        </p>
      )}
    </Card>
  );
}
