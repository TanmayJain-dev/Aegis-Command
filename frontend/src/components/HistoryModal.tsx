"use client";

import React, { useState } from "react";
import { Search, X, ArrowLeft, Clock } from "lucide-react";
import { AegisHistoryRecord, IntelRecord } from "../types/aegis";

export interface HistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  historyRecords: AegisHistoryRecord[];
  isLoading?: boolean;
}

export function HistoryModal({
  isOpen,
  onClose,
  historyRecords,
  isLoading = false,
}: HistoryModalProps) {
  const [historySearch, setHistorySearch] = useState("");
  const [selectedHistory, setSelectedHistory] = useState<AegisHistoryRecord | null>(null);

  if (!isOpen) return null;

  const handleClose = () => {
    setSelectedHistory(null);
    onClose();
  };

  const filteredRecords = historyRecords.filter((record) => {
    const q = historySearch.toLowerCase().trim();
    if (!q) return true;
    return JSON.stringify(record).toLowerCase().includes(q);
  });

  return (
    <div className="fixed inset-0 z-[10000] bg-[#08111d]/85 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="relative z-[10001] w-full max-w-5xl max-h-[85vh] sm:max-h-[90vh] rounded-t-xl sm:rounded-lg bg-[#0d1724] border border-[#243244] shadow-2xl overflow-hidden flex flex-col font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[#243244] bg-[#121e2c]">
          <div className="flex items-center gap-2.5">
            <Clock size={16} className="text-[#3b82f6]" />
            <div>
              <div className="text-[#f2f5f8] font-semibold text-sm tracking-wide">
                Incident History & Historical Intelligence
              </div>
              <div className="text-[#708096] text-xs mt-0.5">
                Archived threat telemetry, AI assessments, and correlated intercepts
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="text-[#708096] hover:text-[#f2f5f8] p-1 transition-colors"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Search Filter Bar */}
        <div className="px-5 py-2.5 border-b border-[#243244] bg-[#09111c] relative flex items-center">
          <Search size={14} className="absolute left-8 text-[#708096] pointer-events-none" />
          <input
            type="text"
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
            placeholder="Filter by class, threat level, reasoning, location, or ID..."
            className="w-full bg-[#0d1724] border border-[#243244] rounded pl-9 pr-3 py-1.5 text-xs text-[#f2f5f8] placeholder-[#708096] outline-none focus:border-[#3b82f6] transition-colors"
          />
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-auto custom-scrollbar">
          {isLoading ? (
            <div className="p-12 text-center text-[#a7b2c2] text-sm">
              Loading historical intelligence records...
            </div>
          ) : selectedHistory ? (
            /* Incident Detail View */
            <div className="p-6 space-y-5">
              <button
                type="button"
                onClick={() => setSelectedHistory(null)}
                className="text-xs text-[#3b82f6] hover:text-[#60a5fa] flex items-center gap-1.5 font-medium transition-colors"
              >
                <ArrowLeft size={14} />
                <span>Back to Incident Log</span>
              </button>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="border border-[#243244] bg-[#09111c] p-3 rounded">
                  <div className="text-[10px] text-[#708096] uppercase font-semibold">
                    Threat Level
                  </div>
                  <div className="text-base font-semibold text-[#ef4444] mt-1 font-mono">
                    {selectedHistory.threat_level ||
                      selectedHistory.assessment?.threat_level ||
                      "UNKNOWN"}
                  </div>
                </div>

                <div className="border border-[#243244] bg-[#09111c] p-3 rounded">
                  <div className="text-[10px] text-[#708096] uppercase font-semibold">
                    Score
                  </div>
                  <div className="text-base font-semibold text-[#f2f5f8] mt-1 font-mono">
                    {selectedHistory.score ?? selectedHistory.assessment?.score ?? "—"}
                  </div>
                </div>

                <div className="border border-[#243244] bg-[#09111c] p-3 rounded">
                  <div className="text-[10px] text-[#708096] uppercase font-semibold">
                    Target Class
                  </div>
                  <div className="text-base font-semibold text-[#3b82f6] mt-1 font-mono">
                    {selectedHistory.threat_class ||
                      selectedHistory.class ||
                      String(selectedHistory.telemetry?.class || "UNKNOWN")}
                  </div>
                </div>

                <div className="border border-[#243244] bg-[#09111c] p-3 rounded">
                  <div className="text-[10px] text-[#708096] uppercase font-semibold">
                    Prior Correlated
                  </div>
                  <div className="text-base font-semibold text-[#f2f5f8] mt-1 font-mono">
                    {selectedHistory.previous_incidents ??
                      selectedHistory.assessment?.previous_incidents ??
                      "—"}
                  </div>
                </div>
              </div>

              {/* Assessment Card */}
              <div className="border border-[#243244] bg-[#09111c] p-4 rounded flex flex-col gap-3">
                <div>
                  <div className="text-[11px] text-[#708096] font-semibold uppercase mb-1">
                    AI Tactical Assessment
                  </div>
                  <div className="text-sm text-[#f2f5f8] leading-relaxed">
                    {selectedHistory.reasoning ||
                      selectedHistory.assessment?.reasoning ||
                      "No AI reasoning recorded."}
                  </div>
                </div>

                <div>
                  <div className="text-[11px] text-[#708096] font-semibold uppercase mb-1">
                    Recommended Operational Action
                  </div>
                  <div className="text-sm text-[#3b82f6] leading-relaxed font-medium">
                    {selectedHistory.recommended_action ||
                      selectedHistory.assessment?.recommended_action ||
                      "No recommendation recorded."}
                  </div>
                </div>
              </div>

              {/* Event Telemetry Data */}
              <div className="border border-[#243244] bg-[#09111c] p-4 rounded">
                <div className="text-[11px] text-[#708096] font-semibold uppercase mb-2">
                  Event Telemetry
                </div>
                <pre className="text-[11px] text-[#a7b2c2] font-mono whitespace-pre-wrap overflow-auto bg-[#0d1724] p-3 rounded border border-[#182332]">
                  {JSON.stringify(
                    selectedHistory.telemetry || selectedHistory.payload || {},
                    null,
                    2
                  )}
                </pre>
              </div>

              {/* Evidence Array if available */}
              {Array.isArray(selectedHistory.evidence) && selectedHistory.evidence.length > 0 && (
                <div className="border border-[#243244] bg-[#09111c] p-4 rounded">
                  <div className="text-[11px] text-[#708096] font-semibold uppercase mb-3">
                    Retrieved Intelligence Intercepts
                  </div>
                  <div className="space-y-2.5">
                    {selectedHistory.evidence.map((item: IntelRecord, index: number) => (
                      <div
                        key={item.id || index}
                        className="border border-[#182332] bg-[#0d1724] p-3 rounded text-xs"
                      >
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="font-mono font-semibold text-[#3b82f6]">
                            {item.id || `INTEL-${index + 1}`}
                          </span>
                          <span className="text-[#708096] font-mono">
                            {item.timestamp || ""}
                          </span>
                        </div>
                        {item.location && (
                          <div className="text-[#708096] text-[11px] mt-1">
                            Location: {item.location}
                          </div>
                        )}
                        <div className="text-[#f2f5f8] text-[12px] mt-1.5 leading-relaxed">
                          {item.transcript || item.summary || item.text || "No transcript available."}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Records List View */
            <div className="divide-y divide-[#182332]">
              {filteredRecords.map((record, index) => {
                const threatLvl = (
                  record.threat_level ||
                  record.assessment?.threat_level ||
                  "UNKNOWN"
                ).toUpperCase();

                const isCritOrHigh = threatLvl === "CRITICAL" || threatLvl === "HIGH";
                const isMedium = threatLvl === "MED" || threatLvl === "MEDIUM";

                const badgeColor = isCritOrHigh
                  ? "text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/30"
                  : isMedium
                  ? "text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30"
                  : "text-[#10b981] bg-[#10b981]/10 border-[#10b981]/30";

                return (
                  <button
                    key={record.id || record.incident_id || index}
                    type="button"
                    onClick={() => setSelectedHistory(record)}
                    className="w-full text-left px-5 py-3 hover:bg-[#121e2c] transition-colors flex flex-col gap-1.5"
                  >
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-[#3b82f6] font-mono font-semibold">
                          {record.incident_id || `INC-${record.id || index + 1}`}
                        </span>
                        <span className="text-xs text-[#f2f5f8] font-medium">
                          {record.threat_class ||
                            record.class ||
                            String(record.telemetry?.class || "UNKNOWN")}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold font-mono ${badgeColor}`}>
                          {threatLvl}
                        </span>
                      </div>
                      <div className="text-[11px] text-[#708096] font-mono">
                        {record.timestamp || record.created_at || ""}
                      </div>
                    </div>
                    <div className="text-xs text-[#a7b2c2] truncate">
                      {record.reasoning || record.assessment?.reasoning || "No AI summary available."}
                    </div>
                  </button>
                );
              })}

              {filteredRecords.length === 0 && (
                <div className="p-12 text-center text-[#708096] text-xs">
                  No historical incidents matched the filter query.
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
