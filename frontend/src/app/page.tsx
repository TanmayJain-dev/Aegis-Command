"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { 
  Shield, 
  Target, 
  Radio, 
  Scan, 
  AlertTriangle, 
  Crosshair, 
  Activity, 
  Terminal
} from "lucide-react";

// --- API Contracts / Types ---
interface IntelData {
  id: string;
  score: number;
  location: string;
  transcript: string;
}

interface IntelResponse {
  status: string;
  data: IntelData[];
}

export default function AegisCommandDashboard() {
  // --- State ---
  const [time, setTime] = useState<string>("0000-00-00 00:00:00");
  const [query, setQuery] = useState<string>("");
  const [intelResults, setIntelResults] = useState<IntelData[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");
  const [autoThreatActive, setAutoThreatActive] = useState<boolean>(false);
  
  // Refs for tracking auto-trigger to prevent infinite polling loops
  const lastDetectedRef = useRef<string>("");

  // --- Clock logic ---
  useEffect(() => {
    // Mount clock to avoid hydration mismatch, formatted to look like military UTC
    const timer = setInterval(() => {
      const now = new Date();
      setTime(now.toISOString().replace("T", " ").substring(0, 19) + "Z");
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // --- RAG Intelligence Search (Port 8000) ---
  const handleSearch = useCallback(async (searchQuery: string) => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    setError("");
    
    try {
      const res = await fetch("http://localhost:8000/api/intel/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: searchQuery }),
      });
      
      if (!res.ok) throw new Error(`COMMS_LINK_FAIL: Status ${res.status}`);
      
      const data: IntelResponse = await res.json();
      if (data.status === "success") {
        setIntelResults(data.data);
      } else {
        throw new Error("MALFORMED_INTEL_PAYLOAD");
      }
    } catch (err: any) {
      setError(err.message || "UNKNOWN_NETWORK_ERROR");
    } finally {
      setLoading(false);
    }
  }, []);

  // --- Vision AI Polling (Port 8001) ---
  useEffect(() => {
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch("http://localhost:8001/api/vision/latest-detection");
        if (res.ok) {
          const data = await res.json();
          const currentDetection = data.detected?.toLowerCase() || "";
          
          // Auto-Threat Correlation Logic
          if (currentDetection === "truck" && lastDetectedRef.current !== "truck") {
            setAutoThreatActive(true);
            setQuery("truck"); // Update UI input field
            handleSearch("truck"); // Auto-trigger Search
            
            // Turn off the heavy visual alert after 8 seconds
            setTimeout(() => setAutoThreatActive(false), 8000);
          }
          
          lastDetectedRef.current = currentDetection;
        }
      } catch (err) {
        console.error("VISION_LINK_OFFLINE", err);
      }
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [handleSearch]);

  // --- Handlers ---
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  return (
    <div className="h-screen w-full bg-slate-950 text-slate-200 overflow-hidden flex flex-col font-mono selection:bg-emerald-500/30 selection:text-emerald-200">
      
      {/* HEADER */}
      <header className="h-16 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between px-6 shrink-0 shadow-[0_4px_30px_rgba(0,0,0,0.5)] z-10 relative">
        <div className="absolute inset-x-0 bottom-0 h-[1px] bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent"></div>
        <div className="flex items-center gap-3 text-emerald-400">
          <Shield className="w-6 h-6 animate-pulse" />
          <h1 className="text-xl font-bold tracking-[0.2em]">AEGIS COMMAND <span className="text-slate-500 font-light tracking-widest">// THREAT INTEL NETWORK</span></h1>
        </div>
        <div className="flex items-center gap-4 text-emerald-500 text-sm">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4" />
            <span>SYS.ONLINE</span>
          </div>
          <div className="px-3 py-1 bg-slate-900 border border-emerald-900 rounded-sm font-bold tracking-wider">
            {time}
          </div>
        </div>
      </header>

      {/* SPLIT PANE LAYOUT */}
      <main className="flex-1 flex overflow-hidden">
        
        {/* LEFT PANE: VISION RECON (60%) */}
        <div className="w-[60%] border-r border-slate-800 p-6 flex flex-col relative bg-slate-950/80">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 text-slate-400 uppercase tracking-widest text-sm font-semibold">
              <Target className="w-5 h-5 text-emerald-500" />
              <h2>Vision Reconnaissance</h2>
            </div>
            {autoThreatActive && (
              <span className="text-red-500 border border-red-500/50 bg-red-950/30 px-3 py-1 rounded-sm animate-pulse flex items-center gap-2 text-xs font-bold tracking-widest">
                <AlertTriangle className="w-4 h-4" /> 
                AUTO-THREAT CORRELATION ACTIVE
              </span>
            )}
          </div>

          {/* Drone Video / HUD Container */}
          <div className="flex-1 bg-black relative rounded-sm border border-slate-800 overflow-hidden shadow-inner">
            {/* Live Stream Img (Fallbacks to an empty black square if port 8001 is off) */}
            <img 
              src="http://localhost:8001/api/vision/stream" 
              alt="LIVE_FEED_OFFLINE" 
              className="w-full h-full object-cover opacity-80"
              onError={(e) => {
                // Fallback style if backend is down
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
            
            {/* Fallback text behind image */}
            <div className="absolute inset-0 flex items-center justify-center text-slate-700 text-xs tracking-widest -z-10">
              AWAITING STREAM CONNECTION ON PORT 8001...
            </div>

            {/* Military HUD Overlays */}
            <div className="absolute inset-0 pointer-events-none">
              {/* Grid background */}
              <div className="absolute inset-0 bg-[linear-gradient(rgba(16,185,129,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(16,185,129,0.05)_1px,transparent_1px)] bg-[size:40px_40px]"></div>
              
              {/* Crosshairs */}
              <div className="absolute top-1/2 left-0 w-full h-[1px] bg-emerald-500/20"></div>
              <div className="absolute top-0 left-1/2 w-[1px] h-full bg-emerald-500/20"></div>
              
              {/* Center Target Box */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 border-[1px] border-emerald-500/30">
                <div className="absolute -top-1 -left-1 w-3 h-3 border-t-2 border-l-2 border-emerald-500"></div>
                <div className="absolute -top-1 -right-1 w-3 h-3 border-t-2 border-r-2 border-emerald-500"></div>
                <div className="absolute -bottom-1 -left-1 w-3 h-3 border-b-2 border-l-2 border-emerald-500"></div>
                <div className="absolute -bottom-1 -right-1 w-3 h-3 border-b-2 border-r-2 border-emerald-500"></div>
              </div>
              
              {/* HUD Details */}
              <div className="absolute top-4 left-4 text-emerald-500/50 text-xs flex flex-col gap-1">
                <span>REC // CH-01</span>
                <span>LAT: 47.3829 N</span>
                <span>LNG: 12.8391 E</span>
              </div>
              <div className="absolute bottom-4 right-4 text-emerald-500/50 text-xs">
                ZOOM: 1.4x // OPTICS: IR
              </div>
              <Crosshair className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 text-emerald-500/40" />
            </div>
          </div>
        </div>

        {/* RIGHT PANE: SIGNAL INTELLIGENCE (40%) */}
        <div className="w-[40%] p-6 flex flex-col bg-slate-900/30">
          <div className="flex items-center gap-2 mb-4 text-slate-400 uppercase tracking-widest text-sm font-semibold">
            <Radio className="w-5 h-5 text-emerald-500" />
            <h2>Signal Intelligence</h2>
          </div>

          {/* Search Form */}
          <form onSubmit={onSubmit} className="flex gap-2 mb-6">
            <div className="relative flex-1">
              <Terminal className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-600" />
              <input 
                type="text" 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 focus:border-emerald-500 outline-none pl-10 pr-4 py-3 text-emerald-400 placeholder:text-slate-700 rounded-sm transition-colors" 
                placeholder="Enter search parameters (e.g., 'truck')..." 
              />
            </div>
            <button 
              type="submit" 
              disabled={loading}
              className="bg-emerald-950/50 border border-emerald-500/50 hover:bg-emerald-900 hover:text-white text-emerald-400 px-6 py-3 flex items-center gap-2 rounded-sm transition-all disabled:opacity-50 font-bold tracking-wider text-sm"
            >
              <Scan className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> 
              {loading ? "SCANNING..." : "SCAN COMMS"}
            </button>
          </form>

          {/* Intelligence Results List */}
          <div className="flex-1 overflow-y-auto pr-2 space-y-4 [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-slate-900 [&::-webkit-scrollbar-thumb]:bg-slate-700">
            
            {loading && (
              <div className="text-emerald-500/70 animate-pulse text-sm text-center py-10 tracking-widest">
                INTERCEPTING COMMS CHANNELS...
              </div>
            )}
            
            {error && (
              <div className="text-red-500 border border-red-900/50 bg-red-950/20 p-4 rounded-sm text-sm flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {!loading && !error && intelResults.length === 0 && (
              <div className="text-slate-600 text-sm text-center py-10 tracking-widest border border-dashed border-slate-800">
                NO INTEL FOUND. AWAITING QUERY.
              </div>
            )}

            {!loading && !error && intelResults.map((intel) => {
              const isUrgent = intel.transcript.includes("URGENT") || autoThreatActive;
              
              return (
                <div
                  key={intel.id} 
                  className={`p-4 border rounded-sm flex flex-col gap-3 relative overflow-hidden ${
                    isUrgent 
                      ? 'border-red-900/80 bg-red-950/10' 
                      : 'border-slate-800 bg-slate-950/50 hover:border-slate-600'
                  } transition-colors`}
                >
                  {isUrgent && (
                    <div className="absolute top-0 left-0 w-1 h-full bg-red-600"></div>
                  )}
                  
                  <div className="flex justify-between items-center text-xs tracking-widest">
                    <span className={`${isUrgent ? 'text-red-400' : 'text-emerald-500'} font-bold`}>
                      {intel.id}
                    </span>
                    <span className="text-slate-500">
                      LOC: {intel.location}
                    </span>
                  </div>
                  
                  <p className={`text-sm leading-relaxed ${isUrgent ? 'text-red-200' : 'text-slate-300'}`}>
                    "{intel.transcript}"
                  </p>
                  
                  <div className="flex justify-between items-center text-xs text-slate-500 border-t border-slate-800/50 pt-2 mt-1">
                    <span>MATCH CONFIDENCE: {(intel.score * 100).toFixed(1)}%</span>
                    <span className="bg-slate-900 px-2 py-1 rounded text-slate-400">CLASS: SIGINT</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}