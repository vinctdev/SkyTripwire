import { useEffect, useMemo, useState, type ReactNode } from "react";

import {
  applyTheme,
  loadPreferences,
  PreferencesContext,
  type Preferences,
  type PreferencesContextValue,
} from "./preferences";
import { writePref } from "./storage";

export function PreferencesProvider({
  children,
  initial,
}: {
  children: ReactNode;
  initial?: Preferences;
}) {
  const [prefs, setPrefs] = useState<Preferences>(() => initial ?? loadPreferences());

  useEffect(() => {
    applyTheme(prefs.theme);
  }, [prefs.theme]);

  const value = useMemo<PreferencesContextValue>(() => {
    const update = <K extends keyof Preferences>(key: K, next: Preferences[K]) => {
      writePref(key, next);
      setPrefs((current) => ({ ...current, [key]: next }));
    };
    return {
      ...prefs,
      setTheme: (theme) => {
        update("theme", theme);
      },
      setAltitudeUnit: (unit) => {
        update("altitudeUnit", unit);
      },
      setSpeedUnit: (unit) => {
        update("speedUnit", unit);
      },
    };
  }, [prefs]);

  return <PreferencesContext value={value}>{children}</PreferencesContext>;
}
