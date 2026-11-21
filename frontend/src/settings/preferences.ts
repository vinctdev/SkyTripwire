import { createContext, useContext } from "react";

import { readPref } from "./storage";
import { ALTITUDE_UNITS, SPEED_UNITS, type AltitudeUnit, type SpeedUnit } from "./units";

export const THEMES = ["dark", "light"] as const;
export type Theme = (typeof THEMES)[number];

export interface Preferences {
  theme: Theme;
  altitudeUnit: AltitudeUnit;
  speedUnit: SpeedUnit;
}

export interface PreferencesContextValue extends Preferences {
  setTheme: (theme: Theme) => void;
  setAltitudeUnit: (unit: AltitudeUnit) => void;
  setSpeedUnit: (unit: SpeedUnit) => void;
}

/** Dark mode, feet and knots unless the user picked something else in this browser. */
export function loadPreferences(): Preferences {
  return {
    theme: readPref("theme", THEMES, "dark"),
    altitudeUnit: readPref("altitudeUnit", ALTITUDE_UNITS, "ft"),
    speedUnit: readPref("speedUnit", SPEED_UNITS, "kts"),
  };
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

export const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function usePreferences(): PreferencesContextValue {
  const value = useContext(PreferencesContext);
  if (value === null) throw new Error("usePreferences() needs a <PreferencesProvider>");
  return value;
}
