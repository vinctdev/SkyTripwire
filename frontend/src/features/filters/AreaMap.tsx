// Map for picking the center of a filter area. Loaded lazily, Leaflet is only needed here.
import "leaflet/dist/leaflet.css";

import { latLng, type LatLngBoundsExpression, type LatLngExpression } from "leaflet";
import { Circle, CircleMarker, MapContainer, TileLayer, useMapEvents } from "react-leaflet";

const METERS_PER_NM = 1852;
const DEFAULT_CENTER: LatLngExpression = [50, 10];
const DEFAULT_ZOOM = 4;
// OSM tiles are light in both themes, so the light theme accent is used for the overlay.
const OVERLAY_COLOR = "#00737e";

export interface AreaMapProps {
  latitude: number | null;
  longitude: number | null;
  radiusNm: number | null;
  onPick: (latitude: number, longitude: number) => void;
}

function ClickToPick({ onPick }: { onPick: AreaMapProps["onPick"] }) {
  useMapEvents({
    click(event) {
      onPick(event.latlng.lat, event.latlng.lng);
    },
  });
  return null;
}

export function AreaMap({ latitude, longitude, radiusNm, onPick }: AreaMapProps) {
  const center = latitude !== null && longitude !== null ? latLng(latitude, longitude) : null;
  const radiusMeters = radiusNm !== null && radiusNm > 0 ? radiusNm * METERS_PER_NM : null;
  // Initial view only: afterwards the user pans and zooms freely.
  const bounds: LatLngBoundsExpression | undefined =
    center && radiusMeters ? center.toBounds(radiusMeters * 2.2) : undefined;

  return (
    <div className="isolate h-96 overflow-hidden rounded-lg border border-line-strong">
      <MapContainer
        className="h-full w-full"
        {...(bounds
          ? { bounds }
          : { center: center ?? DEFAULT_CENTER, zoom: center ? 8 : DEFAULT_ZOOM })}
        worldCopyJump
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxZoom={19}
        />
        <ClickToPick onPick={onPick} />
        {center && radiusMeters && (
          <Circle
            center={center}
            radius={radiusMeters}
            pathOptions={{ color: OVERLAY_COLOR, weight: 2, fillOpacity: 0.12 }}
          />
        )}
        {center && (
          <CircleMarker
            center={center}
            radius={6}
            pathOptions={{ color: OVERLAY_COLOR, fillColor: OVERLAY_COLOR, fillOpacity: 1 }}
          />
        )}
      </MapContainer>
    </div>
  );
}
