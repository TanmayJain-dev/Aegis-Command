"use client";

import React, { useState } from "react";
import { X, ShieldAlert, Bot, CheckCircle } from "lucide-react";
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
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);

  if (!isOpen) return null;

  const rawScore = threatAssessment?.score ?? 0;
  const scoreDisplay =
    rawScore <= 1 && rawScore > 0
      ? Math.round(rawScore * 100)
      : Math.round(rawScore);

  const level = (threatAssessment?.threat_level || "UNKNOWN").toUpperCase();
  const isHighOrCritical = level === "HIGH" || level === "CRITICAL";
  const isMed = level === "MED" || level === "MEDIUM";

  const levelClass = isHighOrCritical
    ? "bg-[#ef4444]/15 border-[#ef4444]/40 text-[#ef4444]"
    : isMed
    ? "bg-[#f59e0b]/15 border-[#f59e0b]/40 text-[#f59e0b]"
    : "bg-[#10b981]/15 border-[#10b981]/40 text-[#10b981]";

  const isRuleBased =
    threatAssessment?.assessment_source === "rule-based" ||
    threatAssessment?.reasoning?.includes("[Rule-based]") ||
    threatAssessment?.reasoning?.includes("[DEGRADED") ||
    threatAssessment?.reasoning?.includes("[OFFLINE");

  const handleAction = (message: string) => {
    setActionFeedback(message);
    setTimeout(() => {
      setActionFeedback(null);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-end sm:items-center justify-center p-0 sm:p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-[#08111d]/85 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal Dialog */}
      <div className="relative z-[10001] bg-[#0d1724] border border-[#243244] rounded-t-xl sm:rounded-lg shadow-2xl w-full max-w-2xl max-h-[85vh] sm:max-h-[90vh] overflow-hidden flex flex-col font-sans">
        {/* Header */}
        <div className="bg-[#121e2c] border-b border-[#243244] px-5 py-3.5 flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <ShieldAlert size={18} className="text-[#3b82f6]" />
            <h2 className="text-[#f2f5f8] font-semibold text-sm tracking-wide">
              Action Protocol · Incident #{intelData?.id || "UNKNOWN"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[#708096] hover:text-[#f2f5f8] transition-colors p-1"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Feedback Banner */}
        {actionFeedback && (
          <div className="bg-[#10b981]/15 border-b border-[#10b981]/30 px-4 py-2 text-xs text-[#10b981] font-medium flex items-center justify-center gap-2">
            <CheckCircle size={14} />
            <span>{actionFeedback}</span>
          </div>
        )}

        {/* Content Body */}
        <div className="p-5 flex flex-col gap-4 text-xs overflow-y-auto custom-scrollbar">
          {/* Status Metrics */}
          {threatAssessment && (
            <div className="flex flex-wrap gap-2.5">
              <div
                className={`px-3 py-1 rounded border font-semibold text-xs ${levelClass}`}
              >
                THREAT LEVEL: {level}
              </div>
              <div className="px-3 py-1 rounded border border-[#243244] bg-[#121e2c] text-[#f2f5f8] font-semibold text-xs font-mono">
                SCORE: {scoreDisplay}/100
              </div>
              <div className="px-3 py-1 rounded border border-[#8b5cf6]/40 bg-[#8b5cf6]/10 text-[#a78bfa] font-medium text-xs font-mono flex items-center gap-1.5">
                <Bot size={12} />
                <span>SOURCE: {isRuleBased ? "DETERMINISTIC RULE" : "NEURAL LLM"}</span>
              </div>
            </div>
          )}

          {/* AI Assessment */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center gap-2 text-[#708096] text-[11px] font-semibold uppercase tracking-wider">
              <span>AI Tactical Assessment</span>
              <span className="text-[#8b5cf6] text-[10px] font-mono lowercase">(model-generated)</span>
            </div>
            <div className="bg-[#09111c] border border-[#182332] p-3.5 rounded text-[#f2f5f8] text-[13px] leading-relaxed">
              <p>{threatAssessment?.reasoning || aiSummary}</p>

              {threatAssessment?.recommended_action && (
                <div className="mt-3 pt-2.5 border-t border-[#182332] text-[#3b82f6] text-[12px]">
                  <span className="text-[#708096] font-semibold uppercase text-[10px] block mb-1">
                    Recommended Operational Action:
                  </span>
                  <p className="text-[#f2f5f8] font-medium">
                    {threatAssessment.recommended_action}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Observed Sensor Data / Raw Transcript */}
          <div className="flex flex-col gap-1.5">
            <div className="text-[#708096] text-[11px] font-semibold uppercase tracking-wider">
              Intercepted Intel / Raw Transcript
            </div>
            <div className="bg-[#09111c] border border-[#182332] p-3 rounded text-[#a7b2c2] text-[12px] leading-relaxed max-h-32 overflow-y-auto custom-scrollbar font-mono">
              {intelData?.transcript || "No transcript evidence associated with this incident."}
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-[#243244] bg-[#121e2c] flex justify-end gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-[#243244] text-[#a7b2c2] hover:bg-[#172333] hover:text-[#f2f5f8] rounded text-xs transition-colors"
          >
            Dismiss
          </button>
          <button
            type="button"
            onClick={() => handleAction("Lockdown protocol recorded (demonstration mode)")}
            className="px-4 py-2 bg-[#ef4444]/15 border border-[#ef4444]/40 text-[#ef4444] hover:bg-[#ef4444]/25 rounded text-xs font-semibold transition-colors"
          >
            Simulate Lockdown
          </button>
          <button
            type="button"
            onClick={() => handleAction("Asset dispatch protocol recorded (demonstration mode)")}
            className="px-4 py-2 bg-[#3b82f6] hover:bg-[#2563eb] text-white rounded text-xs font-semibold transition-colors"
          >
            Deploy Assets (Demo)
          </button>
        </div>
      </div>
    </div>
  );
}
