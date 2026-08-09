"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { Shield, Target, AlertTriangle, Search, Activity, Terminal, Video, Radio, Globe, Map as MapIcon, X, CheckCircle, Crosshair, ChevronRight, Play, Pause, Volume2, VolumeX, Maximize, Minimize } from "lucide-react";
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
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true); 
  const [isFullscreen, setIsFullscreen] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/detections.json")
      .then((res) => res.json())
      .then((data) => setDetections(data))
      .catch((err) => console.error("Error loading detections:", err));
  }, []);

  const detectionKeys = useMemo(() => {
    if (!detections) return [];
    return Object.keys(detections).sort((a, b) => parseFloat(a) - parseFloat(b));
  }, [detections]);

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    if (!video || !canvas || !detections || detectionKeys.length === 0) return;
    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / video.videoWidth;
    const scaleY = canvas.height / video.videoHeight;
    const currentTime = video.currentTime;
    
    let left = 0;
    let right = detectionKeys.length - 1;
    let closestKey = detectionKeys[0];
    let minDiff = Infinity;

    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      const midTime = parseFloat(detectionKeys[mid]);
      const diff = Math.abs(midTime - currentTime);

      if (diff < minDiff) {
        minDiff = diff;
        closestKey = detectionKeys[mid];
      }

      if (midTime === currentTime) {
        break; 
      } else if (midTime < currentTime) {
        left = mid + 1;
      } else {
        right = mid - 1;
      }
    }

    if (minDiff < 0.5) {
      const activeThreats = detections[closestKey];
      
      if (activeThreats && Array.isArray(activeThreats)) {
        activeThreats.forEach((threat: any) => {
          const [x1, y1, x2, y2] = threat.box;
          
          const scaledX = x1 * scaleX;
          const scaledY = y1 * scaleY;
          const scaledWidth = (x2 - x1) * scaleX;
          const scaledHeight = (y2 - y1) * scaleY;

          // PITCH DECK UI: Cyan targeting boxes
          ctx.strokeStyle = "#06b6d4"; // cyan-500
          ctx.lineWidth = 2;
          ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

          ctx.beginPath(); ctx.moveTo(scaledX, scaledY + 10); ctx.lineTo(scaledX, scaledY); ctx.lineTo(scaledX + 10, scaledY); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(scaledX + scaledWidth - 10, scaledY); ctx.lineTo(scaledX + scaledWidth, scaledY); ctx.lineTo(scaledX + scaledWidth, scaledY + 10); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(scaledX, scaledY + scaledHeight - 10); ctx.lineTo(scaledX, scaledY + scaledHeight); ctx.lineTo(scaledX + 10, scaledY + scaledHeight); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(scaledX + scaledWidth - 10, scaledY + scaledHeight); ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight); ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight - 10); ctx.stroke();

          ctx.fillStyle = "rgba(6, 182, 212, 0.15)";
          ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);

          const hasTrackingInfo = threat.id && threat.direction && threat.direction !== "-";
          const labelHeight = hasTrackingInfo ? 34 : 20;

          ctx.fillStyle = "#06b6d4";
          ctx.fillRect(scaledX, scaledY - labelHeight, 140, labelHeight);

          ctx.fillStyle = "#0a0a0a"; // Dark text on cyan background
          ctx.font = "bold 10px monospace";
          ctx.fillText(`[${threat.class.toUpperCase()}] ${(threat.confidence * 100).toFixed(1)}%`, scaledX + 4, scaledY - (hasTrackingInfo ? 20 : 6));

          if (hasTrackingInfo) {
            ctx.fillText(`${threat.id} · ${threat.direction} · ${threat.speed_kmh}km/h`, scaledX + 4, scaledY - 6);
          }

          if (threat.class === "truck" && !intelData && !loading) {
            setQuery("truck");
            handleSearch("truck");
          }
        });
      }
    }
  };

  const seekToTime = (timeStr: string) => {
    if (videoRef.current) {
      videoRef.current.currentTime = parseFloat(timeStr);
      const playPromise = videoRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch((error) => console.log("Auto-play interrupted by user interaction."));
      }
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        const playPromise = videoRef.current.play();
        if (playPromise !== undefined) {
          playPromise.catch((error) => console.log("Play interrupted by user interaction."));
        }
        setIsPlaying(true);
      }
    }
  };

  const toggleMute = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      videoContainerRef.current?.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable full-screen mode: ${err.message}`);
      });
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const handleSearch = async (searchQuery: string = query) => {
    if (!searchQuery) return;
    setLoading(true);
    try {
      const res = await fetch("/api/intel/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });
      const data = await res.json();
      
      if (data.status === "success" && data.data && data.data.length > 0) {
        setIntelData(data.data[0]); 
        setAiSummary(data.ai_summary || "AI processing unavailable.");
        const targetLat = data.data[0].lat;
        const targetLng = data.data[0].lng;
        setMapCoordinates([targetLat, targetLng]);
      } else {
        setIntelData(null);
        setAiSummary("No relevant intel found for this query.");
        setMapCoordinates(null);
      }
    } catch (error) {
      console.error("Search failed:", error);
      setIntelData(null);
      setAiSummary("CONNECTION ERROR: Unable to reach Intelligence Database (Port 8000).");
      setMapCoordinates(null);
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
        <div className="relative bg-slate-950 border border-fuchsia-900/50 rounded shadow-[0_0_50px_rgba(217,70,239,0.15)] w-full max-w-2xl overflow-hidden flex flex-col">
          <div className="bg-fuchsia-950/40 border-b border-fuchsia-900/50 p-4 flex justify-between items-center">
            <h2 className="text-fuchsia-400 font-bold tracking-widest flex items-center gap-2 text-sm">
              <AlertTriangle size={18} /> ACTION REQUIRED: INTEL #{intelData?.id || "UNKNOWN"}
            </h2>
            <button onClick={() => setIsModalOpen(false)} className="text-slate-500 hover:text-white transition-colors">
              <X size={20} />
            </button>
          </div>
          
          <div className="p-6 flex flex-col gap-6 text-sm">
            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">AI Tactical Summary</div>
              <div className="bg-slate-900/50 border border-slate-800 p-4 rounded text-fuchsia-300 leading-relaxed font-mono">
                {aiSummary}
              </div>
            </div>

            <div>
              <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">Raw Transcript / Data</div>
              <div className="bg-black/50 border border-slate-800 p-4 rounded text-slate-300 font-mono text-xs max-h-32 overflow-y-auto custom-scrollbar">
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
              className="px-6 py-2 bg-rose-950 border border-rose-900 text-rose-400 hover:bg-rose-900 hover:text-rose-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(244,63,94,0.2)]"
            >
              INITIATE LOCKDOWN
            </button>
            <button 
              onClick={() => setIsModalOpen(false)}
              className="px-6 py-2 bg-cyan-950 border border-cyan-900 text-cyan-400 hover:bg-cyan-900 hover:text-cyan-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(6,182,212,0.2)]"
            >
              DEPLOY ASSETS
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-mono flex flex-col overflow-hidden select-none">
      {/* PITCH DECK HEADER */}
      <header className="bg-[#0a0a0a] p-4 flex justify-between items-center z-10 relative border-b border-slate-800/50">
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-cyan-500 via-fuchsia-500 to-rose-500"></div>
        <div className="flex items-center gap-4">
          <div className="relative flex items-center justify-center w-10 h-10 border border-cyan-500/30 rounded bg-cyan-950/20">
            <Shield className="text-cyan-400" size={20} />
            <div className="absolute inset-0 animate-ping opacity-20 border border-cyan-500 rounded"></div>
          </div>
          <div className="flex flex-col">
            <h1 className="text-xl font-bold tracking-widest text-white leading-none">AEGIS COMMAND</h1>
            <span className="text-[10px] text-cyan-400 font-bold tracking-[0.2em] mt-1">UNIFIED THREAT INTELLIGENCE</span>
          </div>
        </div>
        <div className="flex items-center gap-6 text-xs border border-slate-800 bg-slate-900/50 px-4 py-2 rounded">
          <span className="flex items-center gap-2 text-slate-400">
            <Activity className="text-cyan-400" size={14} /> 
            SYS: <span className="text-cyan-400 font-bold">SECURE</span>
          </span>
          <span className="w-[1px] h-4 bg-slate-700"></span>
          <span className="text-slate-400 flex items-center gap-2">
            <Globe size={14} className="text-fuchsia-400"/>
            OP-SEC: <span className="text-fuchsia-400 font-bold">OMEGA</span>
          </span>
        </div>
      </header>

      {/* MAIN DASHBOARD */}
      <main className="flex-1 grid grid-cols-12 gap-6 p-6 min-h-0">
        
        {/* LEFT PANE: OPTICS HUD (VISION PATH - CYAN THEME) */}
        <section className="col-span-7 flex flex-col gap-4 relative">
          
          <div className="flex items-center gap-2 text-xs">
            {(["UAV-ALPHA", "PERIMETER CCTV-04", "MOBILE INFANTRY BODYCAM"] as VideoSource[]).map((src) => (
              <button
                key={src}
                onClick={() => setVideoSource(src)}
                className={`px-4 py-2 border rounded flex items-center gap-2 transition-all ${
                  videoSource === src 
                    ? "bg-cyan-950/40 border-cyan-500/50 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.1)]" 
                    : "bg-slate-900/30 border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-300"
                }`}
              >
                <Video size={14} />
                {src}
              </button>
            ))}
          </div>

          <div 
            ref={videoContainerRef} 
            className="relative flex-1 w-full rounded border border-cyan-900/50 bg-black overflow-hidden group shadow-2xl"
          >
            <div className="absolute inset-0 z-10 pointer-events-none flex flex-col justify-between p-4">
               <div className="flex justify-between items-start text-[10px] text-cyan-400 font-bold tracking-widest drop-shadow-[0_0_8px_rgba(0,0,0,0.9)]">
                 <div className="flex flex-col gap-1 bg-black/40 p-2 rounded backdrop-blur-sm border border-cyan-500/20">
                   <span>REC <span className={isPlaying ? "text-rose-500 animate-pulse drop-shadow-[0_0_5px_rgba(244,63,94,0.8)]" : "text-slate-500"}>●</span></span>
                   <span>T-MINUS: 00:00:00</span>
                   <span>FPS: 59.94</span>
                 </div>
                 <div className="flex flex-col items-end gap-1 text-right bg-black/40 p-2 rounded backdrop-blur-sm border border-cyan-500/20">
                   <span>FEED ENCRYPTION: AES-256</span>
                   <span>SRC: {videoSource}</span>
                   <span>STATUS: <span className="text-cyan-400 drop-shadow-[0_0_5px_rgba(6,182,212,0.8)]">LIVE</span></span>
                 </div>
               </div>

               <div className="absolute inset-0 flex items-center justify-center">
                  <Crosshair className="text-cyan-400/40 w-32 h-32 stroke-1 drop-shadow-[0_0_8px_rgba(6,182,212,0.4)]" />
               </div>
               
               <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]"></div>
               <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]"></div>
               <div className="absolute bottom-12 left-4 w-8 h-8 border-b-2 border-l-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]"></div>
               <div className="absolute bottom-12 right-4 w-8 h-8 border-b-2 border-r-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]"></div>
            </div>

            <video 
              ref={videoRef}
              src="/drone_feed.mp4" 
              className="absolute inset-0 w-full h-full object-contain filter contrast-125 brightness-90 grayscale-[20%]"
              onTimeUpdate={() => {
                handleTimeUpdate();
                if (videoRef.current && duration === 0) {
                  setDuration(videoRef.current.duration);
                }
              }}
              onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
              onDurationChange={(e) => setDuration(e.currentTarget.duration)}
              onCanPlay={(e) => setDuration(e.currentTarget.duration)}
              muted={isMuted}
              onClick={togglePlay}
            />
            
            <canvas 
              ref={canvasRef}
              className="absolute inset-0 pointer-events-none z-20"
            />

            <div className="absolute bottom-0 w-full h-12 bg-gradient-to-t from-black/90 to-transparent z-30 flex items-end px-4 pb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
              <div className="flex items-center justify-between w-full text-cyan-400/80">
                <div className="flex items-center gap-4">
                  <button onClick={togglePlay} className="hover:text-cyan-300 transition-colors">
                    {isPlaying ? <Pause size={18} /> : <Play size={18} fill="currentColor" />}
                  </button>
                  <button onClick={toggleMute} className="hover:text-cyan-300 transition-colors">
                    {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
                  </button>
                </div>
                <div className="flex items-center gap-1">
                   <div className="w-1 h-3 bg-cyan-500/40 animate-pulse"></div>
                   <div className="w-1 h-2 bg-cyan-500/40 animate-pulse delay-75"></div>
                   <div className="w-1 h-4 bg-cyan-500/40 animate-pulse delay-150"></div>
                   <div className="w-1 h-2 bg-cyan-500/40 animate-pulse delay-75"></div>
                </div>
                <button onClick={toggleFullscreen} className="hover:text-cyan-300 transition-colors z-40">
                  {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
                </button>
              </div>
            </div>
          </div>

          {/* Threat Radar */}
          <div className="w-full h-8 bg-slate-900 border border-slate-700 relative flex items-center px-1 overflow-hidden shadow-inner rounded">
            <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-20 pointer-events-none"></div>
            <span className="absolute left-3 text-[10px] text-cyan-400 z-10 font-bold tracking-widest flex items-center gap-2">
              <Target size={12}/> THREAT RADAR
            </span>
            {duration > 0 && detections && Object.keys(detections).map((timeKey) => {
              const threats = detections[timeKey];
              if (threats && threats.length > 0) {
                const leftPercentage = (parseFloat(timeKey) / duration) * 100;
                if (leftPercentage >= 0 && leftPercentage <= 100) {
                  return (
                    <div 
                      key={timeKey}
                      onClick={() => seekToTime(timeKey)}
                      className="absolute h-full w-0.5 bg-rose-500 hover:w-1.5 hover:bg-rose-400 cursor-pointer z-20 transition-all shadow-[0_0_10px_rgba(244,63,94,0.8)]"
                      style={{ left: `${leftPercentage}%` }}
                      title={`Threat at ${timeKey}s`}
                    />
                  );
                }
              }
              return null;
            })}
          </div>
        </section>

        {/* RIGHT PANE: GEO & INTEL (INTELLIGENCE PATH - FUCHSIA/ROSE THEME) */}
        <section className="col-span-5 flex flex-col gap-6">
          
          {/* Top Half: Geospatial Map */}
          <div className="h-[40%] min-h-[250px] relative flex flex-col bg-slate-900/20 border border-slate-800 rounded p-1">
             <div className="flex items-center gap-2 text-xs text-fuchsia-400 font-bold p-2 uppercase tracking-wider bg-slate-900/50">
                <MapIcon size={14} className="text-fuchsia-400"/> Tactical Map
             </div>
             <div className="flex-1 relative bg-black border-t border-slate-800">
               <MapComponent coordinates={mapCoordinates} />
             </div>
          </div>

          {/* Bottom Half: Intelligence Stream */}
          <div className="flex-1 flex flex-col gap-4 border border-fuchsia-900/30 bg-slate-900/20 p-4 rounded relative shadow-inner">
            
            <div className="flex justify-between items-center border-b border-slate-800 pb-4">
              <div className="text-xs uppercase tracking-widest text-fuchsia-400 font-bold flex items-center gap-2">
                <Terminal size={14} /> Intel Feed
              </div>
              <div className="flex bg-black border border-slate-700 rounded p-1">
                <button 
                  onClick={() => setIntelMode("SIGINT")}
                  className={`px-4 py-1 rounded text-[10px] font-bold tracking-widest transition-colors ${intelMode === "SIGINT" ? "bg-fuchsia-950/50 text-fuchsia-400" : "text-slate-500 hover:text-slate-300"}`}
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
                  <Search className="absolute left-3 top-3 text-fuchsia-500/50" size={16} />
                  <input 
                    type="text" 
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                    placeholder="QUERY SIGINT DATABASE..."
                    className="w-full rounded bg-black border border-slate-700 text-fuchsia-400 text-sm py-2.5 pl-10 pr-4 outline-none focus:border-fuchsia-500 focus:ring-1 focus:ring-fuchsia-500/50 placeholder-slate-600 transition-all font-mono shadow-inner"
                  />
                  {loading && (
                    <div className="absolute right-3 top-3">
                      <Activity className="animate-spin text-fuchsia-500" size={16} />
                    </div>
                  )}
                </div>

                {intelData ? (
                  <div 
                    onClick={handleIntelClick}
                    className="mt-2 bg-slate-950 border border-fuchsia-900/50 hover:border-fuchsia-500/50 p-4 rounded cursor-pointer transition-all group hover:bg-slate-900/80 shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="text-rose-500" size={16}/>
                        <span className="text-xs font-bold text-rose-500 tracking-widest">INTEL MATCH DETECTED</span>
                      </div>
                      <span className="text-[10px] text-fuchsia-500/70 font-bold">ID: {intelData.id}</span>
                    </div>
                    
                    <p className="text-slate-300 text-sm leading-relaxed border-l-2 border-fuchsia-500/50 pl-3">
                      "{intelData.transcript}"
                    </p>
                    
                    <div className="mt-4 pt-3 border-t border-slate-800 flex justify-between items-center text-xs">
                       <span className="text-slate-500 flex items-center gap-1">
                         <MapIcon size={12} className="text-fuchsia-500/50" /> {intelData.location}
                       </span>
                       <span className="text-fuchsia-500/70 group-hover:text-fuchsia-400 flex items-center gap-1 transition-colors font-bold">
                         VIEW TACTICAL SUMMARY <ChevronRight size={14} />
                       </span>
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-slate-600 border border-dashed border-slate-800 rounded bg-black/20 gap-3">
                    <Radio size={32} className="opacity-50" />
                    <span className="text-xs uppercase tracking-widest text-center px-4 leading-relaxed">
                      {aiSummary || "Awaiting Query Input"}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex-1 flex flex-col bg-black border border-slate-800 rounded overflow-hidden">
                <div className="p-2 border-b border-slate-800 flex items-center gap-2 text-[10px] text-blue-400 bg-blue-950/20">
                  <Activity size={12} className="animate-pulse" /> LIVE CHATTER ANALYSIS
                </div>
                <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
                  {[
                    { src: "Telegram / Unknown", time: "2m ago", text: "Movement spotted near Sector 4 checkpoints. Prepare the cargo.", threat: "HIGH" },
                    { src: "DarkWeb Forum", time: "15m ago", text: "Looking for blindspots in perimeter CCTV-04.", threat: "MED" },
                    { src: "Twitter / Open", time: "1h ago", text: "Loud noises heard coming from the northern ridge.", threat: "LOW" }
                  ].map((item, i) => (
                    <div key={i} className="border-l-2 border-blue-500/50 pl-3 pb-4 border-b border-slate-800/50 last:border-b-0">
                       <div className="flex justify-between items-center mb-1">
                         <span className="text-[10px] text-slate-500">{item.src} // {item.time}</span>
                         <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-black border ${item.threat === 'HIGH' ? 'text-rose-400 border-rose-900/50' : item.threat === 'MED' ? 'text-yellow-400 border-yellow-900/50' : 'text-slate-400 border-slate-700'}`}>
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