"use client";

import React from "react";
import {
  Shield,
  LayoutDashboard,
  Video,
  AlertTriangle,
  Compass,
  FileText,
  Clock,
  Upload,
  Zap,
  Layers,
} from "lucide-react";
import { FeedManifestItem } from "../../lib/feeds";

export type NavSection =
  | "overview"
  | "live"
  | "incidents"
  | "map"
  | "intel"
  | "evidence"
  | "history";

export interface AppSidebarProps {
  activeSection: NavSection;
  onSelectSection: (section: NavSection) => void;
  feeds: FeedManifestItem[];
  activeFeedId: string;
  onSelectFeed: (feedId: string) => void;
  onOpenUploadModal: () => void;
  onSimulateDrill: () => void;
  onOpenHistoryModal: () => void;
  systemInfo: {
    fps: string;
    model: string;
    encryption: string;
    coordinates?: [number, number] | null;
  };
}

const NAV_ITEMS: { id: NavSection; label: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "live", label: "Live Operations", icon: Video },
  { id: "incidents", label: "Incidents", icon: AlertTriangle },
  { id: "map", label: "Tactical Map", icon: Compass },
  { id: "intel", label: "Intelligence", icon: FileText },
  { id: "evidence", label: "Evidence", icon: Layers },
  { id: "history", label: "History", icon: Clock },
];

export function AppSidebar({
  activeSection,
  onSelectSection,
  feeds,
  activeFeedId,
  onSelectFeed,
  onOpenUploadModal,
  onSimulateDrill,
  onOpenHistoryModal,
  systemInfo,
}: AppSidebarProps) {
  const handleNavClick = (sectionId: NavSection) => {
    if (sectionId === "history") {
      onOpenHistoryModal();
    } else {
      onSelectSection(sectionId);
    }
  };

  return (
    <aside className="w-[210px] 2xl:w-[230px] flex-shrink-0 bg-[#0d1724] border-r border-[#243244] flex flex-col justify-between select-none">
      <div className="flex flex-col">
        {/* Brand */}
        <div className="px-4 py-4 border-b border-[#243244]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded bg-[#172333] border border-[#243244] flex items-center justify-center text-[#3b82f6] flex-shrink-0">
              <Shield size={16} />
            </div>
            <div className="flex flex-col">
              <span className="text-[13px] font-semibold text-[#f2f5f8] tracking-wider leading-none">
                AEGIS COMMAND
              </span>
              <span className="text-[9px] font-medium text-[#708096] tracking-widest mt-1">
                SURVEILLANCE & INTEL
              </span>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="py-2.5 px-2">
          <div className="px-2.5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-[#708096]">
            Navigation
          </div>
          <nav className="flex flex-col gap-0.5" aria-label="Main Navigation">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = activeSection === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleNavClick(item.id)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded text-[12px] font-medium transition-colors text-left ${
                    isActive
                      ? "bg-[#172333] text-[#f2f5f8] border-l-2 border-[#3b82f6]"
                      : "text-[#a7b2c2] hover:bg-[#121e2c] hover:text-[#f2f5f8]"
                  }`}
                >
                  <Icon
                    size={14}
                    className={isActive ? "text-[#3b82f6]" : "text-[#708096]"}
                  />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Sources Section */}
        <div className="pt-2 pb-2 px-2 border-t border-[#182332]">
          <div className="px-2.5 pb-1.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider text-[#708096]">
            <span>Feed Sources</span>
            <span className="font-mono text-[9px] text-[#3b82f6]">
              {feeds.length} LIVE
            </span>
          </div>

          <div className="flex flex-col gap-1">
            {feeds.map((feed) => {
              const isSelected = activeFeedId === feed.id;
              return (
                <button
                  key={feed.id}
                  type="button"
                  onClick={() => onSelectFeed(feed.id)}
                  className={`w-full text-left p-2 rounded text-[11px] transition-colors border ${
                    isSelected
                      ? "bg-[#172333] border-[#3b82f6]/50 text-[#f2f5f8]"
                      : "bg-[#09111c] border-[#182332] text-[#a7b2c2] hover:border-[#243244] hover:text-[#f2f5f8]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-medium truncate">{feed.label}</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] flex-shrink-0" />
                  </div>
                  <div className="text-[10px] text-[#708096] truncate mt-0.5">
                    {feed.sensor || "EO/IR Optronics"}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="mt-2.5 flex flex-col gap-1.5">
            <button
              type="button"
              onClick={onOpenUploadModal}
              className="w-full py-1.5 px-2 rounded border border-[#243244] bg-[#121e2c] hover:bg-[#172333] text-[#a7b2c2] hover:text-[#f2f5f8] text-[11px] font-medium flex items-center justify-center gap-1.5 transition-colors"
            >
              <Upload size={12} className="text-[#3b82f6]" />
              <span>Import Custom Feed</span>
            </button>

            <button
              type="button"
              onClick={onSimulateDrill}
              className="w-full py-1.5 px-2 rounded border border-[#ef4444]/40 bg-[#ef4444]/10 hover:bg-[#ef4444]/20 text-[#f87171] text-[11px] font-medium flex items-center justify-center gap-1.5 transition-colors"
            >
              <Zap size={12} />
              <span>Simulate Drill Alert</span>
            </button>
          </div>
        </div>
      </div>

      {/* System Telemetry Metadata */}
      <div className="p-3 border-t border-[#182332] bg-[#09111c]/60 text-[10px] font-mono text-[#708096]">
        <div className="flex items-center justify-between py-0.5">
          <span>MODEL:</span>
          <span className="text-[#a7b2c2] font-semibold truncate max-w-[110px]">
            {systemInfo.model || "yolov8m.pt"}
          </span>
        </div>
        <div className="flex items-center justify-between py-0.5">
          <span>FRAME RATE:</span>
          <span className="text-[#a7b2c2]">{systemInfo.fps} FPS</span>
        </div>
        <div className="flex items-center justify-between py-0.5">
          <span>ENCRYPTION:</span>
          <span className="text-[#a7b2c2]">{systemInfo.encryption}</span>
        </div>
        <div className="flex items-center justify-between py-0.5">
          <span>SECTOR:</span>
          <span className="text-[#a7b2c2]">
            {systemInfo.coordinates
              ? `${systemInfo.coordinates[0].toFixed(2)}°N, ${systemInfo.coordinates[1].toFixed(2)}°E`
              : "31.45°N, 74.92°E"}
          </span>
        </div>
      </div>
    </aside>
  );
}
