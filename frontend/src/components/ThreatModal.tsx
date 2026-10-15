"use client";

import React from "react";
import { AlertTriangle, X } from "lucide-react";
import { ThreatAssessment, IntelRecord } from "../types/aegis";

export interface ThreatModalProps {
  isOpen: boolean;
  onClose: () => void;
  intelData: IntelRecord | null;
  threatAssessment: ThreatAssessment | null;
  aiSummary: string;
}

export function ThreatModal({
  isOpen,
  onClose,
  intelData,
  threatAssessment,
  aiSummary,
}: ThreatModalProps) {
  const [actionFeedback, setActionFeedback] = React.useState<string | null>(null);

  if (!isOpen) return null;

  const rawScore = threatAssessment?.score ?? 0;
  const scoreDisplay =
    rawScore <= 1 && rawScore > 0
      ? Math.round(rawScore * 100)
      : Math.round(rawScore);

  const isHighOrCritical =
    threatAssessment?.threat_level === "HIGH" ||
    threatAssessment?.threat_level === "CRITICAL";

  const handleAction = (message: string) => {
    setActionFeedback(message);
    setTimeout(() => {
      setActionFeedback(null);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        className="absolute inset-0 z-[10000] bg-black/80 backdrop-blur-md"
        onClick={onClose}
      />
      <div className="relative z-[10001] bg-slate-950 border border-fuchsia-900/50 rounded-t-xl sm:rounded shadow-[0_0_50px_rgba(217,70,239,0.15)] w-full max-w-2xl max-h-[85vh] sm:max-h-[90vh] overflow-hidden flex flex-col font-mono">
        <div className="bg-fuchsia-950/40 border-b border-fuchsia-900/50 p-4 flex justify-between items-center">
          <h2 className="text-fuchsia-400 font-bold tracking-widest flex items-center gap-2 text-sm">
            <AlertTriangle size={18} /> ACTION REQUIRED: INTEL #{intelData?.id || "UNKNOWN"}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-500 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {actionFeedback && (
          <div className="bg-emerald-950/80 border-b border-emerald-500/50 px-4 py-2.5 text-xs text-emerald-300 font-bold tracking-widest animate-pulse text-center">
            ✓ {actionFeedback}
          </div>
        )}

        <div className="p-6 flex flex-col gap-6 text-sm">
          {threatAssessment && (
            <div className="flex flex-wrap gap-2 sm:gap-4">
              <div
                className={`px-3 py-1 rounded border font-bold text-xs ${
                  isHighOrCritical
                    ? "bg-rose-950/50 border-rose-500 text-rose-400"
                    : "bg-yellow-950/50 border-yellow-500 text-yellow-400"
                }`}
              >
                THREAT LEVEL: {threatAssessment.threat_level || "UNKNOWN"}
              </div>
              <div className="px-3 py-1 rounded border border-cyan-900/50 bg-cyan-950/30 text-cyan-400 font-bold text-xs">
                THREAT SCORE: {scoreDisplay}/100
              </div>
              {threatAssessment.assessment_source === "rule-based" ||
              threatAssessment.reasoning?.includes("[Rule-based]") ||
              threatAssessment.reasoning?.includes("[DEGRADED") ||
              threatAssessment.reasoning?.includes("[OFFLINE") ? (
                <div className="px-3 py-1 rounded border border-amber-900/50 bg-amber-950/30 text-amber-400 font-bold text-xs flex items-center gap-1">
                  SOURCE: RULE-BASED (FALLBACK)
                </div>
              ) : (
                <div className="px-3 py-1 rounded border border-emerald-900/50 bg-emerald-950/30 text-emerald-400 font-bold text-xs flex items-center gap-1">
                  SOURCE: NEURAL LLM
                </div>
              )}
            </div>
          )}

          <div>
            <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">
              AI Tactical Assessment
            </div>
            <div className="bg-slate-900/50 border border-slate-800 p-4 rounded text-fuchsia-300 leading-relaxed font-mono">
              {threatAssessment?.reasoning || aiSummary}
              {threatAssessment?.recommended_action && (
                <div className="mt-2 pt-2 border-t border-fuchsia-900/30 text-cyan-400">
                  <span className="text-slate-500">RECOMMENDED ACTION:</span>{" "}
                  {threatAssessment.recommended_action}
                </div>
              )}
            </div>
          </div>

          <div>
            <div className="text-slate-500 text-xs mb-2 uppercase tracking-wider">
              Raw Transcript / Data
            </div>
            <div className="bg-black/50 border border-slate-800 p-4 rounded text-slate-300 font-mono text-xs max-h-32 overflow-y-auto custom-scrollbar">
              {intelData?.transcript || "No transcript available."}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-800 bg-slate-900/30 flex justify-end gap-3 sm:gap-4 flex-wrap">
          <button
            onClick={onClose}
            className="px-5 py-2 border border-slate-700 text-slate-400 hover:bg-slate-800 hover:text-white rounded transition-colors text-xs tracking-wider"
          >
            DISMISS
          </button>
          <button
            onClick={() => handleAction("LOCKDOWN PROTOCOL ENFORCED // PERIMETER ACCESS TERMINATED")}
            className="px-5 py-2 bg-rose-950 border border-rose-900 text-rose-400 hover:bg-rose-900 hover:text-rose-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(244,63,94,0.2)]"
          >
            INITIATE LOCKDOWN
          </button>
          <button
            onClick={() => handleAction("COMMAND CONFIRMED // QRT DISPATCH VECTOR INITIATED")}
            className="px-5 py-2 bg-cyan-950 border border-cyan-900 text-cyan-400 hover:bg-cyan-900 hover:text-cyan-100 rounded transition-colors text-xs tracking-wider font-bold shadow-[0_0_15px_rgba(6,182,212,0.2)]"
          >
            DEPLOY ASSETS
          </button>
        </div>
      </div>
    </div>
  );
}
