"use client";

import React from "react";
import { Video, Map as MapIcon, Terminal } from "lucide-react";

export type MobileTab = "optics" | "map" | "intel";

export interface MobileTabsProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
}

export function MobileTabs({ activeTab, onTabChange }: MobileTabsProps) {
  return (
    <div className="lg:hidden flex border-b border-slate-800 bg-slate-950 px-2 py-1.5 gap-1.5 z-40 sticky top-0">
      <button
        type="button"
        onClick={() => onTabChange("optics")}
        className={`flex-1 py-1.5 px-2 rounded text-[10px] font-mono font-bold tracking-wider flex items-center justify-center gap-1.5 transition-all ${
          activeTab === "optics"
            ? "bg-cyan-950/70 border border-cyan-500/80 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.25)]"
            : "bg-slate-900/50 border border-slate-800 text-slate-500 hover:text-slate-300"
        }`}
      >
        <Video size={13} />
        OPTICS
      </button>
      <button
        type="button"
        onClick={() => onTabChange("map")}
        className={`flex-1 py-1.5 px-2 rounded text-[10px] font-mono font-bold tracking-wider flex items-center justify-center gap-1.5 transition-all ${
          activeTab === "map"
            ? "bg-fuchsia-950/70 border border-fuchsia-500/80 text-fuchsia-400 shadow-[0_0_10px_rgba(217,70,239,0.25)]"
            : "bg-slate-900/50 border border-slate-800 text-slate-500 hover:text-slate-300"
        }`}
      >
        <MapIcon size={13} />
        MAP
      </button>
      <button
        type="button"
        onClick={() => onTabChange("intel")}
        className={`flex-1 py-1.5 px-2 rounded text-[10px] font-mono font-bold tracking-wider flex items-center justify-center gap-1.5 transition-all ${
          activeTab === "intel"
            ? "bg-rose-950/70 border border-rose-500/80 text-rose-400 shadow-[0_0_10px_rgba(244,63,94,0.25)]"
            : "bg-slate-900/50 border border-slate-800 text-slate-500 hover:text-slate-300"
        }`}
      >
        <Terminal size={13} />
        INTEL
      </button>
    </div>
  );
}
