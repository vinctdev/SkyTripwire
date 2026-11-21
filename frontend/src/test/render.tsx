// Test helpers: render the whole app at a path against a fake backend.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { App } from "../App";
import { PreferencesProvider } from "../settings/PreferencesProvider";

type Handler = (request: Request) => Response | Promise<Response>;

export interface RecordedRequest {
  method: string;
  path: string;
  url: string;
  body: unknown;
}

/**
 * Replaces `fetch` with a router over `"METHOD /path"` keys. Unknown routes answer 404.
 * `/api/health` is answered by default. Returns the list of received requests.
 */
export function fakeBackend(routes: Record<string, Handler | object>): RecordedRequest[] {
  const requests: RecordedRequest[] = [];
  const all: Record<string, Handler | object> = {
    "GET /api/health": { status: "ok", version: "1.2.3" },
    ...routes,
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      const path = new URL(request.url).pathname;
      const text = await request.text();
      requests.push({
        method: request.method,
        path,
        url: request.url,
        body: text ? JSON.parse(text) : undefined,
      });
      const route = all[`${request.method} ${path}`];
      if (route === undefined) return Response.json({ detail: "Not Found" }, { status: 404 });
      return typeof route === "function" ? (route as Handler)(request) : Response.json(route);
    }),
  );
  return requests;
}

export function renderApp(path = "/") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <PreferencesProvider initial={{ theme: "dark", altitudeUnit: "ft", speedUnit: "kts" }}>
        <MemoryRouter initialEntries={[path]}>
          <App />
        </MemoryRouter>
      </PreferencesProvider>
    </QueryClientProvider>,
  );
}
