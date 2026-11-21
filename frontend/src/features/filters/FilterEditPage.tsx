import { lazy, Suspense, useState, type ReactNode, type SubmitEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { FR24_NOTICE } from "../../api/labels";
import {
  useChannels,
  useConfig,
  useCreateFilter,
  useFilter,
  useUpdateFilter,
  type AppConfig,
  type FilterItem,
} from "../../api/queries";
import { PageHeader } from "../../components/PageHeader";
import {
  Button,
  buttonClass,
  Checkbox,
  Field,
  linkClass,
  Loading,
  Notice,
  Select,
  TextInput,
} from "../../components/ui";
import { usePreferences } from "../../settings/preferences";
import { distanceFromNm, distanceToNm, distanceUnitFor, UNIT_LABELS } from "../../settings/units";
import {
  DEFAULT_RADIUS_NM,
  filterToForm,
  MAX_RADIUS_NM,
  MAX_RADIUS_NM_FR24,
  parseNumber,
  validateFilterForm,
  worldwideIsSearchable,
  type FilterFormField,
  type FilterFormState,
  type FilterUnits,
  type Military,
} from "./filterForm";

type TextField = {
  [K in keyof FilterFormState]: FilterFormState[K] extends string ? K : never;
}[keyof FilterFormState];

const AreaMap = lazy(() => import("./AreaMap").then((m) => ({ default: m.AreaMap })));

export function NewFilterPage() {
  return <FilterPage title="Add filter" />;
}

export function EditFilterPage() {
  const id = Number(useParams().filterId);
  const filter = useFilter(id);
  return (
    <FilterPage title="Edit filter" loading={filter.isPending} error={filter.error?.message}>
      {filter.data}
    </FilterPage>
  );
}

function FilterPage({
  title,
  loading = false,
  error,
  children: filter,
}: {
  title: string;
  loading?: boolean;
  error?: string | undefined;
  children?: FilterItem | undefined;
}) {
  const config = useConfig();
  return (
    <>
      <PageHeader title={title} />
      {(loading || config.isPending) && <Loading />}
      {error && <Notice tone="error">{error}</Notice>}
      {config.isError && <Notice tone="error">{config.error.message}</Notice>}
      {config.data && !loading && !error && (
        <FilterEditor key={filter?.id ?? "new"} filter={filter} config={config.data} />
      )}
    </>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="min-w-0 rounded-xl border border-line bg-surface p-5 shadow-xs">
      <legend className="float-left mb-4 w-full text-lg font-semibold">{title}</legend>
      <div className="clear-both space-y-5">{children}</div>
    </fieldset>
  );
}

const WILDCARD_HINT =
  "Separate values with commas or spaces. Wildcards: * (any) and ? (one character).";

function FilterEditor({ filter, config }: { filter: FilterItem | undefined; config: AppConfig }) {
  const navigate = useNavigate();
  const prefs = usePreferences();
  const channels = useChannels();
  const create = useCreateFilter();
  const update = useUpdateFilter();
  const save = filter ? update : create;

  // Units are fixed while the form is open, so typed values keep their meaning.
  const [units] = useState<FilterUnits>(() => ({
    altitude: prefs.altitudeUnit,
    speed: prefs.speedUnit,
    distance: distanceUnitFor(prefs.speedUnit),
  }));
  const [initial] = useState(() => filterToForm(filter, units));
  const [state, setState] = useState(initial);
  const [submitted, setSubmitted] = useState(false);

  const fr24 = config.fr24_enabled;
  const { errors, body } = validateFilterForm(state, {
    units,
    fr24Enabled: fr24,
    ...(filter ? { original: { filter, form: initial } } : {}),
  });
  const maxRadius = distanceFromNm(fr24 ? MAX_RADIUS_NM_FR24 : MAX_RADIUS_NM, units.distance);
  const showRoute =
    fr24 || state.originAirports.trim() !== "" || state.destinationAirports.trim() !== "";

  function set<K extends keyof FilterFormState>(key: K, value: FilterFormState[K]) {
    setState((current) => ({ ...current, [key]: value }));
  }

  function errorFor(field: FilterFormField): string | undefined {
    return submitted ? errors[field] : undefined;
  }

  function onPick(latitude: number, longitude: number) {
    setState((current) => ({
      ...current,
      latitude: latitude.toFixed(4),
      // Leaflet allows panning across the date line, the API expects -180 to 180.
      longitude: (((((longitude + 180) % 360) + 360) % 360) - 180).toFixed(4),
      radius:
        current.radius.trim() === ""
          ? String(distanceFromNm(DEFAULT_RADIUS_NM, units.distance))
          : current.radius,
    }));
  }

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (!body) return;
    const done = { onSuccess: () => void navigate("/filters") };
    if (filter) update.mutate({ id: filter.id, body }, done);
    else create.mutate(body, done);
  }

  // Range fields share one error (e.g. "altitude"), shown below the "from" input.
  const RANGE_ERRORS: Partial<Record<TextField, FilterFormField>> = {
    altitudeMin: "altitude",
    altitudeMax: "altitude",
    speedMin: "speed",
    speedMax: "speed",
  };
  const text = (field: TextField, extra: object = {}) => ({
    id: `filter-${field}`,
    value: state[field],
    "aria-invalid": errorFor(RANGE_ERRORS[field] ?? (field as FilterFormField)) !== undefined,
    onChange: (e: { target: { value: string } }) => {
      set(field, e.target.value);
    },
    ...extra,
  });

  const mapLatitude = parseNumber(state.latitude);
  const mapLongitude = parseNumber(state.longitude);
  const mapRadius = parseNumber(state.radius);

  return (
    <form noValidate onSubmit={onSubmit} className="max-w-3xl space-y-6">
      <Section title="General">
        <Field id="filter-name" label="Name" error={errorFor("name")}>
          <TextInput {...text("name", { maxLength: 100, placeholder: "e.g. Heavies near FRA" })} />
        </Field>
        <Checkbox
          id="filter-enabled"
          label="Enabled"
          checked={state.enabled}
          onChange={(checked) => {
            set("enabled", checked);
          }}
        />
        <div className="space-y-2">
          <p className="text-sm font-semibold">Notify via</p>
          {channels.isError && <Notice tone="error">{channels.error.message}</Notice>}
          {channels.data?.length === 0 && (
            <Notice>
              No channels yet. Matches are still listed under Alerts.{" "}
              <Link to="/channels/new" className={linkClass}>
                Add a channel
              </Link>
            </Notice>
          )}
          {channels.data?.map((channel) => (
            <Checkbox
              key={channel.id}
              id={`filter-channel-${String(channel.id)}`}
              label={channel.enabled ? channel.name : `${channel.name} (disabled)`}
              checked={state.channelIds.includes(channel.id)}
              onChange={(checked) => {
                set(
                  "channelIds",
                  checked
                    ? [...state.channelIds, channel.id]
                    : state.channelIds.filter((id) => id !== channel.id),
                );
              }}
            />
          ))}
        </div>
        <Field
          id="filter-cooldownMinutes"
          label="Cooldown (minutes)"
          hint="Minimum time between two alerts for the same aircraft. 0 alerts on every sighting."
          error={errorFor("cooldownMinutes")}
        >
          <TextInput {...text("cooldownMinutes", { inputMode: "numeric" })} />
        </Field>
      </Section>

      <Section title="Area">
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(
            [
              [false, "Around a point"],
              [true, "Worldwide"],
            ] as const
          ).map(([worldwide, label]) => (
            <label key={label} className="flex items-center gap-2.5">
              <input
                type="radio"
                name="filter-area-mode"
                className="size-4 accent-accent"
                checked={state.worldwide === worldwide}
                onChange={() => {
                  set("worldwide", worldwide);
                }}
              />
              {label}
            </label>
          ))}
        </div>
        {state.worldwide ? (
          <Notice tone={worldwideIsSearchable(state, fr24) ? "info" : "error"}>
            A worldwide filter needs at least one exact registration, callsign, type or squawk
            {fr24 ? ", an airline" : ""} or &quot;Only military&quot;. Wildcards alone are not
            enough, the data sources cannot search for them.
          </Notice>
        ) : (
          <>
            <p className="text-fg-muted">Click on the map to set the center.</p>
            <Suspense
              fallback={
                <div className="h-96 rounded-lg border border-line-strong bg-surface-muted" />
              }
            >
              <AreaMap
                latitude={Number.isNaN(mapLatitude) ? null : mapLatitude}
                longitude={Number.isNaN(mapLongitude) ? null : mapLongitude}
                radiusNm={
                  mapRadius === null || Number.isNaN(mapRadius)
                    ? null
                    : distanceToNm(mapRadius, units.distance)
                }
                onPick={onPick}
              />
            </Suspense>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="filter-latitude" label="Latitude" error={errorFor("latitude")}>
                <TextInput
                  {...text("latitude", { inputMode: "decimal", placeholder: "50.0379" })}
                />
              </Field>
              <Field id="filter-longitude" label="Longitude" error={errorFor("longitude")}>
                <TextInput
                  {...text("longitude", { inputMode: "decimal", placeholder: "8.5622" })}
                />
              </Field>
              <Field
                id="filter-radius"
                label={`Radius (${units.distance})`}
                hint={`Up to ${String(maxRadius)} ${units.distance}.`}
                error={errorFor("radius")}
              >
                <TextInput {...text("radius", { inputMode: "decimal" })} />
              </Field>
            </div>
          </>
        )}
      </Section>

      <Section title="Aircraft">
        <p className="text-sm text-fg-subtle">
          All set criteria must match. Within one field, any of the values matches. {WILDCARD_HINT}
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="filter-typeCodes" label="Aircraft types (ICAO)" error={errorFor("typeCodes")}>
            <TextInput {...text("typeCodes", { placeholder: "B744, A388, A35*" })} />
          </Field>
          <Field id="filter-registrations" label="Registrations" error={errorFor("registrations")}>
            <TextInput {...text("registrations", { placeholder: "D-ABYA, D-AI*" })} />
          </Field>
          <Field id="filter-callsigns" label="Callsigns" error={errorFor("callsigns")}>
            <TextInput {...text("callsigns", { placeholder: "DLH400, CFG*" })} />
          </Field>
          <Field
            id="filter-airlines"
            label="Airlines (ICAO)"
            hint="Matched by the callsign prefix, e.g. DLH for Lufthansa."
            error={errorFor("airlines")}
          >
            <TextInput {...text("airlines", { placeholder: "DLH, BAW" })} />
          </Field>
        </div>
        <Field id="filter-military" label="Military">
          <Select
            id="filter-military"
            value={state.military}
            onChange={(e) => {
              set("military", e.target.value as Military);
            }}
          >
            <option value="any">Any</option>
            <option value="only">Only military</option>
            <option value="exclude">Exclude military</option>
          </Select>
        </Field>
        <div className="space-y-2">
          <p className="text-sm font-semibold">Categories</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {config.categories.map((category) => (
              <Checkbox
                key={category.code}
                id={`filter-category-${category.code}`}
                label={category.label}
                checked={state.categories.includes(category.code)}
                onChange={(checked) => {
                  set(
                    "categories",
                    checked
                      ? [...state.categories, category.code]
                      : state.categories.filter((c) => c !== category.code),
                  );
                }}
              />
            ))}
          </div>
        </div>
      </Section>

      <Section title="Flight">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            id="filter-altitudeMin"
            label={`Altitude from (${UNIT_LABELS[units.altitude]})`}
            error={errorFor("altitude")}
          >
            <TextInput {...text("altitudeMin", { inputMode: "numeric" })} />
          </Field>
          <Field id="filter-altitudeMax" label={`Altitude to (${UNIT_LABELS[units.altitude]})`}>
            <TextInput {...text("altitudeMax", { inputMode: "numeric" })} />
          </Field>
          <Field
            id="filter-speedMin"
            label={`Ground speed from (${UNIT_LABELS[units.speed]})`}
            error={errorFor("speed")}
          >
            <TextInput {...text("speedMin", { inputMode: "numeric" })} />
          </Field>
          <Field id="filter-speedMax" label={`Ground speed to (${UNIT_LABELS[units.speed]})`}>
            <TextInput {...text("speedMax", { inputMode: "numeric" })} />
          </Field>
          <Field
            id="filter-squawks"
            label="Squawk codes"
            hint="E.g. 7700 (emergency), 7600 (radio failure), 7500 (hijack)."
            error={errorFor("squawks")}
          >
            <TextInput {...text("squawks", { placeholder: "7700", inputMode: "numeric" })} />
          </Field>
        </div>
        <Checkbox
          id="filter-emergencyOnly"
          label="Only emergencies (ADS-B emergency or squawk 7500, 7600, 7700)"
          checked={state.emergencyOnly}
          onChange={(checked) => {
            set("emergencyOnly", checked);
          }}
        />
        <Checkbox
          id="filter-includeOnGround"
          label="Include aircraft on the ground"
          checked={state.includeOnGround}
          onChange={(checked) => {
            set("includeOnGround", checked);
          }}
        />
      </Section>

      {showRoute && (
        <Section title="Route (FR24 only)">
          {fr24 ? (
            <p className="text-sm text-fg-muted">{FR24_NOTICE}</p>
          ) : (
            <Notice tone="error">
              The FR24 source is disabled, so route criteria cannot be checked. Remove them or
              enable FR24.
            </Notice>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              id="filter-originAirports"
              label="From airports (IATA)"
              error={errorFor("originAirports")}
            >
              <TextInput {...text("originAirports", { placeholder: "FRA, MUC" })} />
            </Field>
            <Field
              id="filter-destinationAirports"
              label="To airports (IATA)"
              error={errorFor("destinationAirports")}
            >
              <TextInput {...text("destinationAirports", { placeholder: "JFK" })} />
            </Field>
          </div>
        </Section>
      )}

      {submitted && !body && <Notice tone="error">Please fix the marked fields.</Notice>}
      {save.isError && <Notice tone="error">{save.error.message}</Notice>}

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary" disabled={save.isPending}>
          {save.isPending ? "Saving..." : "Save"}
        </Button>
        <Link to="/filters" className={buttonClass("ghost")}>
          Cancel
        </Link>
      </div>
    </form>
  );
}
