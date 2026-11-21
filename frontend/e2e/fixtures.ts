import { test as base, expect } from "@playwright/test";

// 1x1 transparent PNG, stands in for map tiles.
const EMPTY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

export interface BrowserErrors {
  /** Tolerates "Failed to load resource" console errors for this HTTP status (e.g. 422). */
  allowHttpStatus: (status: number) => void;
}

const FAILED_RESOURCE = /Failed to load resource: the server responded with a status of (\d+)/;

/**
 * Every test: requests leave only to the local backend (OSM tiles get an empty PNG), and
 * console errors or Content Security Policy violations fail the test.
 */
export const test = base.extend<{ browserErrors: BrowserErrors }>({
  browserErrors: [
    async ({ page, baseURL }, provide) => {
      const problems: string[] = [];
      const allowed = new Set<number>();
      await page.route(
        (url) => !url.href.startsWith(baseURL ?? "http://127.0.0.1"),
        (route) => route.fulfill({ contentType: "image/png", body: EMPTY_PNG }),
      );
      page.on("console", (message) => {
        if (message.type() === "error") problems.push(`console: ${message.text()}`);
      });
      page.on("pageerror", (error) => problems.push(`page error: ${error.message}`));
      await page.addInitScript(() => {
        document.addEventListener("securitypolicyviolation", (event) => {
          console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
        });
      });
      await provide({
        allowHttpStatus: (status) => {
          allowed.add(status);
        },
      });
      const unexpected = problems.filter((problem) => {
        const status = FAILED_RESOURCE.exec(problem)?.[1];
        return status === undefined || !allowed.has(Number(status));
      });
      expect(unexpected).toEqual([]);
    },
    { auto: true },
  ],
});

export { expect };

/** Unique names, the tests share one database. */
export function unique(prefix: string): string {
  return `${prefix} ${String(Date.now())}${String(Math.floor(Math.random() * 1000))}`;
}
