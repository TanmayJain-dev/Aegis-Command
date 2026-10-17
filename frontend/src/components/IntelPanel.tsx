"use client";

import React, { useState } from "react";
import {
  Terminal,
  Search,
  Activity,
  AlertTriangle,
  ChevronRight,
  Radio,
  Map as MapIcon,
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

const OSINT_MOCK_FEED: ChatterItem[] = [
  {
    src: "Telegram / Unknown",
    time: "2m ago",
    text: "Movement spotted near Sector 4 checkpoints. Prepare the cargo.",
    threat: "HIGH",
  },
  {
    src: "DarkWeb Forum",
    time: "15m ago",
    text: "Looking for blindspots in perimeter CCTV-04.",
    threat: "MED",
  },
  {
    src: "Twitter / Open",
    time: "1h ago",
    text: "Loud noises heard coming from the northern ridge.",
    threat: "LOW",
  },
];

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

  return (
    <div
      className={`${
        mobileVisible ? "flex flex-1" : "hidden lg:flex"
      } flex-1 flex flex-col gap-4 border border-fuchsia-900/30 bg-slate-900/20 p-3 sm:p-4 rounded relative shadow-inner`}
    >
      <div className="flex justify-between items-center border-b border-slate-800 pb-4">
        <div className="text-xs uppercase tracking-widest text-fuchsia-400 font-bold flex items-center gap-2">
          <Terminal size={14} /> Intel Feed
        </div>
        <div className="flex bg-black border border-slate-700 rounded p-1">
          <button
            type="button"
            onClick={() => setIntelMode("SIGINT")}
            className={`px-4 py-1 rounded text-[10px] font-bold tracking-widest transition-colors ${
              intelMode === "SIGINT"
                ? "bg-fuchsia-950/50 text-fuchsia-400"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            SIGINT / RAG
          </button>
          <button
            type="button"
            onClick={() => setIntelMode("OSINT")}
            className={`px-4 py-1 rounded text-[10px] font-bold tracking-widest transition-colors ${
              intelMode === "OSINT"
                ? "bg-blue-950/50 text-blue-400"
                : "text-slate-500 hover:text-slate-300"
            }`}
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
              onKeyDown={(e) => e.key === "Enter" && onSearch()}
              placeholder="QUERY SIGINT DATABASE..."
              className="w-full rounded bg-black border border-slate-700 text-fuchsia-400 text-sm py-2.5 pl-10 pr-4 outline-none focus:border-fuchsia-500 focus:ring-1 focus:ring-fuchsia-500/50 placeholder-slate-600 transition-all font-mono shadow-inner"
            />
            {isLoading && (
              <div className="absolute right-3 top-3">
                <Activity className="animate-spin text-fuchsia-500" size={16} />
              </div>
            )}
          </div>

          {intelData ? (
            <div
              onClick={onOpenModal}
              className="mt-2 bg-slate-950 border border-fuchsia-900/50 hover:border-fuchsia-500/50 p-4 rounded cursor-pointer transition-all group hover:bg-slate-900/80 shadow-[0_4px_20px_rgba(0,0,0,0.5)]"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="text-rose-500" size={16} />
                  <span className="text-xs font-bold text-rose-500 tracking-widest">
                    INTEL MATCH DETECTED
                  </span>
                </div>
                <span className="text-[10px] text-fuchsia-500/70 font-bold">
                  ID: {intelData.id}
                </span>
              </div>

              <p className="text-slate-300 text-sm leading-relaxed border-l-2 border-fuchsia-500/50 pl-3">
                &quot;{intelData.transcript}&quot;
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
            {OSINT_MOCK_FEED.map((item, i) => (
              <div
                key={i}
                className="border-l-2 border-blue-500/50 pl-3 pb-4 border-b border-slate-800/50 last:border-b-0"
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] text-slate-500">
                    {item.src} &middot; {item.time}
                  </span>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded bg-black border ${
                      item.threat === "HIGH"
                        ? "text-rose-400 border-rose-900/50"
                        : item.threat === "MED"
                        ? "text-yellow-400 border-yellow-900/50"
                        : "text-slate-400 border-slate-700"
                    }`}
                  >
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
  );
}
