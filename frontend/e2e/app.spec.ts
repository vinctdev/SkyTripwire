import { expect, test, unique } from "./fixtures";

const TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw";

test("opens on the filters page with navigation, theme and units", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/filters$/);
  await expect(page.getByRole("heading", { name: "Filters" })).toBeVisible();
  await expect(page.getByText(/SkyTripwire v\d/)).toBeVisible();

  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("button", { name: "Light mode" }).click();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(page.locator("html")).not.toHaveClass(/dark/);

  await page.getByRole("link", { name: "Status" }).click();
  await expect(page.getByText("Data source: adsb.lol")).toBeVisible();
  await expect(page.getByText(/polling worker is disabled/)).toBeVisible();
});

test("client-side routes survive a reload (served by the backend)", async ({ page }) => {
  await page.goto("/channels/new");
  await expect(page.getByRole("heading", { name: "Add channel" })).toBeVisible();
  await page.goto("/does-not-exist");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
});

test("channel: test message fails cleanly, save, edit, delete", async ({ page }) => {
  const name = unique("Local hook");
  await page.goto("/channels/new");
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Type").selectOption("apprise");
  // Closed local port: the test message fails without leaving the machine.
  await page.getByLabel("Apprise URL").fill("json://127.0.0.1:9/");
  await page.getByRole("button", { name: "Send test message" }).click();
  await expect(page.getByText(/Test message failed/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("button", { name: "Save" }).click();
  const row = page.getByRole("listitem").filter({ hasText: name });
  await expect(row).toBeVisible();
  await expect(row.getByText("Not used by any filter")).toBeVisible();

  await row.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByText(/Leave the fields below empty/)).toBeVisible();
  await page.getByLabel("Enabled").uncheck();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(row.getByText("Disabled")).toBeVisible();

  await row.getByRole("button", { name: "Delete" }).click();
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(row).toHaveCount(0);
});

test("filter: pick an area on the map, save, see it, rejected worldwide edit", async ({
  page,
  browserErrors,
}) => {
  // The worldwide edit at the end is rejected by the backend on purpose.
  browserErrors.allowHttpStatus(422);
  const channel = unique("Phone");
  await page.goto("/channels/new");
  await page.getByLabel("Name").fill(channel);
  await page.getByLabel("Bot token").fill(TOKEN);
  await page.getByLabel("Chat ID").fill("987654321");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("heading", { name: "Channels" })).toBeVisible();

  const name = unique("Helicopters");
  await page.goto("/filters/new");
  await page.getByLabel("Name").fill(name);
  const map = page.locator(".leaflet-container");
  await expect(map).toBeVisible();
  await map.click();
  await expect(page.getByLabel("Latitude")).not.toHaveValue("");
  await expect(page.getByLabel("Radius (nm)")).toHaveValue("25");
  await expect(page.locator(".leaflet-container path.leaflet-interactive")).toHaveCount(2);
  await page.getByLabel("Radius (nm)").fill("40");
  await page.getByLabel("Rotorcraft (helicopter)").check();
  await page.getByLabel(channel).check();
  await page.getByRole("button", { name: "Save" }).click();

  const row = page.getByRole("listitem").filter({ hasText: name });
  await expect(row.getByText(/^Within 40 nm of /)).toBeVisible();
  await expect(row.getByText("Category: Rotorcraft (helicopter)")).toBeVisible();
  await expect(row.getByText("via adsb.lol")).toBeVisible();
  await expect(row.getByText(`Notifies: ${channel}`)).toBeVisible();

  // Reload the editor directly (SPA fallback) and try an unsearchable worldwide filter.
  await row.getByRole("link", { name: "Edit" }).click();
  await page.reload();
  await expect(page.getByLabel("Name")).toHaveValue(name);
  await page.getByLabel("Worldwide").check();
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText(/A worldwide filter needs exact registrations/)).toBeVisible();

  await page.getByRole("link", { name: "Cancel" }).click();
  await row.getByRole("link", { name: "Alerts" }).click();
  await expect(page).toHaveURL(/\/alerts\?filter=\d+$/);
  await expect(page.getByText(/No alerts yet/)).toBeVisible();
});

test("metric units are shown and stored values do not drift", async ({ page }) => {
  const name = unique("Metric");
  // Units are fixed while a form is open, so pick them before opening the editor.
  await page.goto("/filters");
  await page.getByLabel("Speed unit").selectOption("kmh");
  await page.getByLabel("Altitude unit").selectOption("m");
  await page.getByRole("link", { name: "Add filter" }).click();
  await page.getByLabel("Name").fill(name);
  await page.getByLabel("Worldwide").check();
  await page.getByLabel("Registrations").fill("D-ABYA");
  await page.getByLabel("Altitude to (m)").fill("3048");
  await page.getByLabel("Ground speed to (km/h)").fill("500");
  await page.getByRole("button", { name: "Save" }).click();

  const row = page.getByRole("listitem").filter({ hasText: name });
  await expect(row.getByText("Altitude at most 3,048 m")).toBeVisible();
  await expect(row.getByText("Ground speed at most 500 km/h")).toBeVisible();

  // Saving again without changes must not shift the stored values by rounding.
  await row.getByRole("link", { name: "Edit" }).click();
  await expect(page.getByLabel("Ground speed to (km/h)")).toHaveValue("500");
  await page.getByRole("button", { name: "Save" }).click();
  await page.getByLabel("Altitude unit").selectOption("ft");
  await page.getByLabel("Speed unit").selectOption("kts");
  await expect(row.getByText("Altitude at most 10,000 ft")).toBeVisible();
  await expect(row.getByText("Ground speed at most 270 kts")).toBeVisible();
});
