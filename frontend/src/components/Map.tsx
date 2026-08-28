"use client";

import React, { useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
  Circle,
} from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete (L.Icon.Default.prototype as any)._getIconUrl;

const targetIcon = new L.DivIcon({
  className: "custom-target-icon",
  html: `
    <div style="
      width:24px;
      height:24px;
      background-color:rgba(244,63,94,.8);
      border-radius:50%;
      border:2px solid #fff;
      box-shadow:0 0 15px #f43f5e;
      animation:ping 1.5s cubic-bezier(0,0,.2,1) infinite;
    "></div>
  `,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function MapUpdater({
  coordinates,
}: {
  coordinates: [number, number] | null;
}) {
  const map = useMap();

  const lastTarget = React.useRef<[number, number] | null>(null);
  const lastCameraUpdate = React.useRef(0);

  useEffect(() => {
    if (!coordinates) return;

    const now = Date.now();
    const previous = lastTarget.current;

    if (
      previous &&
      Math.abs(previous[0] - coordinates[0]) < 0.00008 &&
      Math.abs(previous[1] - coordinates[1]) < 0.00008
    ) {
      return;
    }

    if (now - lastCameraUpdate.current < 1500) {
      lastTarget.current = coordinates;
      return;
    }

    const currentZoom = map.getZoom();

    if (previous) {
      const latDelta = Math.abs(previous[0] - coordinates[0]);
      const lngDelta = Math.abs(previous[1] - coordinates[1]);

      if (latDelta < 0.00015 && lngDelta < 0.00015) {
        lastTarget.current = coordinates;
        return;
      }
    }

    lastTarget.current = coordinates;
    lastCameraUpdate.current = now;

    map.flyTo(coordinates, currentZoom, {
      duration: 0.9,
      easeLinearity: 0.35,
    });
  }, [coordinates, map]);

  return null;
}

export default function Map({
  coordinates,
}: {
  coordinates: [number, number] | null;
}) {
  const defaultCenter: [number, number] = [31.452, 74.925];

  const cartoApiKey = process.env.NEXT_PUBLIC_CARTO_API_KEY;

  const cartoUrl =
    "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" +
    (cartoApiKey ? `?key=${cartoApiKey}` : "");

  const mapUrl = cartoApiKey
    ? cartoUrl
    : "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

  const attribution = cartoApiKey
    ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>'
    : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

  return (
    <div className="relative z-0 h-full w-full overflow-hidden rounded border-none">
      <MapContainer
        key="aegis-main-map"
        center={defaultCenter}
        zoom={10}
        style={{
          height: "100%",
          width: "100%",
          background: "#0a0a0a",
        }}
        zoomControl={false}
      >
        <TileLayer attribution={attribution} url={mapUrl} />

        {coordinates && (
          <>
            <Marker position={coordinates} icon={targetIcon}>
              <Popup className="font-mono text-xs">
                <div className="bg-slate-900 p-1 font-mono font-bold text-rose-400 border border-rose-900/50">
                  TARGET LOCK CONFIRMED
                </div>
              </Popup>
            </Marker>

            <Circle
              center={coordinates}
              pathOptions={{
                color: "#f43f5e",
                fillColor: "#f43f5e",
                fillOpacity: 0.1,
                weight: 1,
              }}
              radius={1500}
            />
          </>
        )}

        <MapUpdater coordinates={coordinates} />
      </MapContainer>

      <div className="pointer-events-none absolute left-2 top-2 z-[401] rounded border border-cyan-500/30 bg-black/80 px-2 py-1 font-mono text-[10px] tracking-widest text-cyan-400/90 backdrop-blur-sm">
        SAT-LINK: SECURE // LAT:{" "}
        {coordinates
          ? coordinates[0].toFixed(4)
          : defaultCenter[0].toFixed(4)}{" "}
        LNG:{" "}
        {coordinates
          ? coordinates[1].toFixed(4)
          : defaultCenter[1].toFixed(4)}
      </div>
    </div>
  );
}
