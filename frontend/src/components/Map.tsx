"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix for missing marker icons in Leaflet with webpack/Next.js
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// A component to handle panning
function MapUpdater({ coordinates }: { coordinates: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (coordinates) {
      map.flyTo(coordinates, 13, { duration: 1.5 });
    }
  }, [coordinates, map]);
  return null;
}

export default function Map({ coordinates }: { coordinates: [number, number] | null }) {
  const defaultCenter: [number, number] = [28.6139, 77.2090];
  
  return (
    <div className="w-full h-full rounded border-none overflow-hidden relative">
      <MapContainer 
        center={defaultCenter} 
        zoom={4} 
        style={{ height: '100%', width: '100%', background: '#0a0a0a' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://carto.com/">Carto</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        {coordinates && (
          <Marker position={coordinates}>
            <Popup className="font-mono text-xs">
              <div className="bg-slate-900 text-emerald-400 p-1 font-mono">
                TARGET LOCATION CONFIRMED
              </div>
            </Popup>
          </Marker>
        )}
        <MapUpdater coordinates={coordinates} />
      </MapContainer>
      <div className="absolute top-2 left-2 z-[400] text-[10px] text-emerald-500/70 bg-black/80 px-2 py-1 rounded border border-emerald-500/20 backdrop-blur-sm pointer-events-none font-mono">
        SAT-LINK: SECURE // LAT: {coordinates ? coordinates[0].toFixed(4) : defaultCenter[0].toFixed(4)} LNG: {coordinates ? coordinates[1].toFixed(4) : defaultCenter[1].toFixed(4)}
      </div>
    </div>
  );
}
