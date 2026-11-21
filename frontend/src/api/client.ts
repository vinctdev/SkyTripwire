import createClient from "openapi-fetch";

import type { paths } from "./schema";

// Same origin: the backend serves the UI in production, Vite proxies /api in development.
// The app is meant to run at the root of its (sub)domain, not under a path prefix.
// `fetch` is looked up per call (openapi-fetch would capture it at import), so tests can stub it.
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: (request) => globalThis.fetch(request),
});

/** Error response of the API. `detail` is FastAPI's error body (string or validation list). */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(errorMessage(status, detail));
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

interface ApiResult<T> {
  data?: T;
  error?: unknown;
  response: Response;
}

/** Returns the response body of a successful call, throws `ApiError` otherwise. */
export async function unwrap<T>(request: Promise<ApiResult<T>>): Promise<T> {
  const { data, error, response } = await request;
  if (!response.ok) throw new ApiError(response.status, error);
  return data as T;
}

/** Human readable message from FastAPI's `{"detail": ...}` error body. */
export function errorMessage(status: number, body: unknown): string {
  const detail = isRecord(body) ? body.detail : undefined;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (isRecord(item) && typeof item.msg === "string" ? item.msg : null))
      .filter((msg): msg is string => msg !== null);
    if (messages.length > 0) return messages.join("; ");
  }
  return `Request failed (HTTP ${String(status)})`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
