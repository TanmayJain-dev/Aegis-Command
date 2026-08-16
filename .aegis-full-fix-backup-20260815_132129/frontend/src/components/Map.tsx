"use client";
import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete (L.Icon.Default.prototype as any)._getIconUrl;

const targetIcon = new L.DivIcon({
  className: 'custom-target-icon',
  html: `<div style="width: 24px; height: 24px; background-color: rgba(244, 63, 94, 0.8); border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 15px #f43f5e; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

function MapUpdater({ coordinates }: { coordinates: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (coordinates) { map.flyTo(coordinates, 14, { duration: 2.0, easeLinearity: 0.25 }); }
  }, [coordinates, map]);
  return null;
}

export default function Map({ coordinates }: { coordinates: [number, number] | null }) {
  const defaultCenter: [number, number] = [31.4520, 74.9250]; 
  return (
    <div className="w-full h-full rounded border-none overflow-hidden relative">
      <MapContainer key="aegis-main-map" center={defaultCenter} zoom={10} style={{ height: '100%', width: '100%', background: '#0a0a0a' }} zoomControl={false}>
        <TileLayer attribution='&copy; Carto' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        {coordinates && (
          <>
            <Marker position={coordinates} icon={targetIcon}>
              <Popup className="font-mono text-xs">
                <div className="bg-slate-900 text-rose-400 p-1 font-mono font-bold border border-rose-900/50">TARGET LOCK CONFIRMED</div>
              </Popup>
            </Marker>
            <Circle center={coordinates} pathOptions={{ color: '#f43f5e', fillColor: '#f43f5e', fillOpacity: 0.1, weight: 1 }} radius={1500} />
          </>
        )}
        <MapUpdater coordinates={coordinates} />
      </MapContainer>
      <div className="absolute top-2 left-2 z-[400] text-[10px] text-cyan-400/90 bg-black/80 px-2 py-1 rounded border border-cyan-500/30 backdrop-blur-sm pointer-events-none font-mono tracking-widest">
        SAT-LINK: SECURE // LAT: {coordinates ? coordinates[0].toFixed(4) : defaultCenter[0].toFixed(4)} LNG: {coordinates ? coordinates[1].toFixed(4) : defaultCenter[1].toFixed(4)}
      </div>
    </div>
  );
}
