// Per-browser UI preferences. Storage can be unavailable (private mode, blocked site data),
// so every access is guarded and falls back to the default.

const PREFIX = "skytripwire.";

export function readPref<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = window.localStorage.getItem(PREFIX + key);
    return allowed.find((option) => option === value) ?? fallback;
  } catch {
    return fallback;
  }
}

export function writePref(key: string, value: string): void {
  try {
    window.localStorage.setItem(PREFIX + key, value);
  } catch {
    // Not persisted, the choice still applies until the page is reloaded.
  }
}
