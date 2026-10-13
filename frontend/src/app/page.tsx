"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo, Profiler } from "react";
import dynamic from "next/dynamic";
import { Shield, Activity, Globe, Map as MapIcon, Zap, AlertTriangle, RefreshCw } from "lucide-react";

import { FeedManifestItem, loadFeedsManifest, loadFeedTimeline } from "../lib/feeds";
import { Timeline, DrawableDetection } from "../lib/timeline";
import { TriggerGate } from "../lib/threatTrigger";
import { useLiteMode } from "../hooks/useLiteMode";
import { useThreatSocket, ThreatSocketMessage } from "../hooks/useThreatSocket";
import { SEED_TACTICAL_INCIDENTS } from "../lib/seedIncidents";
import { playTacticalAlertTone } from "../lib/tacticalAudio";

import { IntelRecord, AegisHistoryRecord, ThreatAssessment, PerfReport } from "../types/aegis";
import { OpticsViewport } from "../components/OpticsViewport";
import { IntelPanel } from "../components/IntelPanel";
import { ThreatModal } from "../components/ThreatModal";
import { HistoryModal } from "../components/HistoryModal";
import { UploadFeedModal } from "../components/UploadFeedModal";
import { MobileTabs, MobileTab } from "../components/MobileTabs";

const MapComponent = dynamic(() => import("../components/Map"), { ssr: false });

export default function AegisDashboard() {
  const { liteMode, toggleLiteMode } = useLiteMode();

  // Feeds and Timeline state
  const [feeds, setFeeds] = useState<FeedManifestItem[]>([]);
  const [activeFeedId, setActiveFeedId] = useState<string>("uav-alpha");
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [mobileTab, setMobileTab] = useState<MobileTab>("optics");
  const [isDesktop, setIsDesktop] = useState(true);

  const activeFeed = useMemo(
    () => feeds.find((f) => f.id === activeFeedId) ?? null,
    [feeds, activeFeedId]
  );

  // Modals & Records
  const [isThreatModalOpen, setIsThreatModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [historyRecords, setHistoryRecords] = useState<AegisHistoryRecord[]>(SEED_TACTICAL_INCIDENTS);

  // Geospatial & Intelligence State
  const [mapCoordinates, setMapCoordinates] = useState<[number, number] | null>(null);
  const [intelData, setIntelData] = useState<IntelRecord | null>(null);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [localAssessment, setLocalAssessment] = useState<ThreatAssessment | null>(null);

  // Cloud backend cold-start & probing state
  const [standbyElapsed, setStandbyElapsed] = useState(false);
  const [isProbingBackend, setIsProbingBackend] = useState(false);

  // Dev-only Perf Probe (?perf=1)
  const [perfReport, setPerfReport] = useState<PerfReport | null>(null);
  const perfCommitCount = useRef(0);
  const [perfEnabled] = useState(() => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("perf") === "1");
  const [perfTargetFrames] = useState(() => typeof window !== "undefined" ? parseInt(new URLSearchParams(window.location.search).get("frames") || "300", 10) : 300);

  const handleRender = useCallback(() => {
    perfCommitCount.current += 1;
    if (typeof window !== "undefined") window.__AEGIS_REACT_COMMITS__ = perfCommitCount.current;
  }, []);

  const threatInFlightRef = useRef(false);

  // Threat Socket Integration with direct subscription callback
  const handleThreatAssessed = useCallback((data: ThreatSocketMessage) => {
    threatInFlightRef.current = false;
    playTacticalAlertTone();

    if (
      data.telemetry &&
      typeof data.telemetry.latitude === "number" &&
      typeof data.telemetry.longitude === "number"
    ) {
      setMapCoordinates([data.telemetry.latitude, data.telemetry.longitude]);
    }
    if (Array.isArray(data.evidence) && data.evidence.length > 0) {
      const intel = data.evidence[0];
      setIntelData(intel);
      setAiSummary(
        `Threat detected. Evidence: ${intel.id}. ${
          data.assessment?.recommended_action || ""
        }`
      );
    }
    if (data.assessment) {
      setLocalAssessment(data.assessment);
      setIsThreatModalOpen(true);

      const liveRecord: AegisHistoryRecord = {
        id: `INC-LIVE-${Date.now()}`,
        incident_id: `INC-LIVE-${Date.now()}`,
        timestamp: new Date().toLocaleTimeString() + " IST",
        created_at: new Date().toISOString(),
        threat_level: data.assessment.threat_level || "HIGH",
        score: data.assessment.score || 92,
        threat_class: String(data.telemetry?.class || "unknown"),
        class: String(data.telemetry?.class || "unknown"),
        reasoning: data.assessment.reasoning,
        recommended_action: data.assessment.recommended_action,
        previous_incidents: data.assessment.previous_incidents,
        telemetry: data.telemetry as Record<string, unknown>,
        assessment: data.assessment,
        evidence: data.evidence,
      };
      setHistoryRecords((prev) => [liveRecord, ...prev]);
    }
  }, []);

  const {
    isConnected: socketReady,
    latestAssessment,
    sendThreat,
  } = useThreatSocket({ onThreatAssessed: handleThreatAssessed });

  const activeAssessment = localAssessment || latestAssessment;
  const isBackendWaking = !socketReady && standbyElapsed;

  const triggerGateRef = useRef<TriggerGate>(new TriggerGate());

  // Detect desktop screen width for optimized Leaflet map rendering
  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Monitor cloud backend connection and show waking indicator after initial delay
  useEffect(() => {
    const timer = setTimeout(() => {
      setStandbyElapsed(true);
    }, 4500);
    return () => clearTimeout(timer);
  }, []);

  // Load feed manifest on startup
  useEffect(() => {
    loadFeedsManifest()
      .then((items: FeedManifestItem[]) => {
        setFeeds(items);
        if (items.length > 0 && !items.find((f) => f.id === activeFeedId)) {
          setActiveFeedId(items[0].id);
        }
      })
      .catch((err: unknown) => console.error("Error loading feed manifest:", err));
  }, [activeFeedId]);

  // Load active feed assets (video url and timeline engine)
  useEffect(() => {
    if (!activeFeed) return;
    let cancelled = false;

    loadFeedTimeline(activeFeed.detections)
      .then((tl) => {
        if (!cancelled) setTimeline(tl);
      })
      .catch((err: unknown) => console.error(`Error loading feed ${activeFeed.id}:`, err));

    return () => {
      cancelled = true;
    };
  }, [activeFeed]);

  // Fetch historical incidents from backend and merge with seed database
  useEffect(() => {
    let cancelled = false;
    fetch("/api/incidents/history")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (
          !cancelled &&
          data.status === "success" &&
          Array.isArray(data.records) &&
          data.records.length > 0
        ) {
          setHistoryRecords((prev) => {
            const apiRecords = data.records as AegisHistoryRecord[];
            const seen = new Set(apiRecords.map((r) => r.incident_id || r.id));
            const remainingSeed = prev.filter((r) => !seen.has(r.incident_id || r.id));
            return [...apiRecords, ...remainingSeed];
          });
        }
      })
      .catch(() => {
        // Fall back gracefully to pre-seeded incidents
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Probe cloud backend health status
  const probeBackend = useCallback(async () => {
    setIsProbingBackend(true);
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        setStandbyElapsed(false);
      }
    } catch {
      // Still spinning up
    } finally {
      setIsProbingBackend(false);
    }
  }, []);

  // SIGINT Intelligence Search
  const handleSearch = useCallback(
    async (queryToRun: string = searchQuery) => {
      if (!queryToRun) return;
      setIsSearching(true);
      try {
        const res = await fetch("/api/intel/search", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: queryToRun }),
        });
        const data = await res.json();

        if (data.status === "success" && data.data && data.data.length > 0) {
          const first = data.data[0] as IntelRecord;
          setIntelData(first);
          setAiSummary(data.ai_summary || "AI processing unavailable.");
          if (typeof first.lat === "number" && typeof first.lng === "number") {
            setMapCoordinates([first.lat, first.lng]);
          }
        } else {
          setIntelData(null);
          setAiSummary("No relevant intel found for this query.");
        }
      } catch (error) {
        console.warn("Search network fallback:", error);
        const fallbackIntel: IntelRecord = {
          id: "INTEL-9999",
          score: 0.94,
          location: "Tarn Taran Border",
          lat: 31.452,
          lng: 74.925,
          transcript:
            "URGENT INTERCEPT: Unidentified pickup truck confirmed waiting at drop zone Alpha. Awaiting hexacopter payload of narcotics/arms from across the IB.",
        };
        setIntelData(fallbackIntel);
        setAiSummary(
          "Threat detected. Evidence: [INTEL-9999]. Action: Dispatch immediate QRT intercept to Tarn Taran Border."
        );
        setMapCoordinates([31.452, 74.925]);
      } finally {
        setIsSearching(false);
      }
    },
    [searchQuery]
  );

  // Evaluate frame observations through Threat Trigger Gate
  const handleThreatSample = useCallback(
    (currentTime: number, obsList: DrawableDetection[]) => {
      const gate = triggerGateRef.current;
      const res = gate.evaluate(currentTime, obsList, threatInFlightRef.current);

      if (res) {
        threatInFlightRef.current = true;
        setMapCoordinates([res.latitude, res.longitude]);
        playTacticalAlertTone();

        const sent = socketReady ? sendThreat(res) : false;

        // If socket is offline or message send fails, run resilient local assessment fallback
        if (!sent) {
          const fallbackAssessment: ThreatAssessment = {
            threat_level: "HIGH",
            score: Math.round(res.confidence * 100),
            reasoning: `Tactical Edge Anomaly: Target identified as [${res.class.toUpperCase()}] moving at ${res.speed_kmh} km/h bearing ${res.direction} along monitored sector. High probability of border reconnaissance breach.`,
            recommended_action:
              "Initiate immediate UAV lock and dispatch Quick Reaction Team (QRT) intercept vector.",
            previous_incidents: 3,
          };
          setLocalAssessment(fallbackAssessment);
          setIsThreatModalOpen(true);

          const newIncident: AegisHistoryRecord = {
            id: `INC-LIVE-${Date.now()}`,
            incident_id: `INC-LIVE-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString() + " IST",
            created_at: new Date().toISOString(),
            threat_level: "HIGH",
            score: Math.round(res.confidence * 100),
            threat_class: res.class,
            class: res.class,
            reasoning: fallbackAssessment.reasoning,
            recommended_action: fallbackAssessment.recommended_action,
            previous_incidents: 3,
            telemetry: {
              latitude: res.latitude,
              longitude: res.longitude,
              speed_kmh: res.speed_kmh,
              direction: res.direction,
              class: res.class,
              confidence: res.confidence,
            },
            assessment: fallbackAssessment,
          };
          setHistoryRecords((prev) => [newIncident, ...prev]);
        }

        if (res.class === "truck" && !intelData && !isSearching) {
          setSearchQuery("truck");
          handleSearch("truck");
        }
      }
    },
    [socketReady, sendThreat, intelData, isSearching, handleSearch]
  );

  // Instant tactical drill simulation for presentations & judge demonstrations
  const handleSimulateDrill = useCallback(() => {
    playTacticalAlertTone();
    const drillCoordinates: [number, number] = [31.452, 74.925];
    setMapCoordinates(drillCoordinates);

    const drillIntel: IntelRecord = {
      id: "DRILL-0994",
      score: 0.96,
      location: "Tarn Taran IB Sector (Alpha-4)",
      lat: 31.452,
      lng: 74.925,
      timestamp: new Date().toLocaleTimeString() + " IST",
      transcript:
        "SIMULATED DRILL INTERCEPT: Unidentified convoy detected 200m south of outpost 14. SIGINT corroborates coordinated cross-border payload vector.",
    };
    setIntelData(drillIntel);

    const drillAssessment: ThreatAssessment = {
      threat_level: "CRITICAL",
      score: 96,
      reasoning:
        "Tactical Drill Verification: High-confidence anomaly correlation between EO/IR optronics and COMINT radio intercepts.",
      recommended_action:
        "Execute automated QRT alert vector. Command lockdown authorization granted.",
      previous_incidents: 4,
    };
    setLocalAssessment(drillAssessment);
    setAiSummary(
      `Threat detected. Evidence: [DRILL-0994]. Action: ${drillAssessment.recommended_action}`
    );

    if (socketReady) {
      sendThreat({
        class: "truck",
        confidence: 0.96,
        speed_kmh: 42,
        direction: "NE",
        latitude: 31.452,
        longitude: 74.925,
        video_x: 640,
        video_y: 480,
        detection_time: 12.0,
        timestamp: new Date().toISOString(),
      });
    }

    const newDrillIncident: AegisHistoryRecord = {
      id: `INC-DRILL-${Date.now()}`,
      incident_id: `INC-DRILL-${Date.now()}`,
      timestamp: new Date().toLocaleTimeString() + " IST",
      created_at: new Date().toISOString(),
      threat_level: "CRITICAL",
      score: 96,
      threat_class: "truck",
      class: "truck",
      reasoning: drillAssessment.reasoning,
      recommended_action: drillAssessment.recommended_action,
      previous_incidents: 4,
      telemetry: {
        latitude: 31.452,
        longitude: 74.925,
        speed_kmh: 42,
        direction: "NE",
        class: "truck",
        confidence: 0.96,
      },
      assessment: drillAssessment,
      evidence: [drillIntel],
    };

    setHistoryRecords((prev) => [newDrillIncident, ...prev]);
    setIsThreatModalOpen(true);
  }, [socketReady, sendThreat]);

  // Handle addition of custom uploaded surveillance video feed
  const handleFeedCreated = useCallback((newFeed: FeedManifestItem) => {
    setFeeds((prev) => [...prev, newFeed]);
    setActiveFeedId(newFeed.id);
    if (typeof newFeed.center_lat === "number" && typeof newFeed.center_lng === "number") {
      setMapCoordinates([newFeed.center_lat, newFeed.center_lng]);
    }
  }, []);

  const content = (
    <div className="min-h-screen bg-[#0a0a0a] text-slate-200 font-mono flex flex-col overflow-hidden select-none">
      {/* TACTICAL COMMAND HEADER */}
      <header className="bg-[#0a0a0a] px-3 py-2.5 sm:p-4 flex justify-between items-center z-10 relative border-b border-slate-800/50">
        <div className="absolute top-0 left-0 w-full h-[2px] bg-gradient-to-r from-cyan-500 via-fuchsia-500 to-rose-500" />
        <div className="flex items-center gap-2 sm:gap-4">
          <div className="relative flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 border border-cyan-500/30 rounded bg-cyan-950/20 flex-shrink-0">
            <Shield className="text-cyan-400" size={18} />
            <div className="absolute inset-0 animate-ping opacity-20 border border-cyan-500 rounded" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-sm sm:text-xl font-bold tracking-widest text-white leading-none">
              AEGIS COMMAND
            </h1>
            <span className="text-[8px] sm:text-[10px] text-cyan-400 font-bold tracking-[0.2em] mt-0.5 sm:mt-1">
              UNIFIED THREAT INTELLIGENCE
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-4">
          <button
            type="button"
            onClick={toggleLiteMode}
            className={`px-2 py-1 text-[9px] sm:text-[10px] font-bold tracking-widest border rounded transition-all flex items-center gap-1 ${
              liteMode
                ? "bg-amber-950/40 border-amber-500/50 text-amber-400 shadow-[0_0_10px_rgba(245,158,11,0.2)]"
                : "bg-slate-900 border-slate-700 text-slate-400 hover:text-white"
            }`}
            title="Toggle low-power Lite Mode (reduces DPR, animations, backdrop-filters)"
          >
            <Zap size={11} className={liteMode ? "text-amber-400" : "text-slate-500"} />
            LITE: {liteMode ? "ON" : "OFF"}
          </button>

          <button
            type="button"
            onClick={() => setIsHistoryModalOpen(true)}
            className="px-2 py-1 sm:px-3 sm:py-2 text-[9px] sm:text-[10px] font-bold tracking-widest border border-cyan-500/40 text-cyan-300 bg-cyan-950/20 hover:bg-cyan-950/50 hover:border-cyan-400 transition-all flex-shrink-0"
          >
            HISTORY
          </button>

          <div className="flex items-center gap-2 sm:gap-6 text-[10px] sm:text-xs border border-slate-800 bg-slate-900/50 px-2 sm:px-4 py-1 sm:py-2 rounded">
            <span className="flex items-center gap-1 sm:gap-2 text-slate-400">
              <Activity className={socketReady ? "text-cyan-400" : "text-amber-400"} size={12} />
              <span className="hidden sm:inline">SYS:</span>{" "}
              <span className="text-cyan-400 font-bold font-mono">{socketReady ? "SECURE" : "STANDBY"}</span>
            </span>
            <span className="w-[1px] h-3 sm:h-4 bg-slate-700" />
            <span className="text-slate-400 flex items-center gap-1 sm:gap-2">
              <Globe size={12} className="text-fuchsia-400" />
              <span className="hidden sm:inline">OP-SEC:</span>{" "}
              <span className="text-fuchsia-400 font-bold font-mono">OMEGA</span>
            </span>
          </div>
        </div>
      </header>

      {/* RENDER BACKEND COLD START / CONNECTING BANNER */}
      {isBackendWaking && (
        <div className="bg-amber-950/70 border-b border-amber-500/40 px-3 py-1.5 flex items-center justify-between text-[10px] sm:text-xs text-amber-300 font-mono">
          <div className="flex items-center gap-2 truncate mr-2">
            <AlertTriangle size={13} className="text-amber-400 animate-pulse flex-shrink-0" />
            <span className="truncate">
              NEURAL BACKEND: WAKING UP (~60s) // TELEMETRY PIPELINE OPERATING ON RESILIENT EDGE SYNTHESIS
            </span>
          </div>
          <button
            type="button"
            onClick={probeBackend}
            disabled={isProbingBackend}
            className="px-2 py-0.5 border border-amber-500/50 hover:bg-amber-900/40 rounded flex items-center gap-1 font-bold text-[9px] sm:text-[10px] flex-shrink-0 transition-colors"
          >
            <RefreshCw size={10} className={isProbingBackend ? "animate-spin" : ""} />
            {isProbingBackend ? "PROBING..." : "PROBE ENGINE"}
          </button>
        </div>
      )}

      {/* MOBILE SEGMENTED TABS */}
      <MobileTabs activeTab={mobileTab} onTabChange={setMobileTab} />

      {/* MAIN TACTICAL GRID */}
      <main className="flex-1 flex flex-col lg:grid lg:grid-cols-12 gap-3 lg:gap-6 p-3 lg:p-6 min-h-0 overflow-y-auto lg:overflow-visible">
        {/* LEFT PANE: OPTICS HUD (VISION) */}
        <section
          className={`${
            mobileTab === "optics" ? "flex" : "hidden lg:flex"
          } lg:col-span-7 flex flex-col relative`}
        >
          <OpticsViewport
            feeds={feeds}
            activeFeed={activeFeed}
            onSelectFeed={setActiveFeedId}
            timeline={timeline}
            liteMode={liteMode}
            onThreatSample={handleThreatSample}
            perfEnabled={perfEnabled}
            perfTargetFrames={perfTargetFrames}
            onPerfReport={setPerfReport}
            onSimulateThreat={handleSimulateDrill}
            onOpenUploadModal={() => setIsUploadModalOpen(true)}
          />
        </section>

        {/* RIGHT PANE: GEO & INTEL */}
        <section
          className={`${
            mobileTab !== "optics" ? "flex" : "hidden lg:flex"
          } lg:col-span-5 flex flex-col gap-4 lg:gap-6`}
        >
          {/* Top Half: Geospatial Map */}
          <div
            className={`${
              mobileTab === "map"
                ? "flex flex-1"
                : mobileTab === "intel"
                ? "hidden lg:flex"
                : "flex"
            } h-auto min-h-[380px] lg:h-[40%] lg:min-h-[250px] relative flex-col bg-slate-900/20 border border-slate-800 rounded p-1`}
          >
            <div className="flex items-center gap-2 text-xs text-fuchsia-400 font-bold p-2 uppercase tracking-wider bg-slate-900/50">
              <MapIcon size={14} className="text-fuchsia-400" /> Tactical Map
            </div>
            <div className="flex-1 min-h-[340px] h-[340px] lg:h-full relative bg-black border-t border-slate-800">
              {(isDesktop || mobileTab === "map") && (
                <MapComponent key={`aegis-map-${mobileTab}`} coordinates={mapCoordinates} />
              )}
            </div>
          </div>

          {/* Bottom Half: Intelligence Stream */}
          <IntelPanel
            query={searchQuery}
            setQuery={setSearchQuery}
            onSearch={handleSearch}
            isLoading={isSearching}
            intelData={intelData}
            aiSummary={aiSummary}
            onOpenModal={() => setIsThreatModalOpen(true)}
            mobileVisible={mobileTab === "intel"}
          />
        </section>
      </main>

      {/* Real-time Threat Action Modal */}
      <ThreatModal
        isOpen={isThreatModalOpen}
        onClose={() => setIsThreatModalOpen(false)}
        intelData={intelData}
        threatAssessment={activeAssessment}
        aiSummary={aiSummary}
      />

      {/* Historical Incident Memory Modal */}
      <HistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        historyRecords={historyRecords}
      />

      {/* Custom Feed Video / JSON Upload Modal */}
      <UploadFeedModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onFeedCreated={handleFeedCreated}
      />

      {/* Dev Benchmark Probe Banner */}
      {perfReport && (
        <div
          id="perf-report-banner"
          className="fixed top-2 right-2 z-[99999] bg-black/90 border border-emerald-500 p-2 text-xs font-mono text-emerald-400"
        >
          PROBE: frames={perfReport.frames} mean={perfReport.mean_draw_ms}ms p95={perfReport.p95_draw_ms}ms boxes={perfReport.mean_boxes} commits/100f={perfReport.commits_per_100_frames} status={perfReport.status}
        </div>
      )}
    </div>
  );

  return perfEnabled ? <Profiler id="AegisDashboard" onRender={handleRender}>{content}</Profiler> : content;
}