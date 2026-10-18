"use client";

import React from "react";
import { ShieldAlert, Bot, ChevronRight, Zap } from "lucide-react";
import { ThreatAssessment, IntelRecord } from "../../types/aegis";

export interface ThreatAssessmentPanelProps {
  assessment: ThreatAssessment | null;
  intelData: IntelRecord | null;
  onOpenActionModal: () => void;
  onSimulateDrill?: () => void;
}

export function ThreatAssessmentPanel({
  assessment,
  intelData,
  onOpenActionModal,
  onSimulateDrill,
}: ThreatAssessmentPanelProps) {
  const level = (assessment?.threat_level || "LOW").toUpperCase();
  const rawScore = assessment?.score ?? 0;
  const score = rawScore <= 1 && rawScore > 0 ? Math.round(rawScore * 100) : Math.round(rawScore);

  const isCritical = level === "CRITICAL";
  const isHigh = level === "HIGH";
  const isMed = level === "MED" || level === "MEDIUM";

  const levelColor = isCritical || isHigh
    ? "text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/30"
    : isMed
    ? "text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/30"
    : "text-[#10b981] bg-[#10b981]/10 border-[#10b981]/30";

  const isRuleBased =
    assessment?.assessment_source === "rule-based" ||
    assessment?.reasoning?.includes("[Rule-based]") ||
    assessment?.reasoning?.includes("[DEGRADED") ||
    assessment?.reasoning?.includes("[OFFLINE");

  return (
    <div className="flex flex-col rounded bg-[#0d1724] border border-[#243244] overflow-hidden">
      {/* Header */}
      <div className="px-3.5 py-2.5 bg-[#121e2c] border-b border-[#243244] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert size={15} className="text-[#3b82f6]" />
          <span className="text-[13px] font-semibold text-[#f2f5f8] tracking-wide">
            Incident Assessment
          </span>
        </div>

        {/* AI GENERATED BADGE */}
        <div className="flex items-center gap-1 px-2 py-0.5 rounded border border-[#8b5cf6]/40 bg-[#8b5cf6]/10 text-[#a78bfa] text-[10px] font-medium font-mono">
          <Bot size={11} />
          <span>{isRuleBased ? "DETERMINISTIC HEURISTIC" : "AI GENERATED"}</span>
        </div>
      </div>

      <div className="p-3.5 flex flex-col gap-3.5">
        {/* Threat Level & Score Bar */}
        <div className="flex items-center justify-between gap-3 p-2.5 rounded bg-[#09111c] border border-[#182332]">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-[#708096]">THREAT LEVEL:</span>
            <span className={`px-2 py-0.5 rounded border text-[11px] font-semibold font-mono ${levelColor}`}>
              {level}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium text-[#708096]">THREAT SCORE:</span>
            <span className="font-mono text-[13px] font-bold text-[#f2f5f8]">
              {score > 0 ? `${score}%` : "—"}
            </span>
          </div>
        </div>

        {/* AI Reasoning Section */}
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[#a7b2c2]">
            <span>Automated Tactical Assessment</span>
            {assessment?.previous_incidents !== undefined && assessment.previous_incidents > 0 && (
              <span className="text-[10px] text-[#708096] font-mono lowercase">
                {assessment.previous_incidents} prior matches
              </span>
            )}
          </div>

          <div className="p-2.5 rounded bg-[#09111c] border border-[#182332] text-[12px] leading-relaxed text-[#f2f5f8]">
            {assessment?.reasoning ? (
              <p>{assessment.reasoning}</p>
            ) : (
              <p className="text-[#708096] italic">
                Awaiting active threat observation from telemetry stream...
              </p>
            )}
          </div>
        </div>

        {/* Recommended Action */}
        {assessment?.recommended_action && (
          <div className="flex flex-col gap-1.5">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-[#a7b2c2]">
              Recommended Response Protocol
            </div>
            <div className="p-2.5 rounded bg-[#121e2c] border border-[#3b82f6]/30 text-[12px] text-[#f2f5f8] leading-relaxed border-l-2 border-l-[#3b82f6]">
              {assessment.recommended_action}
            </div>
          </div>
        )}

        {/* Correlated Evidence Block */}
        {intelData && (
          <div className="flex flex-col gap-1.5 pt-1 border-t border-[#182332]">
            <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[#708096]">
              <span>Correlated SIGINT Evidence</span>
              <span className="font-mono text-[10px] text-[#3b82f6]">{intelData.id}</span>
            </div>
            <div className="p-2.5 rounded bg-[#09111c] border border-[#182332] text-[11px] text-[#a7b2c2] leading-relaxed">
              <p className="line-clamp-2 italic">&ldquo;{intelData.transcript}&rdquo;</p>
              {intelData.location && (
                <div className="mt-1 text-[10px] text-[#708096] font-mono">
                  Location: {intelData.location}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="pt-1 flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenActionModal}
            className="flex-1 py-2 px-3 rounded bg-[#3b82f6] hover:bg-[#2563eb] text-white text-[12px] font-medium flex items-center justify-center gap-1.5 transition-colors shadow-sm"
          >
            <span>Review Incident Action Protocols</span>
            <ChevronRight size={14} />
          </button>
          {onSimulateDrill && (
            <button
              type="button"
              onClick={onSimulateDrill}
              className="py-2 px-3 rounded border border-[#ef4444]/40 bg-[#ef4444]/10 hover:bg-[#ef4444]/20 text-[#f87171] text-[12px] font-medium flex items-center gap-1 transition-colors"
              title="Trigger simulated tactical drill"
            >
              <Zap size={13} />
              <span>Drill</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
