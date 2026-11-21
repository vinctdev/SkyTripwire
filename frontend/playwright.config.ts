import { defineConfig, devices } from "@playwright/test";

// End-to-end tests against the production build served by the real backend, with a fresh
// database, the polling worker off and no external requests (see e2e/fixtures.ts).
// Run `npm run e2e` (builds first). The backend's Python defaults to its local venv.
// With SKYTRIPWIRE_E2E_BASE_URL the tests run against an already running instance instead
// (CI: the Docker image). It must use a fresh database and have the worker disabled.
const PORT = 8765;
const python = process.env.SKYTRIPWIRE_PYTHON ?? "../backend/.venv/bin/python";
const externalBaseUrl = process.env.SKYTRIPWIRE_E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  // One backend and one database for all tests: run them one after another.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: externalBaseUrl ?? `http://127.0.0.1:${String(PORT)}`,
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: externalBaseUrl
    ? undefined
    : {
        command: `rm -rf e2e/.data && ${python} -m skytripwire`,
        url: `http://127.0.0.1:${String(PORT)}/api/health`,
        reuseExistingServer: false,
        timeout: 30_000,
        env: {
          SKYTRIPWIRE_PORT: String(PORT),
          SKYTRIPWIRE_DATA_DIR: "e2e/.data",
          SKYTRIPWIRE_FRONTEND_DIR: "dist",
          SKYTRIPWIRE_WORKER_ENABLED: "false",
          SKYTRIPWIRE_LOG_LEVEL: "warning",
        },
      },
});
