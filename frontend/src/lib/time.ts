// Date and duration formatting. The API sends ISO 8601 timestamps in UTC; the UI shows local time.

const DATE_TIME = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  return DATE_TIME.format(new Date(iso));
}

/** "45 s", "12 min", "3 h 5 min", "2 d 4 h". */
export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${String(s)} s`;
  const minutes = Math.floor(s / 60);
  if (minutes < 60) return `${String(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const rest = minutes % 60;
    return rest ? `${String(hours)} h ${String(rest)} min` : `${String(hours)} h`;
  }
  const days = Math.floor(hours / 24);
  const rest = hours % 24;
  return rest ? `${String(days)} d ${String(rest)} h` : `${String(days)} d`;
}

/** "just now", "5 min ago", "in 2 min". */
export function formatRelative(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "-";
  const diff = (new Date(iso).getTime() - now.getTime()) / 1000;
  if (Math.abs(diff) < 10) return "just now";
  return diff > 0 ? `in ${formatDuration(diff)}` : `${formatDuration(-diff)} ago`;
}
