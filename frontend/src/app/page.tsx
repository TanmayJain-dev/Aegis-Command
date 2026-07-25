"use client";

import React, { useState, useEffect, useRef } from "react";
import { Shield, Target, AlertTriangle, Search, Activity, Terminal } from "lucide-react";

export default function AegisDashboard() {
  const [query, setQuery] = useState("");
  const [intelData, setIntelData] = useState<any>(null);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [detections, setDetections] = useState<any>({});
  const [duration, setDuration] = useState(0);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // 1. Load the pre-processed YOLO JSON on mount
  useEffect(() => {
    fetch("/detections.json")
      .then((res) => res.json())
      .then((data) => setDetections(data))
      .catch((err) => console.error("Error loading detections:", err));
  }, []);

  // 2. Sync Video timestamp with Canvas drawing
  // 2. Sync Video timestamp with Canvas drawing
  const handleTimeUpdate = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    
    // SAFETY CHECK 1: Ensure DOM elements and detections exist
    if (!video || !canvas || !detections || Object.keys(detections).length === 0) return;
    
    // SAFETY CHECK 2: Ensure video metadata is loaded to prevent divide-by-zero
    if (video.videoWidth === 0 || video.videoHeight === 0) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Match canvas size to video rendering size
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;

    // Clear previous drawings
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calculate scaling factors
    const scaleX = canvas.width / video.videoWidth;
    const scaleY = canvas.height / video.videoHeight;

    const currentTime = video.currentTime;
    
    // Find the closest timestamp in our JSON
    const closestTime = Object.keys(detections).reduce((prev, curr) => {
      return Math.abs(parseFloat(curr) - currentTime) < Math.abs(parseFloat(prev) - currentTime)
        ? curr
        : prev;
    }, Object.keys(detections)[0]); // Default to the first actual key instead of "0"

    // If the closest time is within 0.5 seconds, draw the box
    if (Math.abs(parseFloat(closestTime) - currentTime) < 0.5) {
      const activeThreats = detections[closestTime];
      
      // SAFETY CHECK 3: Ensure activeThreats is actually an array before looping
      if (activeThreats && Array.isArray(activeThreats)) {
        activeThreats.forEach((threat: any) => {
          const [x1, y1, x2, y2] = threat.box;
          
          // Scale coordinates
          const scaledX = x1 * scaleX;
          const scaledY = y1 * scaleY;
          const scaledWidth = (x2 - x1) * scaleX;
          const scaledHeight = (y2 - y1) * scaleY;

          // Draw Box
          ctx.strokeStyle = "#ef4444"; // red-500
          ctx.lineWidth = 3;
          ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

          // Draw Text Background
          ctx.fillStyle = "#ef4444";
          ctx.fillRect(scaledX, scaledY - 20, 80, 20);

          // Draw Text
          ctx.fillStyle = "#ffffff";
          ctx.font = "12px monospace";
          ctx.fillText(`${threat.class.toUpperCase()} ${threat.confidence}`, scaledX + 5, scaledY - 6);

          // Auto-Trigger UI Feature
          if (threat.class === "truck" && !intelData && !loading) {
            setQuery("truck");
            handleSearch("truck");
          }
        });
      }
    }
  };
  // 4. Capture total video length when it loads
  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  // 5. Allow clicking the timeline to jump to a threat
  const seekToTime = (timeStr: string) => {
    if (videoRef.current) {
      videoRef.current.currentTime = parseFloat(timeStr);
      videoRef.current.play();
    }
  };
  // 3. Search RAG Backend API
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
      if (data.status === "success") {
        setIntelData(data.data[0]);
        setAiSummary(data.ai_summary || "AI processing unavailable.");
      }
    } catch (error) {
      console.error("Search failed:", error);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-mono flex flex-col overflow-hidden">
      {/* HEADER */}
      <header className="border-b border-emerald-900/30 bg-slate-900/50 p-4 flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <Shield className="text-emerald-500" size={24} />
          <h1 className="text-xl font-bold tracking-widest text-emerald-50">AEGIS COMMAND <span className="text-emerald-500/50">//</span> <span className="text-sm font-normal text-slate-400">THREAT INTEL NETWORK</span></h1>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <span className="flex items-center gap-2"><Activity className="text-emerald-400" size={14}/> SYSTEM SECURE</span>
          <span className="text-slate-500">OP-SECTOR: OMEGA</span>
        </div>
      </header>

      {/* MAIN DASHBOARD */}
      <main className="flex-1 grid grid-cols-12 gap-4 p-4 min-h-0">
        
        {/* LEFT PANE: VISION RECON (65% width) */}
        <section className="col-span-8 flex flex-col gap-2 relative border border-slate-800 bg-slate-900/20 rounded-lg p-2">
          <div className="flex items-center justify-between text-xs text-slate-400 px-2 uppercase tracking-wider">
            <span className="flex items-center gap-2"><Target size={14} className="text-red-400"/> Live Reconnaissance</span>
            <span>UAV Feed: Active</span>
          </div>
          
          <div className="relative flex-1 w-full rounded overflow-hidden bg-black border border-slate-800/50">
            {/* HTML5 Native Video */}
            <video 
              ref={videoRef}
              src="/drone_feed.mp4" 
              className="absolute inset-0 w-full h-full object-contain"
              controls
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
            />
            {/* Canvas overlay for drawing AI Boxes */}
            <canvas 
              ref={canvasRef}
              className="absolute inset-0 pointer-events-none"
            />
            {/* Aesthetic Crosshair Overlay */}
            <div className="absolute inset-0 pointer-events-none border-[1px] border-emerald-500/10 flex justify-center items-center">
               <div className="w-16 h-16 border border-emerald-500/20 rounded-full flex justify-center items-center">
                  <div className="w-2 h-2 bg-emerald-500/30 rounded-full"></div>
               </div>
            </div>
          </div>

          {/* CUSTOM THREAT RADAR TIMELINE */}
          <div className="w-full h-6 bg-slate-900 border border-slate-700 rounded mt-1 relative flex items-center px-1">
            <span className="absolute left-2 text-[10px] text-slate-500 z-10 font-bold">THREAT RADAR</span>
            {duration > 0 && Object.keys(detections).map((time) => {
              // Only draw markers if there are actual threats at this timestamp
              if (detections[time].length > 0) {
                const leftPercentage = (parseFloat(time) / duration) * 100;
                return (
                  <div 
                    key={time}
                    onClick={() => seekToTime(time)}
                    className="absolute h-4 w-1.5 bg-red-500/80 hover:bg-red-400 cursor-pointer rounded-full z-20 transition-all hover:scale-150 hover:shadow-[0_0_8px_rgba(239,68,68,0.8)]"
                    style={{ left: `${leftPercentage}%` }}
                    title={`Threat detected at ${time}s`}
                  />
                );
              }
              return null;
            })}
          </div>
        </section>

        {/* RIGHT PANE: SIGNAL INTELLIGENCE (35% width) */}
        <section className="col-span-4 flex flex-col gap-4">
          
          {/* AI Commander Summary Box */}
          <div className="border border-emerald-900/50 bg-emerald-950/20 rounded-lg p-4 relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500"></div>
            <h2 className="text-emerald-400 text-xs font-bold tracking-widest uppercase mb-2 flex items-center gap-2">
              <Terminal size={14}/> Tactical AI Summary
            </h2>
            <p className="text-sm text-emerald-100/80 leading-relaxed">
              {aiSummary ? aiSummary : "Awaiting intel correlation. Scan communications to generate tactical overview."}
            </p>
          </div>

          {/* RAG Search Engine */}
          <div className="flex gap-2">
            <input 
              type="text" 
              placeholder="Query intercept database..." 
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
            />
            <button 
              onClick={() => handleSearch()}
              className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 px-4 py-2 rounded flex items-center justify-center font-bold transition-colors"
            >
              {loading ? <Activity className="animate-spin" size={18}/> : <Search size={18}/>}
            </button>
          </div>

          {/* Intel Results Feed */}
          <div className="flex-1 overflow-y-auto border border-slate-800 bg-slate-900/30 rounded-lg p-2 space-y-2 custom-scrollbar">
             {intelData ? (
                <div className="bg-slate-800/50 border border-slate-700 p-3 rounded text-sm relative group cursor-pointer hover:border-slate-500 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs text-slate-400 font-bold">{intelData.id}</span>
                    <span className="text-[10px] bg-red-950 text-red-400 border border-red-900 px-2 py-0.5 rounded flex items-center gap-1">
                      <AlertTriangle size={10}/> Threat Detected
                    </span>
                  </div>
                  <div className="text-slate-300 mb-2 leading-relaxed">"{intelData.transcript}"</div>
                  <div className="text-xs text-slate-500 uppercase tracking-widest pt-2 border-t border-slate-700/50">
                    Location Coord: {intelData.location}
                  </div>
                </div>
             ) : (
                <div className="h-full flex flex-col items-center justify-center text-slate-600 space-y-2 opacity-50">
                  <Shield size={32} className="mb-2"/>
                  <span className="text-xs uppercase tracking-widest">No Active Intel Selected</span>
                </div>
             )}
          </div>
        </section>

      </main>
    </div>
  );
}