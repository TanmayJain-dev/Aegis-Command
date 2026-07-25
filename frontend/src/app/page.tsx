"use client";

import React, { useState, useEffect, useRef } from "react";
import { Shield, Target, AlertTriangle, Search, Activity, Terminal, Video, Radio, Globe, Map as MapIcon, X, CheckCircle, Crosshair, ChevronRight } from "lucide-react";
import dynamic from "next/dynamic";

const MapComponent = dynamic(() => import("../components/Map"), { ssr: false });

type VideoSource = "UAV-ALPHA" | "PERIMETER CCTV-04" | "MOBILE INFANTRY BODYCAM";
type IntelMode = "SIGINT" | "OSINT";

export default function AegisDashboard() {
  const [query, setQuery] = useState("");
  const [intelData, setIntelData] = useState<any>(null);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [detections, setDetections] = useState<any>({});
  const [duration, setDuration] = useState(0);

  const [videoSource, setVideoSource] = useState<VideoSource>("UAV-ALPHA");
  const [intelMode, setIntelMode] = useState<IntelMode>("SIGINT");
  const [mapCoordinates, setMapCoordinates] = useState<[number, number] | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    fetch("/detections.json")
      .then((res) => res.json())
      .then((data) => setDetections(data))
      .catch((err) => console.error("Error loading detections:", err));
  }, []);

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (!video || !canvas || !detections || Object.keys(detections).length === 0) return;
    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / video.videoWidth;
    const scaleY = canvas.height / video.videoHeight;
    const currentTime = video.currentTime;
    
    const closestTime = Object.keys(detections).reduce((prev, curr) => {
      return Math.abs(parseFloat(curr) - currentTime) < Math.abs(parseFloat(prev) - currentTime)
        ? curr
        : prev;
    }, Object.keys(detections)[0]);

    if (Math.abs(parseFloat(closestTime) - currentTime) < 0.5) {
      const activeThreats = detections[closestTime];
      
      if (activeThreats && Array.isArray(activeThreats)) {
        activeThreats.forEach((threat: any) => {
          const [x1, y1, x2, y2] = threat.box;
          
          const scaledX = x1 * scaleX;
          const scaledY = y1 * scaleY;
          const scaledWidth = (x2 - x1) * scaleX;
          const scaledHeight = (y2 - y1) * scaleY;

          ctx.strokeStyle = "#ef4444";
          ctx.lineWidth = 2;
          ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

          // Corner accents
          ctx.beginPath();
          ctx.moveTo(scaledX, scaledY + 10);
          ctx.lineTo(scaledX, scaledY);
          ctx.lineTo(scaledX + 10, scaledY);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(scaledX + scaledWidth - 10, scaledY);
          ctx.lineTo(scaledX + scaledWidth, scaledY);
          ctx.lineTo(scaledX + scaledWidth, scaledY + 10);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(scaledX, scaledY + scaledHeight - 10);
          ctx.lineTo(scaledX, scaledY + scaledHeight);
          ctx.lineTo(scaledX + 10, scaledY + scaledHeight);
          ctx.stroke();

          ctx.beginPath();
          ctx.moveTo(scaledX + scaledWidth - 10, scaledY + scaledHeight);
          ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight);
          ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight - 10);
          ctx.stroke();

          ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
          ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);

          ctx.fillStyle = "#ef4444";
          ctx.fillRect(scaledX, scaledY - 20, 100, 20);

          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 10px monospace";
          ctx.fillText(`[${threat.class.toUpperCase()}] ${(threat.confidence * 100).toFixed(1)}%`, scaledX + 4, scaledY - 6);

          if (threat.class === "truck" && !intelData && !loading) {
            setQuery("truck");
            handleSearch("truck");
          }
        });
      }
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const seekToTime = (timeStr: string) => {
    if (videoRef.current) {
      videoRef.current.currentTime = parseFloat(timeStr);
      videoRef.current.play();
    }
  };

  const handleSearch = async (searchQuery: string = query) => {
    if (!searchQuery) return;
    setLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/intel/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });
      const data = await res.json();
      if (data.status === "success" && data.data && data.data.length > 0) {
        setIntelData(data.data[0]);
        setAiSummary(data.ai_summary || "AI processing unavailable.");
        // Randomize coordinates for dummy map panning
        const randomLat = 28.6139 + (Math.random() - 0.5) * 0.1;
        const randomLng = 77.2090 + (Math.random() - 0.5) * 0.1;
        setMapCoordinates([randomLat, randomLng]);
      } else {
        // Fallback for demo
        setIntelData({ transcript: "Simulated response for: " + searchQuery, id: "DEMO-01", location: "Sector 7" });
        setAiSummary("Simulated AI summary based on RAG context.");
        setMapCoordinates([28.62, 77.21]);
      }
    } catch (error) {
      console.error("Search failed:", error);
      // Fallback data when backend isn't actually running
      setIntelData({ transcript: "Simulated fallback response for: " + searchQuery, id: "FALLBACK-01", location: "Sector X" });
      setAiSummary("Simulated AI summary due to backend connection failure.");
      setMapCoordinates([28.5, 77.1]);
    }
    setLoading(false);
  };

  const handleIntelClick = () => {
    if (intelData) {
      setIsModalOpen(true);
    }
  };

  const renderModal = () => {
    if (!isModalOpen) return null;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="absolute inset-0 bg-black/80 backdrop-blur-md" onClick={() => setIsModalOpen(false)}></div>
        <div className="relative bg-slate-950 border border-red-900/50 rounded shadow-[0_0_50px_rgba(220,38,38,0.15)] w-full max-w-2xl overflow-hidden flex flex-col">
          <div className="bg-red-950/40 border-b border-red-900/50 p-4 flex justify-between items-center">
            <h2 className="text-red-500 font-bold tracking-widest flex items-center gap-2 text-sm">
              <AlertTriangle size={18} /> ACTION REQUIRED: INTEL #{intelData?.id || "UNKNOWN"}
            </h2>
            <button onClick={() => setIsModalOpen(false)} className="text-slate-500 hover:text-white transition-colors">
              <X size={20} />
            </button>
          </div>
          
          <div className="p-6 flex flex-col gap-6 text-sm">
            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">AI Tactical Summary</div>
              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded text-emerald-400 leading-relaxed font-mono">
                {aiSummary}
              </div>
            </div>

            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">Raw Transcript / Data</div>
              <div className="bg-black/50 border border-slate-800 p-4 rounded text-slate-300 font-mono text-xs max-h-32 overflow-y-auto">
                {intelData?.transcript || "No transcript available."}
              </div>
            </div>
          </div>

          <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex justify-end gap-4">
            <button 
              onClick={() => setIsModalOpen(false)}
              className="px-6 py-2 border border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-white rounded transition-colors text-xs tracking-wider"
            >
              DISMISS
            </button>
            <button 
              onClick={() => setIsModalOpen(false)}
              className="px-6 py-2 bg-red-950 border border-red-900 text-red-400 hover:bg-red-900 hover:text-red-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(220,38,38,0.2)]"
            >
              INITIATE LOCKDOWN
            </button>
            <button 
              onClick={() => setIsModalOpen(false)}
              className="px-6 py-2 bg-emerald-950 border border-emerald-900 text-emerald-400 hover:bg-emerald-900 hover:text-emerald-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(16,185,129,0.2)]"
            >
              DEPLOY ASSETS
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-mono flex flex-col overflow-hidden select-none">
      {/* HEADER */}
      <header className="border-b border-emerald-900/30 bg-slate-950 p-4 flex justify-between items-center z-10 shadow-sm relative">
        <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent"></div>
        <div className="flex items-center gap-4">
          <div className="relative flex items-center justify-center w-10 h-10 border border-emerald-500/30 rounded bg-emerald-950/20">
            <Shield className="text-emerald-500" size={20} />
            <div className="absolute inset-0 animate-ping opacity-20 border border-emerald-500 rounded"></div>
          </div>
          <div className="flex flex-col">
            <h1 className="text-xl font-bold tracking-widest text-emerald-50 leading-none">AEGIS_COMMAND</h1>
            <span className="text-[10px] text-emerald-500/70 tracking-[0.2em] mt-1">THREAT INTEL NETWORK V3</span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs border border-slate-800 bg-slate-900/50 px-4 py-2 rounded">
          <span className="flex items-center gap-2 text-slate-400">
            <Activity className="text-emerald-400" size={14} /> 
            SYS: <span className="text-emerald-400 font-bold">SECURE</span>
          </span>
          <span className="w-[1px] h-4 bg-slate-700"></span>
          <span className="text-slate-400 flex items-center gap-2">
            <Globe size={14} className="text-blue-400"/>
            OP-SEC: <span className="text-blue-400 font-bold">OMEGA</span>
          </span>
        </div>
      </header>

      {/* MAIN DASHBOARD */}
      <main className="flex-1 grid grid-cols-12 gap-6 p-6 min-h-0">
        
        {/* LEFT PANE: OPTICS HUD (7 Columns) */}
        <section className="col-span-7 flex flex-col gap-4 relative">
          
          {/* Source Selector */}
          <div className="flex items-center gap-2 text-xs">
            {(["UAV-ALPHA", "PERIMETER CCTV-04", "MOBILE INFANTRY BODYCAM"] as VideoSource[]).map((src) => (
              <button
                key={src}
                onClick={() => setVideoSource(src)}
                className={`px-4 py-2 border rounded flex items-center gap-2 transition-all ${
                  videoSource === src 
                    ? "bg-emerald-950/40 border-emerald-500/50 text-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.1)]" 
                    : "bg-slate-900/30 border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-300"
                }`}
              >
                <Video size={14} />
                {src}
              </button>
            ))}
          </div>

          <div className="relative flex-1 w-full rounded border border-slate-800 bg-black overflow-hidden group shadow-2xl">
            {/* Universal Military Optics HUD */}
            <div className="absolute inset-0 z-10 pointer-events-none flex flex-col justify-between p-4">
               <div className="flex justify-between items-start text-[10px] text-emerald-500/70 font-bold tracking-widest drop-shadow-md">
                 <div className="flex flex-col gap-1">
                   <span>REC <span className="text-red-500 animate-pulse">●</span></span>
                   <span>T-MINUS: 00:00:00</span>
                   <span>FPS: 59.94</span>
                 </div>
                 <div className="flex flex-col items-end gap-1 text-right">
                   <span>FEED ENCRYPTION: AES-256</span>
                   <span>SRC: {videoSource}</span>
                   <span>STATUS: <span className="text-emerald-400">LIVE</span></span>
                 </div>
               </div>

               {/* Center Crosshair */}
               <div className="absolute inset-0 flex items-center justify-center">
                  <Crosshair className="text-emerald-500/20 w-32 h-32 stroke-[0.5]" />
               </div>
               
               {/* Corner Brackets */}
               <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-emerald-500/30"></div>
               <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-emerald-500/30"></div>
               <div className="absolute bottom-4 left-4 w-8 h-8 border-b-2 border-l-2 border-emerald-500/30"></div>
               <div className="absolute bottom-4 right-4 w-8 h-8 border-b-2 border-r-2 border-emerald-500/30"></div>

               <div className="flex justify-between items-end text-[10px] text-emerald-500/70 font-bold tracking-widest drop-shadow-md">
                 <div className="flex items-center gap-2">
                   <div className="w-24 h-1 bg-slate-800 overflow-hidden"><div className="w-2/3 h-full bg-emerald-500/50"></div></div>
                   <span>SIG STRENGTH</span>
                 </div>
                 <span>ZOOM: 1.0x</span>
               </div>
            </div>

            {/* Video Player */}
            <video 
              ref={videoRef}
              src="/drone_feed.mp4" 
              className="absolute inset-0 w-full h-full object-contain filter contrast-125 brightness-90 grayscale-[20%]"
              controls
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
              onCanPlay={(e) => setDuration(e.currentTarget.duration)}
            />
            {/* Canvas overlay for YOLO Boxes */}
            <canvas 
              ref={canvasRef}
              className="absolute inset-0 pointer-events-none z-20"
            />
          </div>

          {/* Threat Radar */}
          <div className="w-full h-8 bg-slate-900 border border-slate-700 relative flex items-center px-1 overflow-hidden shadow-inner rounded">
            <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-20 pointer-events-none"></div>
            <span className="absolute left-3 text-[10px] text-slate-400 z-10 font-bold tracking-widest flex items-center gap-2">
              <Target size={12}/> THREAT RADAR
            </span>
            {duration > 0 && detections && Object.entries(detections).map(([time, threats]: [string, any]) => {
              if (threats && threats.length > 0) {
                const leftPercentage = (parseFloat(time) / duration) * 100;
                // Only render if it's a valid percentage
                if (leftPercentage >= 0 && leftPercentage <= 100) {
                  return (
                    <div 
                      key={time}
                      onClick={() => seekToTime(time)}
                      className="absolute h-full w-0.5 bg-red-500 hover:w-1.5 hover:bg-red-400 cursor-pointer z-20 transition-all shadow-[0_0_10px_rgba(239,68,68,0.8)]"
                      style={{ left: `${leftPercentage}%` }}
                      title={`Threat at ${time}s`}
                    />
                  );
                }
              }
              return null;
            })}
          </div>
        </section>

        {/* RIGHT PANE: GEO & INTEL (5 Columns) */}
        <section className="col-span-5 flex flex-col gap-6">
          
          {/* Top Half: Geospatial Map */}
          <div className="h-[40%] min-h-[250px] relative flex flex-col bg-slate-900/20 border border-slate-800 rounded p-1">
             <div className="flex items-center gap-2 text-xs text-slate-400 p-2 uppercase tracking-wider bg-slate-900/50">
                <MapIcon size={14} className="text-blue-400"/> Tactical Map
             </div>
             <div className="flex-1 relative bg-black border-t border-slate-800">
               <MapComponent coordinates={mapCoordinates} />
             </div>
          </div>

          {/* Bottom Half: Intelligence Stream */}
          <div className="flex-1 flex flex-col gap-4 border border-slate-800 bg-slate-900/20 p-4 rounded relative shadow-inner">
            
            {/* Modal Toggle */}
            <div className="flex justify-between items-center border-b border-slate-800 pb-4">
              <div className="text-xs uppercase tracking-widest text-slate-400 flex items-center gap-2">
                <Terminal size={14} /> Intel Feed
              </div>
              <div className="flex bg-black border border-slate-700 rounded p-1">
                <button 
                  onClick={() => setIntelMode("SIGINT")}
                  className={`px-4 py-1 rounded text-[10px] font-bold tracking-widest transition-colors ${intelMode === "SIGINT" ? "bg-emerald-950/50 text-emerald-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  SIGINT / RAG
                </button>
                <button 
                  onClick={() => setIntelMode("OSINT")}
                  className={`px-4 py-1 rounded text-[10px] font-bold tracking-widest transition-colors ${intelMode === "OSINT" ? "bg-blue-950/50 text-blue-400" : "text-slate-500 hover:text-slate-300"}`}
                >
                  OSINT / WEB
                </button>
              </div>
            </div>

            {intelMode === "SIGINT" ? (
              <div className="flex flex-col gap-4 flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-3 text-emerald-500/50" size={16} />
                  <input 
                    type="text" 
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    placeholder="QUERY SIGINT DATABASE..."
                    className="w-full rounded bg-black border border-slate-700 text-emerald-400 text-sm py-2.5 pl-10 pr-4 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/50 placeholder-slate-600 transition-all font-mono shadow-inner"
                  />
                  {loading && (
                    <div className="absolute right-3 top-3">
                      <Activity className="animate-spin text-emerald-500" size={16} />
                    </div>
                  )}
                </div>

                {intelData ? (
                  <div 
                    onClick={handleIntelClick}
                    className="mt-2 bg-slate-950 border border-emerald-900/50 hover:border-emerald-500/50 p-4 rounded cursor-pointer transition-all group hover:bg-slate-900/80 shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="text-yellow-500" size={16}/>
                        <span className="text-xs font-bold text-yellow-500 tracking-widest">INTEL MATCH DETECTED</span>
                      </div>
                      <span className="text-[10px] text-slate-500">ID: {intelData.id}</span>
                    </div>
                    
                    <p className="text-slate-300 text-sm leading-relaxed border-l-2 border-emerald-500/30 pl-3">
                      "{intelData.transcript}"
                    </p>
                    
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-xs">
                       <span className="text-slate-500 flex items-center gap-1">
                         <MapIcon size={12} /> {intelData.location}
                       </span>
                       <span className="text-emerald-500/70 group-hover:text-emerald-400 flex items-center gap-1 transition-colors">
                         VIEW TACTICAL SUMMARY <ChevronRight size={14} />
                       </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-600 border border-dashed border-slate-800 rounded bg-black/20 gap-3">
                    <Radio size={32} className="opacity-50" />
                    <span className="text-xs uppercase tracking-widest">Awaiting Query Input</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex flex-col bg-black border border-slate-800 rounded overflow-hidden">
                <div className="p-2 border-b border-slate-800 flex items-center gap-2 text-[10px] text-blue-400 bg-blue-950/20">
                  <Activity size={12} className="animate-pulse" /> LIVE CHATTER ANALYSIS
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                  {[
                    { src: "Telegram / Unknown", time: "2m ago", text: "Movement spotted near Sector 4 checkpoints. Prepare the cargo.", threat: "HIGH" },
                    { src: "DarkWeb Forum", time: "15m ago", text: "Looking for blindspots in perimeter CCTV-04.", threat: "MED" },
                    { src: "Twitter / Open", time: "1h ago", text: "Loud noises heard coming from the northern ridge.", threat: "LOW" }
                  ].map((item, i) => (
                    <div key={i} className="border-l-2 border-blue-500/50 pl-3 pb-4 border-b border-slate-800/50 last:border-b-0">
                       <div className="flex justify-between items-center mb-1">
                         <span className="text-[10px] text-slate-500">{item.src} // {item.time}</span>
                         <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-black border ${item.threat === 'HIGH' ? 'text-red-400 border-red-900/50' : item.threat === 'MED' ? 'text-yellow-400 border-yellow-900/50' : 'text-slate-400 border-slate-700'}`}>
                           {item.threat}
                         </span>
                       </div>
                       <p className="text-xs text-slate-300 font-sans">{item.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

      </main>
      {renderModal()}
    </div>
  );
}
