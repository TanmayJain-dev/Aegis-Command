"use client";

import React, { useState, useEffect, useRef, useCallback, useMemo, Profiler } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, RefreshCw, Compass } from "lucide-react";

import { FeedManifestItem, loadFeedsManifest, loadFeedTimeline } from "../lib/feeds";
import { Timeline, DrawableDetection } from "../lib/timeline";
import { TriggerGate } from "../lib/threatTrigger";
import { useLiteMode } from "../hooks/useLiteMode";
import { useThreatSocket, ThreatSocketMessage } from "../hooks/useThreatSocket";
import { SEED_TACTICAL_INCIDENTS } from "../lib/seedIncidents";
import { playTacticalAlertTone } from "../lib/tacticalAudio";

import { IntelRecord, AegisHistoryRecord, ThreatAssessment, PerfReport } from "../types/aegis";
import { AppSidebar, NavSection } from "../components/aegis/AppSidebar";
import { TopBar } from "../components/aegis/TopBar";
import { LiveFeedPanel } from "../components/aegis/LiveFeedPanel";
import { ThreatAssessmentPanel } from "../components/aegis/ThreatAssessmentPanel";
import { DetectionTimeline } from "../components/aegis/DetectionTimeline";
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
  const [isSidebarOpenMobile, setIsSidebarOpenMobile] = useState(false);
  const [activeSection, setActiveSection] = useState<NavSection>("overview");

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

  // Live and recent detections list for DetectionTimeline table
  const [recentDetections, setRecentDetections] = useState<
    Array<{ time: number; detection: DrawableDetection; source: string }>
  >([]);

  // Cloud backend cold-start & probing state
  const [isProbingBackend, setIsProbingBackend] = useState(false);

  // Dev-only Perf Probe (?perf=1)
  const [perfReport, setPerfReport] = useState<PerfReport | null>(null);
  const perfCommitCount = useRef(0);
  const [perfEnabled] = useState(
    () => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("perf") === "1"
  );
  const [perfTargetFrames] = useState(
    () =>
      typeof window !== "undefined"
        ? parseInt(new URLSearchParams(window.location.search).get("frames") || "300", 10)
        : 300
  );

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
        timestamp: new Date().toLocaleTimeString() + " UTC",
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

  const [standbySeconds, setStandbySeconds] = useState(0);

  useEffect(() => {
    if (socketReady) return;
    const timer = setInterval(() => {
      setStandbySeconds((s) => s + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [socketReady]);

  const connectionStatus: "LIVE" | "DEGRADED" | "OFFLINE" = socketReady
    ? "LIVE"
    : standbySeconds >= 90
    ? "OFFLINE"
    : "DEGRADED";

  const triggerGateRef = useRef<TriggerGate>(new TriggerGate());

  // Detect desktop screen width for optimized Leaflet map rendering
  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
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
        setStandbySeconds(0);
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
        setIntelData(null);
        setAiSummary("Search service temporarily unreachable. Check network connection.");
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

        // Also record in recent detections
        setRecentDetections((prev) => [
          {
            time: currentTime,
            detection: {
              id: "Trigger-Threat",
              class: res.class,
              confidence: res.confidence,
              box: [0, 0, 0, 0],
              speed_kmh: res.speed_kmh,
              direction: res.direction,
            },
            source: activeFeed?.label || "UAV Alpha",
          },
          ...prev.slice(0, 19),
        ]);

        const sent = socketReady ? sendThreat(res) : false;

        // If socket is offline or message send fails, run resilient local assessment fallback
        if (!sent) {
          const fallbackAssessment: ThreatAssessment = {
            threat_level: "HIGH",
            score: Math.round(res.confidence * 100),
            reasoning: `Tactical Edge Anomaly: Target identified as [${res.class}] moving at ${res.speed_kmh} km/h bearing ${res.direction} along monitored sector. High probability of border reconnaissance breach.`,
            recommended_action:
              "Initiate immediate UAV lock and dispatch Quick Reaction Team (QRT) intercept vector.",
            previous_incidents: 3,
            assessment_source: "rule-based",
          };
          setLocalAssessment(fallbackAssessment);
          setIsThreatModalOpen(true);

          const newIncident: AegisHistoryRecord = {
            id: `INC-LIVE-${Date.now()}`,
            incident_id: `INC-LIVE-${Date.now()}`,
            timestamp: new Date().toLocaleTimeString() + " UTC",
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
    [socketReady, sendThreat, intelData, isSearching, handleSearch, activeFeed]
  );

  // Instant tactical drill simulation for presentations & demonstrations
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
      timestamp: new Date().toLocaleTimeString() + " UTC",
      transcript:
        "SIMULATED DRILL INTERCEPT: Unidentified convoy detected 200m south of outpost 14. SIGINT corroborates coordinated cross-border payload vector.",
    };
    setIntelData(drillIntel);

    const drillAssessment: ThreatAssessment = {
      threat_level: "CRITICAL",
      score: 96,
      reasoning: socketReady
        ? "Tactical Drill Verification: High-confidence anomaly correlation between EO/IR optronics and COMINT radio intercepts."
        : `[${connectionStatus} MODE] Autonomous backend unreachable. Threat assessed locally via deterministic rule-based heuristics.`,
      recommended_action:
        "Execute automated QRT alert vector. Command lockdown authorization granted.",
      assessment_source: socketReady ? "llm" : "rule-based",
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
      timestamp: new Date().toLocaleTimeString() + " UTC",
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
  }, [socketReady, connectionStatus, sendThreat]);

  // Handle addition of custom uploaded surveillance video feed
  const handleFeedCreated = useCallback((newFeed: FeedManifestItem) => {
    setFeeds((prev) => [...prev, newFeed]);
    setActiveFeedId(newFeed.id);
    if (typeof newFeed.center_lat === "number" && typeof newFeed.center_lng === "number") {
      setMapCoordinates([newFeed.center_lat, newFeed.center_lng]);
    }
  }, []);

  // Update active detections list from frame updates
  const handleActiveDetectionsChange = useCallback(
    (obsList: DrawableDetection[], time: number) => {
      if (obsList.length === 0) return;
      setRecentDetections((prev) => {
        const sourceName = activeFeed?.label || "UAV Alpha";
        const newItems = obsList.map((d) => ({
          time,
          detection: d,
          source: sourceName,
        }));
        const combined = [...newItems, ...prev];
        const seen = new Set<string>();
        const deduped: typeof combined = [];
        for (const item of combined) {
          const key = `${Math.floor(item.time * 2)}-${item.detection.id || item.detection.class}`;
          if (!seen.has(key)) {
            seen.add(key);
            deduped.push(item);
          }
          if (deduped.length >= 20) break;
        }
        return deduped;
      });
    },
    [activeFeed]
  );

  const systemInfo = useMemo(() => {
    return {
      fps: liteMode ? "30.00" : "59.94",
      model: timeline?.meta?.model || "yolov8m.pt",
      encryption: "AES-256",
      coordinates: mapCoordinates,
    };
  }, [liteMode, timeline, mapCoordinates]);

  const handleSelectSection = useCallback((section: NavSection) => {
    setActiveSection(section);
    if (section === "map") {
      setMobileTab("map");
    } else if (section === "intel") {
      setMobileTab("intel");
    } else if (section === "live") {
      setMobileTab("optics");
    } else if (section === "incidents") {
      setIsThreatModalOpen(true);
    } else if (section === "evidence") {
      setMobileTab("intel");
    }
    setIsSidebarOpenMobile(false);
  }, []);

  const content = (
    <div className="min-h-screen bg-[#08111d] text-[#f2f5f8] flex flex-col font-sans">
      {/* Top Header Bar */}
      <TopBar
        connectionStatus={connectionStatus}
        socketReady={socketReady}
        isProbingBackend={isProbingBackend}
        onProbeBackend={probeBackend}
        liteMode={liteMode}
        onToggleLiteMode={toggleLiteMode}
        onOpenHistory={() => setIsHistoryModalOpen(true)}
        activeFeedLabel={activeFeed?.label}
        onToggleSidebarMobile={() => setIsSidebarOpenMobile(!isSidebarOpenMobile)}
      />

      {/* Backend Degraded / Cold-Start Banner */}
      {connectionStatus === "DEGRADED" && (
        <div className="bg-[#f59e0b]/10 border-b border-[#f59e0b]/30 px-4 py-1.5 flex items-center justify-between text-xs text-[#f59e0b] font-mono">
          <div className="flex items-center gap-2 truncate mr-2">
            <AlertTriangle size={13} className="text-[#f59e0b] flex-shrink-0" />
            <span className="truncate">
              Autonomous backend warming up (~60s) · Operating in resilient local deterministic mode
            </span>
          </div>
          <button
            type="button"
            onClick={probeBackend}
            disabled={isProbingBackend}
            className="px-2 py-0.5 border border-[#f59e0b]/40 hover:bg-[#f59e0b]/20 rounded flex items-center gap-1 font-semibold text-[10px] flex-shrink-0 transition-colors"
          >
            <RefreshCw size={10} className={isProbingBackend ? "animate-spin" : ""} />
            {isProbingBackend ? "Probing..." : "Retry"}
          </button>
        </div>
      )}

      {/* Backend Offline Banner */}
      {connectionStatus === "OFFLINE" && (
        <div className="bg-[#ef4444]/10 border-b border-[#ef4444]/30 px-4 py-1.5 flex items-center justify-between text-xs text-[#ef4444] font-mono">
          <div className="flex items-center gap-2 truncate mr-2">
            <AlertTriangle size={13} className="text-[#ef4444] flex-shrink-0" />
            <span className="truncate">
              Autonomous cloud backend offline · Local deterministic rule-based mode active
            </span>
          </div>
          <button
            type="button"
            onClick={probeBackend}
            disabled={isProbingBackend}
            className="px-2 py-0.5 border border-[#ef4444]/40 hover:bg-[#ef4444]/20 rounded flex items-center gap-1 font-semibold text-[10px] flex-shrink-0 transition-colors"
          >
            <RefreshCw size={10} className={isProbingBackend ? "animate-spin" : ""} />
            {isProbingBackend ? "Probing..." : "Retry"}
          </button>
        </div>
      )}

      {/* Main Container: Sidebar + Workspace */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Desktop Sidebar */}
        <div className="hidden md:flex">
          <AppSidebar
            activeSection={activeSection}
            onSelectSection={handleSelectSection}
            feeds={feeds}
            activeFeedId={activeFeedId}
            onSelectFeed={(feedId) => {
              setActiveFeedId(feedId);
              const f = feeds.find((item) => item.id === feedId);
              if (f?.center_lat && f?.center_lng) {
                setMapCoordinates([f.center_lat, f.center_lng]);
              }
            }}
            onOpenUploadModal={() => setIsUploadModalOpen(true)}
            onSimulateDrill={handleSimulateDrill}
            onOpenHistoryModal={() => setIsHistoryModalOpen(true)}
            systemInfo={systemInfo}
          />
        </div>

        {/* Mobile Sidebar Drawer */}
        {isSidebarOpenMobile && (
          <div className="md:hidden fixed inset-0 z-50 flex">
            <div
              className="fixed inset-0 bg-[#08111d]/80 backdrop-blur-sm"
              onClick={() => setIsSidebarOpenMobile(false)}
            />
            <div className="relative z-50 h-full">
              <AppSidebar
                activeSection={activeSection}
                onSelectSection={handleSelectSection}
                feeds={feeds}
                activeFeedId={activeFeedId}
                onSelectFeed={(feedId) => {
                  setActiveFeedId(feedId);
                  const f = feeds.find((item) => item.id === feedId);
                  if (f?.center_lat && f?.center_lng) {
                    setMapCoordinates([f.center_lat, f.center_lng]);
                  }
                  setIsSidebarOpenMobile(false);
                }}
                onOpenUploadModal={() => {
                  setIsUploadModalOpen(true);
                  setIsSidebarOpenMobile(false);
                }}
                onSimulateDrill={() => {
                  handleSimulateDrill();
                  setIsSidebarOpenMobile(false);
                }}
                onOpenHistoryModal={() => {
                  setIsHistoryModalOpen(true);
                  setIsSidebarOpenMobile(false);
                }}
                systemInfo={systemInfo}
              />
            </div>
          </div>
        )}

        {/* Workspace Column */}
        <div className="flex-1 flex flex-col min-w-0 overflow-y-auto custom-scrollbar">
          {/* Mobile Tabs */}
          <MobileTabs activeTab={mobileTab} onTabChange={setMobileTab} />

          {/* Main Dashboard Layout */}
          <main className="p-3 sm:p-4 lg:p-5 flex flex-col gap-4 max-w-[1920px] w-full mx-auto">
            {/* UPPER ROW: Hero Video (8 cols) + Threat Assessment (4 cols) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
              {/* Hero Video Feed */}
              <section
                className={`${
                  mobileTab === "optics" ? "flex" : "hidden lg:flex"
                } lg:col-span-8 flex flex-col`}
              >
                <LiveFeedPanel
                  activeFeed={activeFeed}
                  timeline={timeline}
                  liteMode={liteMode}
                  onThreatSample={handleThreatSample}
                  perfEnabled={perfEnabled}
                  perfTargetFrames={perfTargetFrames}
                  onPerfReport={setPerfReport}
                  onActiveDetectionsChange={handleActiveDetectionsChange}
                />
              </section>

              {/* Threat Assessment Panel */}
              <section
                className={`${
                  mobileTab === "optics" ? "flex" : "hidden lg:flex"
                } lg:col-span-4 flex flex-col`}
              >
                <ThreatAssessmentPanel
                  assessment={activeAssessment}
                  intelData={intelData}
                  onOpenActionModal={() => setIsThreatModalOpen(true)}
                  onSimulateDrill={handleSimulateDrill}
                />
              </section>
            </div>

            {/* LOWER ROW: Detection Table (4 cols) + Tactical Map (4 cols) + Intel (4 cols) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
              {/* Detection Timeline Table */}
              <section
                className={`${
                  mobileTab === "optics" ? "flex" : "hidden lg:flex"
                } lg:col-span-4 flex flex-col`}
              >
                <DetectionTimeline
                  recentDetections={recentDetections}
                  onSelectDetectionTime={(t) => {
                    const videoEl = document.querySelector("video");
                    if (videoEl) {
                      videoEl.currentTime = t;
                      videoEl.play().catch(() => {});
                    }
                  }}
                />
              </section>

              {/* Tactical Map */}
              <section
                className={`${
                  mobileTab === "map" ? "flex" : "hidden lg:flex"
                } lg:col-span-4 flex flex-col min-h-[300px] h-[320px]`}
              >
                <div className="flex flex-col h-full rounded bg-[#0d1724] border border-[#243244] overflow-hidden">
                  <div className="px-3.5 py-2.5 bg-[#121e2c] border-b border-[#243244] flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Compass size={14} className="text-[#3b82f6]" />
                      <span className="text-[12px] font-semibold text-[#f2f5f8] tracking-wide">
                        Tactical Map
                      </span>
                    </div>
                    <span className="text-[10px] font-mono text-[#708096]">
                      CARTO / OpenStreetMap
                    </span>
                  </div>
                  <div className="flex-1 relative">
                    {(isDesktop || mobileTab === "map") && (
                      <MapComponent
                        key={`aegis-map-${mobileTab}`}
                        coordinates={mapCoordinates}
                      />
                    )}
                  </div>
                </div>
              </section>

              {/* Intelligence Retrieval (RAG / SIGINT / OSINT) */}
              <section
                className={`${
                  mobileTab === "intel" ? "flex" : "hidden lg:flex"
                } lg:col-span-4 flex flex-col min-h-[300px] h-[320px]`}
              >
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
            </div>
          </main>
        </div>
      </div>

      {/* Action Modals */}
      <ThreatModal
        isOpen={isThreatModalOpen}
        onClose={() => setIsThreatModalOpen(false)}
        intelData={intelData}
        threatAssessment={activeAssessment}
        aiSummary={aiSummary}
      />

      <HistoryModal
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
        historyRecords={historyRecords}
      />

      <UploadFeedModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onFeedCreated={handleFeedCreated}
      />

      {/* Dev Benchmark Probe Banner */}
      {perfReport && (
        <div
          id="perf-report-banner"
          className="fixed top-2 right-2 z-[99999] bg-[#08111d]/95 border border-[#10b981] p-2 text-xs font-mono text-[#10b981] rounded shadow-lg"
        >
          PROBE: frames={perfReport.frames} mean={perfReport.mean_draw_ms}ms p95=
          {perfReport.p95_draw_ms}ms boxes={perfReport.mean_boxes} commits/100f=
          {perfReport.commits_per_100_frames} status={perfReport.status}
        </div>
      )}
    </div>
  );

  return perfEnabled ? (
    <Profiler id="AegisDashboard" onRender={handleRender}>
      {content}
    </Profiler>
  ) : (
    content
  );
}