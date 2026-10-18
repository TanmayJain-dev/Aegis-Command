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

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;

const targetIcon = new L.DivIcon({
  className: "tactical-target-icon",
  html: `
    <div style="
      position:relative;
      width:18px;
      height:18px;
      display:flex;
      align-items:center;
      justify-content:center;
    ">
      <div style="
        position:absolute;
        width:18px;
        height:18px;
        border-radius:50%;
        border:2px solid #ef4444;
        background-color:rgba(239,68,68,0.25);
      "></div>
      <div style="
        width:6px;
        height:6px;
        border-radius:50%;
        background-color:#ef4444;
      "></div>
    </div>
  `,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

function MapUpdater({
  coordinates,
}: {
  coordinates: [number, number] | null;
}) {
  const map = useMap();

  useEffect(() => {
    map.invalidateSize();
    const timer = setTimeout(() => {
      map.invalidateSize();
    }, 200);
    return () => clearTimeout(timer);
  }, [map]);

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
    <div className="relative z-0 h-full w-full min-h-[300px] overflow-hidden rounded bg-[#08111d] border border-[#243244]">
      <MapContainer
        key="aegis-main-map"
        center={defaultCenter}
        zoom={10}
        style={{
          height: "100%",
          minHeight: "300px",
          width: "100%",
          background: "#08111d",
        }}
        zoomControl={false}
      >
        <TileLayer attribution={attribution} url={mapUrl} />

        {coordinates && (
          <>
            <Marker position={coordinates} icon={targetIcon}>
              <Popup className="tactical-map-popup">
                <div className="bg-[#0d1724] text-[#f2f5f8] p-2 text-xs border border-[#243244] rounded">
                  <div className="text-[10px] text-[#ef4444] font-semibold uppercase tracking-wider mb-1">
                    Incident Sector
                  </div>
                  <div className="font-mono text-[11px] text-[#a7b2c2]">
                    {coordinates[0].toFixed(4)}° N, {coordinates[1].toFixed(4)}° E
                  </div>
                </div>
              </Popup>
            </Marker>

            <Circle
              center={coordinates}
              pathOptions={{
                color: "#ef4444",
                fillColor: "#ef4444",
                fillOpacity: 0.12,
                weight: 1.5,
                dashArray: "4 4",
              }}
              radius={1500}
            />
          </>
        )}

        <MapUpdater coordinates={coordinates} />
      </MapContainer>

      <div className="pointer-events-none absolute left-3 top-3 z-[401] rounded border border-[#243244] bg-[#0d1724]/90 px-2.5 py-1 text-[11px] font-mono text-[#f2f5f8] shadow-sm backdrop-blur-sm flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
        <span className="text-[#a7b2c2]">COORDINATES:</span>
        <span>
          {coordinates
            ? `${coordinates[0].toFixed(4)}° N  ${coordinates[1].toFixed(4)}° E`
            : `${defaultCenter[0].toFixed(4)}° N  ${defaultCenter[1].toFixed(4)}° E`}
        </span>
      </div>
    </div>
  );
}
