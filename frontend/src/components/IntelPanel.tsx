"use client";

import React, { useState, useMemo } from "react";
import {
  Search,
  Loader2,
  FileText,
  MapPin,
  Radio,
  ExternalLink,
  ShieldAlert,
  Compass,
} from "lucide-react";
import { IntelRecord, ChatterItem } from "../types/aegis";

export type IntelMode = "SIGINT" | "OSINT";

export interface IntelPanelProps {
  query: string;
  setQuery: (query: string) => void;
  onSearch: (searchQuery?: string) => void;
  isLoading: boolean;
  intelData: IntelRecord | null;
  aiSummary: string;
  onOpenModal: () => void;
  mobileVisible?: boolean;
}

interface ParsedBullet {
  type: "SITUATION" | "EVIDENCE" | "DIRECTIVE" | "GENERAL";
  title: string;
  text: string;
}

const OSINT_MOCK_FEED: ChatterItem[] = [
  {
    src: "Border Telecom Monitor / Cell Tower S-4",
    time: "2m ago",
    text: "Anomalous burst of unencrypted roaming SIM connections recorded near forward culvert milestone 114.",
    threat: "HIGH",
  },
  {
    src: "VHF Tactical Intercept / 142.85 MHz",
    time: "11m ago",
    text: "Directional hop transmission: Repeated logistics inquiries regarding blindspots along perimeter CCTV-04.",
    threat: "MED",
  },
  {
    src: "ADS-B / Drone Beacon Sentry",
    time: "24m ago",
    text: "Low-altitude transponder drop registered at 120m AGL along Chenab riverine bend. Radar tracking handoff initiated.",
    threat: "HIGH",
  },
  {
    src: "Acoustic Ground Sentry Array",
    time: "48m ago",
    text: "Dual-rotor low-frequency resonance (180 Hz) registered by passive acoustic array at Samba sector perimeter fence.",
    threat: "MED",
  },
  {
    src: "BSF Sector Operations Log",
    time: "1h ago",
    text: "Joint Army-BSF QRT completed scheduled night relief. Optronic FLIR barriers verified operational across all outposts.",
    threat: "LOW",
  },
];

const QUICK_SUGGESTIONS = [
  "Drop Zone Alpha",
  "Hexacopter",
  "Samba Sector",
  "Seismic Trigger",
  "Micro-Doppler",
  "Chenab Riverine",
  "Akhnoor Post",
];

function extractDiscipline(transcript?: string): { tag: string; cleanText: string; color: string } {
  if (!transcript) return { tag: "INTEL", cleanText: "", color: "bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/30" };
  const match = transcript.match(/^\[(.*?)\]\s*(.*)$/);
  if (match) {
    const rawTag = match[1].toUpperCase();
    const cleanText = match[2];
    let color = "bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/30";
    if (rawTag.includes("FLASH") || rawTag.includes("ALERT") || rawTag.includes("CRITICAL")) {
      color = "bg-[#ef4444]/10 text-[#ef4444] border-[#ef4444]/30";
    } else if (rawTag.includes("ELINT") || rawTag.includes("RADAR") || rawTag.includes("EW")) {
      color = "bg-[#06b6d4]/10 text-[#06b6d4] border-[#06b6d4]/30";
    } else if (rawTag.includes("SIGINT") || rawTag.includes("COMINT") || rawTag.includes("CELLULAR")) {
      color = "bg-[#8b5cf6]/10 text-[#a78bfa] border-[#8b5cf6]/30";
    } else if (rawTag.includes("OPTICS") || rawTag.includes("FLIR") || rawTag.includes("THERMAL")) {
      color = "bg-[#f59e0b]/10 text-[#f59e0b] border-[#f59e0b]/30";
    } else if (rawTag.includes("SEISMIC") || rawTag.includes("BARRIER")) {
      color = "bg-[#ec4899]/10 text-[#ec4899] border-[#ec4899]/30";
    } else if (rawTag.includes("ROUTINE") || rawTag.includes("PATROL")) {
      color = "bg-[#10b981]/10 text-[#10b981] border-[#10b981]/30";
    }
    return { tag: rawTag, cleanText, color };
  }
  return { tag: "SIGINT / INTERCEPT", cleanText: transcript, color: "bg-[#3b82f6]/10 text-[#3b82f6] border-[#3b82f6]/30" };
}

function parseAiBullets(summary: string): ParsedBullet[] {
  if (!summary) return [];
  const lines = summary.split("\n").map(l => l.trim()).filter(Boolean);
  const result: ParsedBullet[] = [];

  for (const line of lines) {
    const clean = line.replace(/^[•\-*]\s*/, "");
    if (/^SITUATION\s*[:\-]/i.test(clean)) {
      result.push({
        type: "SITUATION",
        title: "SITUATION",
        text: clean.replace(/^SITUATION\s*[:\-]\s*/i, ""),
      });
    } else if (/^EVIDENCE\s*[:\-]/i.test(clean)) {
      result.push({
        type: "EVIDENCE",
        title: "EVIDENCE",
        text: clean.replace(/^EVIDENCE\s*[:\-]\s*/i, ""),
      });
    } else if (/^(DIRECTIVE|ACTION|RECOMMENDATION)\s*[:\-]/i.test(clean)) {
      result.push({
        type: "DIRECTIVE",
        title: "DIRECTIVE",
        text: clean.replace(/^(DIRECTIVE|ACTION|RECOMMENDATION)\s*[:\-]\s*/i, ""),
      });
    } else {
      result.push({
        type: "GENERAL",
        title: "BRIEF",
        text: clean,
      });
    }
  }

  return result;
}

export function IntelPanel({
  query,
  setQuery,
  onSearch,
  isLoading,
  intelData,
  aiSummary,
  onOpenModal,
  mobileVisible = true,
}: IntelPanelProps) {
  const [intelMode, setIntelMode] = useState<IntelMode>("SIGINT");

  const discipline = extractDiscipline(intelData?.transcript);
  const parsedBullets = useMemo(() => parseAiBullets(aiSummary), [aiSummary]);

  return (
    <div
      className={`${
        mobileVisible ? "flex" : "hidden lg:flex"
      } flex-col rounded bg-[#0d1724] border border-[#243244] overflow-hidden flex-1`}
    >
      {/* Header with Mode Tabs */}
      <div className="px-3.5 py-2.5 bg-[#121e2c] border-b border-[#243244] flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <FileText size={14} className="text-[#3b82f6]" />
          <span className="text-[12px] font-semibold text-[#f2f5f8] tracking-wide">
            Intelligence Retrieval & Analysis
          </span>
          <span className="text-[10px] font-mono text-[#708096] bg-[#09111c] px-1.5 py-0.5 rounded border border-[#182332]">
            1,250 Reports
          </span>
        </div>

        {/* Mode Selector */}
        <div className="flex items-center p-0.5 rounded bg-[#09111c] border border-[#243244]">
          <button
            type="button"
            onClick={() => setIntelMode("SIGINT")}
            className={`px-2.5 py-1 rounded text-[10px] font-semibold tracking-wider transition-colors ${
              intelMode === "SIGINT"
                ? "bg-[#172333] text-[#f2f5f8] shadow-sm"
                : "text-[#708096] hover:text-[#a7b2c2]"
            }`}
          >
            SIGINT / RAG
          </button>
          <button
            type="button"
            onClick={() => setIntelMode("OSINT")}
            className={`px-2.5 py-1 rounded text-[10px] font-semibold tracking-wider transition-colors ${
              intelMode === "OSINT"
                ? "bg-[#172333] text-[#f2f5f8] shadow-sm"
                : "text-[#708096] hover:text-[#a7b2c2]"
            }`}
          >
            OSINT CHATTER
          </button>
        </div>
      </div>

      <div className="p-3.5 flex flex-col gap-3 flex-1 overflow-y-auto custom-scrollbar">
        {intelMode === "SIGINT" ? (
          <>
            {/* Search Input Box */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                onSearch();
              }}
              className="relative flex items-center"
            >
              <Search
                size={14}
                className="absolute left-3 text-[#708096] pointer-events-none"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search across 1,250 SIGINT, ELINT, and tactical border reports..."
                className="w-full pl-9 pr-20 py-2 rounded bg-[#09111c] border border-[#243244] text-[#f2f5f8] placeholder-[#708096] text-[12px] outline-none focus:border-[#3b82f6] transition-colors font-mono"
              />
              <button
                type="submit"
                disabled={isLoading}
                className="absolute right-1.5 px-2.5 py-1 rounded bg-[#172333] hover:bg-[#243244] text-[#a7b2c2] hover:text-[#f2f5f8] text-[11px] font-medium transition-colors flex items-center gap-1 border border-[#243244]"
              >
                {isLoading ? (
                  <Loader2 size={12} className="animate-spin text-[#3b82f6]" />
                ) : (
                  <span>Query</span>
                )}
              </button>
            </form>

            {/* Quick Suggestions Chips */}
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] text-[#708096] font-mono uppercase tracking-wider">
                Explore:
              </span>
              {QUICK_SUGGESTIONS.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => {
                    setQuery(sug);
                    onSearch(sug);
                  }}
                  className="px-2 py-0.5 rounded bg-[#09111c] hover:bg-[#172333] border border-[#1f2d3d] hover:border-[#3b82f6]/40 text-[#a7b2c2] hover:text-[#f2f5f8] text-[10px] font-mono transition-colors"
                >
                  {sug}
                </button>
              ))}
            </div>

            {/* Retrieved Intelligence Result */}
            {intelData ? (
              <div className="flex flex-col gap-2.5 p-3 rounded bg-[#09111c] border border-[#182332] text-xs">
                {/* Top Badges */}
                <div className="flex items-center justify-between flex-wrap gap-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-[11px] text-[#3b82f6] bg-[#3b82f6]/10 px-2 py-0.5 rounded border border-[#3b82f6]/30">
                      {intelData.id}
                    </span>
                    <span
                      className={`font-mono font-medium text-[10px] px-2 py-0.5 rounded border ${discipline.color}`}
                    >
                      {discipline.tag}
                    </span>
                    {intelData.score !== undefined && (
                      <span className="text-[10px] font-mono text-[#708096]">
                        Relevance: {Math.round(intelData.score * 100)}%
                      </span>
                    )}
                  </div>

                  {intelData.location && (
                    <div className="flex items-center gap-1 text-[11px] text-[#a7b2c2] font-mono">
                      <MapPin size={12} className="text-[#3b82f6]" />
                      <span>{intelData.location}</span>
                    </div>
                  )}
                </div>

                {/* Raw Transcript Content */}
                <div className="p-2.5 rounded bg-[#0d1724] border border-[#243244] text-[#f2f5f8] text-[12px] leading-relaxed">
                  &ldquo;{intelData.transcript}&rdquo;
                </div>

                {/* AI Military Intelligence Synthesis (Bulleted Single-Look Output) */}
                {parsedBullets.length > 0 && (
                  <div className="p-3 rounded bg-[#111927] border border-[#8b5cf6]/35 flex flex-col gap-2">
                    <div className="flex items-center justify-between border-b border-[#243244]/60 pb-1.5">
                      <span className="text-[10px] uppercase font-semibold text-[#a78bfa] font-mono tracking-wider flex items-center gap-1.5">
                        <ShieldAlert size={12} className="text-[#a78bfa]" />
                        <span>AI Tactical Intelligence Synthesis</span>
                      </span>
                      <span className="text-[9px] font-mono text-[#708096] px-1.5 py-0.2 rounded bg-[#09111c] border border-[#1f2d3d]">
                        Groq qwen/qwen3.8-27b
                      </span>
                    </div>

                    <div className="flex flex-col gap-2 pt-0.5">
                      {parsedBullets.map((bullet, idx) => {
                        const badgeStyle =
                          bullet.type === "SITUATION"
                            ? "bg-[#3b82f6]/20 text-[#60a5fa] border-[#3b82f6]/50"
                            : bullet.type === "EVIDENCE"
                            ? "bg-[#8b5cf6]/20 text-[#c084fc] border-[#8b5cf6]/50"
                            : bullet.type === "DIRECTIVE"
                            ? "bg-[#10b981]/20 text-[#34d399] border-[#10b981]/50"
                            : "bg-[#1f2d3d] text-[#a7b2c2] border-[#243244]";

                        return (
                          <div
                            key={idx}
                            className="flex items-start gap-2.5 text-[12px] leading-relaxed"
                          >
                            <span
                              className={`px-2 py-0.5 rounded border text-[9px] font-mono font-bold tracking-wider shrink-0 mt-0.5 ${badgeStyle}`}
                            >
                              {bullet.title}
                            </span>
                            <span className="text-[#e2e8f0] flex-1">
                              {bullet.text}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Modal View Button */}
                <button
                  type="button"
                  onClick={onOpenModal}
                  className="mt-1 w-full py-1.5 px-2.5 rounded bg-[#121e2c] hover:bg-[#172333] border border-[#243244] text-[#a7b2c2] hover:text-[#f2f5f8] text-[11px] font-medium flex items-center justify-center gap-1 transition-colors"
                >
                  <span>Inspect Full Evidence Chain</span>
                  <ExternalLink size={12} />
                </button>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-[#708096] text-[12px] border border-dashed border-[#182332] rounded">
                <Radio size={24} className="text-[#334358] mb-2" />
                <p className="font-medium text-[#a7b2c2] mb-1">
                  {aiSummary || "Awaiting Sector Query"}
                </p>
                <p className="text-[11px] text-[#708096] max-w-xs">
                  Search across 1,250 vectorized intercepts including FLIR thermals, micro-Doppler radar, geophone seismic sensors, and encrypted VHF comms.
                </p>
              </div>
            )}
          </>
        ) : (
          /* OSINT Chatter Mode */
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-[10px] font-semibold text-[#708096] uppercase tracking-wider mb-0.5">
              <span>Monitored Signals & Open-Source Chatter</span>
              <span className="font-mono text-[#10b981] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] animate-pulse" />
                SCANNING
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {OSINT_MOCK_FEED.map((item, idx) => {
                const badgeColor =
                  item.threat === "HIGH"
                    ? "text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/30"
                    : item.threat === "MED"
                    ? "text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30"
                    : "text-[#708096] bg-[#708096]/10 border-[#708096]/30";

                return (
                  <div
                    key={idx}
                    className="p-2.5 rounded bg-[#09111c] border border-[#182332] flex flex-col gap-1 text-[11px]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-[#a7b2c2] font-medium flex items-center gap-1.5">
                        <Compass size={12} className="text-[#3b82f6]" />
                        <span>{item.src}</span>
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[#708096] font-mono">
                          {item.time}
                        </span>
                        <span className={`px-1.5 py-0.2 rounded border text-[9px] font-semibold ${badgeColor}`}>
                          {item.threat}
                        </span>
                      </div>
                    </div>
                    <p className="text-[#f2f5f8] text-[11px] leading-relaxed">
                      {item.text}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
