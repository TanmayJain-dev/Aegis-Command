"use client";

import React, { useState, useEffect } from "react";
import { Zap, Clock, RefreshCw, Menu } from "lucide-react";

export interface TopBarProps {
  connectionStatus: "LIVE" | "DEGRADED" | "OFFLINE";
  socketReady: boolean;
  isProbingBackend: boolean;
  onProbeBackend: () => void;
  liteMode: boolean;
  onToggleLiteMode: () => void;
  onOpenHistory: () => void;
  activeFeedLabel?: string;
  onToggleSidebarMobile?: () => void;
}

export function TopBar({
  connectionStatus,
  socketReady,
  isProbingBackend,
  onProbeBackend,
  liteMode,
  onToggleLiteMode,
  onOpenHistory,
  activeFeedLabel,
  onToggleSidebarMobile,
}: TopBarProps) {
  const [currentTimeStr, setCurrentTimeStr] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTimeStr(
        now.toISOString().slice(0, 19).replace("T", " ") + " UTC"
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-12 bg-[#0d1724] border-b border-[#243244] px-4 flex items-center justify-between z-20 flex-shrink-0 select-none">
      <div className="flex items-center gap-3">
        {onToggleSidebarMobile && (
          <button
            type="button"
            onClick={onToggleSidebarMobile}
            className="md:hidden p-1.5 rounded text-[#a7b2c2] hover:text-[#f2f5f8] hover:bg-[#172333]"
            aria-label="Toggle navigation sidebar"
          >
            <Menu size={16} />
          </button>
        )}

        <div className="flex items-center gap-2">
          <span className="text-[12px] font-semibold text-[#f2f5f8] tracking-wide">
            Operation Alpha
          </span>
          <span className="text-[#708096] text-xs">/</span>
          <span className="text-[12px] text-[#a7b2c2] font-medium hidden sm:inline">
            Tactical Surveillance & Response Console
          </span>
          {activeFeedLabel && (
            <>
              <span className="text-[#708096] text-xs hidden sm:inline">/</span>
              <span className="text-[11px] font-mono text-[#3b82f6] hidden sm:inline font-medium">
                {activeFeedLabel}
              </span>
            </>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 sm:gap-3">
        {/* UTC Clock */}
        <div className="hidden lg:flex items-center gap-1.5 text-[11px] font-mono text-[#708096] px-2 py-1">
          <Clock size={12} className="text-[#708096]" />
          <span>{currentTimeStr || "--:--:-- UTC"}</span>
        </div>

        {/* System Operational Status Pill */}
        <div
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-medium font-mono ${
            connectionStatus === "LIVE"
              ? "bg-[#10b981]/10 border-[#10b981]/30 text-[#10b981]"
              : connectionStatus === "DEGRADED"
              ? "bg-[#f59e0b]/10 border-[#f59e0b]/30 text-[#f59e0b]"
              : "bg-[#ef4444]/10 border-[#ef4444]/30 text-[#ef4444]"
          }`}
          title={`Autonomous Engine Connection: ${connectionStatus} (WebSocket: ${socketReady ? "Active" : "Reconnecting"})`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              connectionStatus === "LIVE"
                ? "bg-[#10b981]"
                : connectionStatus === "DEGRADED"
                ? "bg-[#f59e0b]"
                : "bg-[#ef4444]"
            }`}
          />
          <span>{connectionStatus === "LIVE" ? "System Operational" : connectionStatus}</span>
        </div>

        {/* Retry probe if degraded or offline */}
        {connectionStatus !== "LIVE" && (
          <button
            type="button"
            onClick={onProbeBackend}
            disabled={isProbingBackend}
            className="px-2 py-1 border border-[#243244] bg-[#121e2c] hover:bg-[#172333] rounded text-[11px] text-[#a7b2c2] hover:text-[#f2f5f8] flex items-center gap-1 transition-colors"
            title="Probe backend health status"
          >
            <RefreshCw size={11} className={isProbingBackend ? "animate-spin" : ""} />
            <span className="hidden sm:inline">Retry</span>
          </button>
        )}

        {/* Lite Mode Toggle */}
        <button
          type="button"
          onClick={onToggleLiteMode}
          className={`px-2 py-1 text-[11px] font-medium rounded border transition-colors flex items-center gap-1 ${
            liteMode
              ? "bg-[#f59e0b]/15 border-[#f59e0b]/40 text-[#f59e0b]"
              : "bg-[#121e2c] border-[#243244] text-[#a7b2c2] hover:text-[#f2f5f8]"
          }`}
          title="Toggle low-power Lite Mode for reduced GPU usage"
          aria-label="Toggle Lite Mode"
        >
          <Zap size={11} className={liteMode ? "text-[#f59e0b]" : "text-[#708096]"} />
          <span className="hidden sm:inline">Lite:</span>
          <span>{liteMode ? "On" : "Off"}</span>
        </button>

        {/* History Modal Trigger */}
        <button
          type="button"
          onClick={onOpenHistory}
          className="px-2.5 py-1 text-[11px] font-medium rounded border border-[#243244] bg-[#121e2c] hover:bg-[#172333] text-[#a7b2c2] hover:text-[#f2f5f8] transition-colors"
        >
          History
        </button>
      </div>
    </header>
  );
}
