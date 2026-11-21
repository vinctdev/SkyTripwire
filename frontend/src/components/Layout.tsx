import { NavLink, Outlet } from "react-router";

import { useHealth } from "../api/queries";
import { usePreferences } from "../settings/preferences";
import { UNIT_LABELS, type AltitudeUnit, type SpeedUnit } from "../settings/units";

const NAV_ITEMS = [
  { to: "/filters", label: "Filters" },
  { to: "/channels", label: "Channels" },
  { to: "/alerts", label: "Alerts" },
  { to: "/status", label: "Status" },
] as const;

const controlClass =
  "rounded-md border border-line-strong bg-surface px-2.5 py-1.5 text-sm text-fg hover:bg-surface-muted";

export function Layout() {
  return (
    <div className="flex min-h-dvh flex-col bg-canvas text-fg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 pt-4 pb-2 sm:px-6">
          <Wordmark />
          <PreferenceControls />
        </div>
        <nav aria-label="Main" className="mx-auto max-w-6xl overflow-x-auto px-2 sm:px-4">
          <ul className="flex gap-1">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  className={({ isActive }) =>
                    `block border-b-2 px-3 py-2.5 font-medium whitespace-nowrap transition-colors ${
                      isActive
                        ? "border-accent text-fg"
                        : "border-transparent text-fg-subtle hover:border-line-strong hover:text-fg"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}

/** Product name with the logo: an aircraft sending out a signal (same artwork as the favicon). */
function Wordmark() {
  return (
    <span className="flex items-center gap-2.5 text-2xl font-bold tracking-tight">
      <svg
        aria-hidden="true"
        viewBox="0 0 32 32"
        className="size-9 shrink-0 text-accent"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
      >
        <path
          d="M23 10.5A8 8 0 0 1 23 21.5M9 10.5A8 8 0 0 0 9 21.5M26.5 7A12.5 12.5 0 0 1 26.5 25M5.5 7A12.5 12.5 0 0 0 5.5 25"
          strokeWidth="2.25"
        />
        <path
          d="M0 -6.5C.8 -6.5 1 -5.5 1 -4.5V-1.2L6.5 2V3.4L1 1.8V4.6L2.8 5.9V6.9L0 6.2-2.8 6.9V5.9L-1 4.6V1.8L-6.5 3.4V2L-1 -1.2V-4.5C-1 -5.5-.8 -6.5 0 -6.5Z"
          transform="translate(16 16) scale(1.05)"
          fill="currentColor"
          stroke="none"
        />
      </svg>
      SkyTripwire
    </span>
  );
}

function PreferenceControls() {
  const prefs = usePreferences();
  return (
    <div className="flex items-center gap-2">
      <label className="sr-only" htmlFor="altitude-unit">
        Altitude unit
      </label>
      <select
        id="altitude-unit"
        className={controlClass}
        value={prefs.altitudeUnit}
        onChange={(e) => {
          prefs.setAltitudeUnit(e.target.value as AltitudeUnit);
        }}
      >
        <option value="ft">{UNIT_LABELS.ft}</option>
        <option value="m">{UNIT_LABELS.m}</option>
      </select>
      <label className="sr-only" htmlFor="speed-unit">
        Speed unit
      </label>
      <select
        id="speed-unit"
        className={controlClass}
        value={prefs.speedUnit}
        onChange={(e) => {
          prefs.setSpeedUnit(e.target.value as SpeedUnit);
        }}
      >
        <option value="kts">{UNIT_LABELS.kts}</option>
        <option value="kmh">{UNIT_LABELS.kmh}</option>
      </select>
      <button
        type="button"
        className={controlClass}
        onClick={() => {
          prefs.setTheme(prefs.theme === "dark" ? "light" : "dark");
        }}
      >
        {prefs.theme === "dark" ? "Light mode" : "Dark mode"}
      </button>
    </div>
  );
}

function Footer() {
  const health = useHealth();
  return (
    <footer className="border-t border-line px-4 py-4 text-center text-sm text-fg-subtle">
      SkyTripwire {health.data ? `v${health.data.version}` : ""}
      {health.isError && <span className="text-danger-text"> (backend unreachable)</span>}
      {" · "}
      <a className="underline underline-offset-2 hover:text-fg" href="/third-party-licenses.txt">
        Third-party licenses
      </a>
    </footer>
  );
}
