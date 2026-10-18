"use client";

import React from "react";
import { Video, Map as MapIcon, FileText } from "lucide-react";

export type MobileTab = "optics" | "map" | "intel";

export interface MobileTabsProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
}

export function MobileTabs({ activeTab, onTabChange }: MobileTabsProps) {
  return (
    <div className="lg:hidden flex border-b border-[#243244] bg-[#0d1724] px-2 py-1.5 gap-1.5 z-30 sticky top-0">
      <button
        type="button"
        onClick={() => onTabChange("optics")}
        className={`flex-1 py-1.5 px-2 rounded text-[11px] font-medium tracking-wide flex items-center justify-center gap-1.5 transition-colors ${
          activeTab === "optics"
            ? "bg-[#172333] border border-[#3b82f6]/50 text-[#f2f5f8] shadow-sm font-semibold"
            : "bg-[#09111c] border border-[#182332] text-[#708096] hover:text-[#a7b2c2]"
        }`}
      >
        <Video size={13} className={activeTab === "optics" ? "text-[#3b82f6]" : "text-[#708096]"} />
        <span>Optics Feed</span>
      </button>

      <button
        type="button"
        onClick={() => onTabChange("map")}
        className={`flex-1 py-1.5 px-2 rounded text-[11px] font-medium tracking-wide flex items-center justify-center gap-1.5 transition-colors ${
          activeTab === "map"
            ? "bg-[#172333] border border-[#3b82f6]/50 text-[#f2f5f8] shadow-sm font-semibold"
            : "bg-[#09111c] border border-[#182332] text-[#708096] hover:text-[#a7b2c2]"
        }`}
      >
        <MapIcon size={13} className={activeTab === "map" ? "text-[#3b82f6]" : "text-[#708096]"} />
        <span>Tactical Map</span>
      </button>

      <button
        type="button"
        onClick={() => onTabChange("intel")}
        className={`flex-1 py-1.5 px-2 rounded text-[11px] font-medium tracking-wide flex items-center justify-center gap-1.5 transition-colors ${
          activeTab === "intel"
            ? "bg-[#172333] border border-[#3b82f6]/50 text-[#f2f5f8] shadow-sm font-semibold"
            : "bg-[#09111c] border border-[#182332] text-[#708096] hover:text-[#a7b2c2]"
        }`}
      >
        <FileText size={13} className={activeTab === "intel" ? "text-[#3b82f6]" : "text-[#708096]"} />
        <span>Intelligence</span>
      </button>
    </div>
  );
}
