"use client";

import React from "react";
import { ListFilter } from "lucide-react";
import { DrawableDetection } from "../../lib/timeline";

export interface DetectionTimelineProps {
  recentDetections: Array<{
    time: number;
    detection: DrawableDetection;
    source: string;
  }>;
  onSelectDetectionTime?: (time: number) => void;
}

export function DetectionTimeline({
  recentDetections,
  onSelectDetectionTime,
}: DetectionTimelineProps) {
  const formatTime = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 10);
    return `${mins.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}.${ms}`;
  };

  return (
    <div className="flex flex-col rounded bg-[#0d1724] border border-[#243244] overflow-hidden">
      <div className="px-3.5 py-2.5 bg-[#121e2c] border-b border-[#243244] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ListFilter size={14} className="text-[#3b82f6]" />
          <span className="text-[12px] font-semibold text-[#f2f5f8] tracking-wide">
            Recent Detections
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px] text-[#708096]">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" />
            Personnel
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#3b82f6]" />
            Vehicle
          </span>
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#ef4444]" />
            Critical Alert
          </span>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[160px] custom-scrollbar">
        <table className="w-full text-left border-collapse text-[11px] font-mono">
          <thead>
            <tr className="border-b border-[#182332] bg-[#09111c] text-[#708096] text-[10px] uppercase tracking-wider">
              <th className="py-1.5 px-3 font-semibold">Time</th>
              <th className="py-1.5 px-3 font-semibold">Class</th>
              <th className="py-1.5 px-3 font-semibold">Confidence</th>
              <th className="py-1.5 px-3 font-semibold">Telemetry</th>
              <th className="py-1.5 px-3 font-semibold">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#182332]">
            {recentDetections.length > 0 ? (
              recentDetections.slice(0, 8).map((item, idx) => {
                const det = item.detection;
                const isPersonnel = det.class === "person";
                const isThreat = det.class === "truck" || det.class === "drone";
                const badgeColor = isPersonnel
                  ? "text-[#10b981] bg-[#10b981]/10 border-[#10b981]/30"
                  : isThreat
                  ? "text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/30"
                  : "text-[#3b82f6] bg-[#3b82f6]/10 border-[#3b82f6]/30";

                return (
                  <tr
                    key={`${item.time}-${det.id}-${idx}`}
                    onClick={() => onSelectDetectionTime?.(item.time)}
                    className="hover:bg-[#121e2c] cursor-pointer transition-colors"
                  >
                    <td className="py-1.5 px-3 text-[#f2f5f8] whitespace-nowrap">
                      {formatTime(item.time)}
                    </td>
                    <td className="py-1.5 px-3 whitespace-nowrap">
                      <span className={`px-1.5 py-0.5 rounded border text-[10px] font-semibold ${badgeColor}`}>
                        {det.class}
                      </span>
                    </td>
                    <td className="py-1.5 px-3 text-[#a7b2c2] whitespace-nowrap">
                      {(det.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="py-1.5 px-3 text-[#708096] whitespace-nowrap">
                      {det.speed_kmh > 0 ? `${det.speed_kmh} km/h ${det.direction || ""}` : "stationary"}
                    </td>
                    <td className="py-1.5 px-3 text-[#708096] whitespace-nowrap truncate max-w-[120px]">
                      {item.source}
                    </td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={5} className="py-4 text-center text-[#708096] italic text-[11px]">
                  No active detections on current frame
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
