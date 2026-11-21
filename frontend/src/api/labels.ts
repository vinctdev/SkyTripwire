const PROVIDER_LABELS: Record<string, string> = {
  adsblol: "adsb.lol",
  fr24: "FR24 (unofficial)",
};

/** Terms for the optional FR24 source, shown wherever the UI uses or offers it. */
export const FR24_NOTICE =
  "FR24 is accessed through the unofficial FlightRadarAPI library, not an official API. " +
  "For personal and educational use only. For commercial use, contact Flightradar24.";

export function providerLabel(name: string): string {
  return PROVIDER_LABELS[name] ?? name;
}
