"use client";

import React, { useState } from "react";
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
    <div className="fixed inset-0 z-[10000] bg-black/85 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div className="relative z-[10001] w-full max-w-6xl max-h-[85vh] sm:max-h-[90vh] rounded-t-xl sm:rounded bg-slate-950 border border-cyan-500/40 shadow-2xl overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-cyan-500/20">
          <div>
            <div className="text-cyan-300 font-mono text-sm tracking-widest">
              AEGIS // INCIDENT HISTORY
            </div>
            <div className="text-slate-500 text-xs font-mono mt-1">
              Historical threat assessments and intelligence records
            </div>
          </div>
          <button
            onClick={handleClose}
            className="text-slate-400 hover:text-white text-xl px-3"
          >
            ×
          </button>
        </div>

        <div className="px-5 py-3 border-b border-slate-800">
          <input
            value={historySearch}
            onChange={(e) => setHistorySearch(e.target.value)}
            placeholder="Search class, threat level, reasoning, location..."
            className="w-full bg-black border border-slate-700 px-3 py-2 text-xs font-mono text-white outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="p-10 text-center text-cyan-300 font-mono text-sm">
              LOADING HISTORICAL INTELLIGENCE...
            </div>
          ) : selectedHistory ? (
            <div className="p-6 space-y-5">
              <button
                onClick={() => setSelectedHistory(null)}
                className="text-xs font-mono text-cyan-400 hover:text-white"
              >
                ← BACK TO HISTORY
              </button>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="border border-slate-800 bg-black p-3">
                  <div className="text-[10px] text-slate-500 font-mono">THREAT LEVEL</div>
                  <div className="text-lg font-mono text-red-300 mt-1">
                    {selectedHistory.threat_level ||
                      selectedHistory.assessment?.threat_level ||
                      "UNKNOWN"}
                  </div>
                </div>

                <div className="border border-slate-800 bg-black p-3">
                  <div className="text-[10px] text-slate-500 font-mono">SCORE</div>
                  <div className="text-lg font-mono text-white mt-1">
                    {selectedHistory.score ?? selectedHistory.assessment?.score ?? "—"}
                  </div>
                </div>

                <div className="border border-slate-800 bg-black p-3">
                  <div className="text-[10px] text-slate-500 font-mono">CLASS</div>
                  <div className="text-lg font-mono text-cyan-300 mt-1">
                    {selectedHistory.threat_class ||
                      selectedHistory.class ||
                      String(selectedHistory.telemetry?.class || "UNKNOWN")}
                  </div>
                </div>

                <div className="border border-slate-800 bg-black p-3">
                  <div className="text-[10px] text-slate-500 font-mono">PREVIOUS</div>
                  <div className="text-lg font-mono text-white mt-1">
                    {selectedHistory.previous_incidents ??
                      selectedHistory.assessment?.previous_incidents ??
                      "—"}
                  </div>
                </div>
              </div>

              <div className="border border-slate-800 bg-black p-4">
                <div className="text-xs text-cyan-300 font-mono mb-2">AI ASSESSMENT</div>
                <div className="text-sm text-white leading-relaxed">
                  {selectedHistory.reasoning ||
                    selectedHistory.assessment?.reasoning ||
                    "No AI reasoning recorded."}
                </div>

                <div className="mt-4 text-xs text-slate-400 font-mono">RECOMMENDED ACTION</div>
                <div className="mt-1 text-sm text-slate-200">
                  {selectedHistory.recommended_action ||
                    selectedHistory.assessment?.recommended_action ||
                    "No recommendation recorded."}
                </div>
              </div>

              <div className="border border-slate-800 bg-black p-4">
                <div className="text-xs text-cyan-300 font-mono mb-3">EVENT TELEMETRY</div>
                <pre className="text-[11px] text-slate-300 whitespace-pre-wrap overflow-auto">
                  {JSON.stringify(
                    selectedHistory.telemetry || selectedHistory.payload || {},
                    null,
                    2
                  )}
                </pre>
              </div>

              {Array.isArray(selectedHistory.evidence) && selectedHistory.evidence.length > 0 && (
                <div className="border border-slate-800 bg-black p-4">
                  <div className="text-xs text-cyan-300 font-mono mb-3">RETRIEVED INTELLIGENCE</div>
                  <div className="space-y-3">
                    {selectedHistory.evidence.map((item: IntelRecord, index: number) => (
                      <div key={item.id || index} className="border border-slate-800 p-3">
                        <div className="flex justify-between gap-4">
                          <span className="text-xs text-cyan-300 font-mono">
                            {item.id || `INTEL-${index + 1}`}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {item.timestamp || ""}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 mt-2">
                          {item.location || "Unknown location"}
                        </div>
                        <div className="text-sm text-slate-200 mt-2 leading-relaxed">
                          {item.transcript || item.summary || item.text || "No transcript available."}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="border border-slate-800 bg-black p-4">
                <div className="text-xs text-cyan-300 font-mono mb-3">RAW ASSESSMENT RECORD</div>
                <pre className="text-[10px] text-slate-400 whitespace-pre-wrap overflow-auto">
                  {JSON.stringify(selectedHistory.assessment || {}, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-slate-900">
              {filteredRecords.map((record, index) => (
                <button
                  key={record.id || record.incident_id || index}
                  onClick={() => setSelectedHistory(record)}
                  className="w-full text-left px-5 py-4 hover:bg-cyan-950/20 transition"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="text-xs text-cyan-400 font-mono">
                        {record.incident_id || `INC-${record.id || index + 1}`}
                      </div>
                      <div className="text-xs text-white font-mono">
                        {record.threat_class ||
                          record.class ||
                          String(record.telemetry?.class || "UNKNOWN")}
                      </div>
                      <div className="text-xs text-slate-400">
                        {record.threat_level || record.assessment?.threat_level || "UNKNOWN"}
                      </div>
                    </div>
                    <div className="text-[10px] text-slate-500 font-mono">
                      {record.timestamp || record.created_at || ""}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-400 truncate">
                    {record.reasoning || record.assessment?.reasoning || "No AI summary available."}
                  </div>
                </button>
              ))}

              {filteredRecords.length === 0 && (
                <div className="p-10 text-center text-slate-500 font-mono text-xs">
                  NO HISTORICAL INCIDENTS FOUND
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
