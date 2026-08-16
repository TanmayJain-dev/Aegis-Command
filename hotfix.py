import os
import re

# --- 1. OVERWRITE MAP.TSX ---
map_code = """"use client";
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
"""
with open('frontend/src/components/Map.tsx', 'w', encoding='utf-8') as f:
    f.write(map_code)

# --- 2. PATCH PAGE.TSX ---
with open('frontend/src/app/page.tsx', 'r', encoding='utf-8') as f:
    page = f.read()

# Remove Ugly JSON Box
page = re.sub(r'\{threatAssessment && \(\s*<div data-testid="threat-assessment".*?</div>\s*\)\}\s*\{renderModal\(\)\}', '{renderModal()}', page, flags=re.DOTALL)

# Add Audio Beep
page = page.replace(
    'console.log("[THREAT WS] THREAT_ASSESSED", data);',
    'console.log("[THREAT WS] THREAT_ASSESSED", data);\n          try { new Audio("data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU").play().catch(()=>console.log("Audio blocked")); } catch(e){}'
)

# Update Modal UI
modal_target = '''<div className="p-6 flex flex-col gap-6 text-sm">
            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">AI Tactical Summary</div>
              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded text-fuchsia-300 leading-relaxed font-mono">
                {aiSummary}
              </div>
            </div>'''
            
modal_replacement = '''<div className="p-6 flex flex-col gap-6 text-sm">
            {threatAssessment && (
              <div className="flex gap-4">
                <div className={`px-3 py-1 rounded border font-bold text-xs ${threatAssessment.threat_level === 'HIGH' || threatAssessment.threat_level === 'CRITICAL' ? 'bg-rose-950/50 border-rose-500 text-rose-400' : 'bg-yellow-950/50 border-yellow-500 text-yellow-400'}`}>
                  THREAT LEVEL: {threatAssessment.threat_level}
                </div>
                <div className="px-3 py-1 rounded border border-cyan-900/50 bg-cyan-950/30 text-cyan-400 font-bold text-xs flex items-center gap-2">
                  <Activity size={12}/> AI CONFIDENCE: {threatAssessment.score}%
                </div>
                <div className="px-3 py-1 rounded border border-fuchsia-900/50 bg-fuchsia-950/30 text-fuchsia-400 font-bold text-xs">
                  PRIOR INCIDENTS: {threatAssessment.previous_incidents || 0}
                </div>
              </div>
            )}
            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">AI Tactical Assessment</div>
              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded text-fuchsia-300 leading-relaxed font-mono">
                {threatAssessment ? threatAssessment.reasoning : aiSummary}
                {threatAssessment && (
                  <div className="mt-2 pt-2 border-t border-fuchsia-900/30 text-cyan-400">
                    <span className="text-slate-500">RECOMMENDED ACTION:</span> {threatAssessment.recommended_action}
                  </div>
                )}
              </div>
            </div>'''
page = page.replace(modal_target, modal_replacement)

with open('frontend/src/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(page)

print("[SUCCESS] All UI Hotfixes applied automatically!")
