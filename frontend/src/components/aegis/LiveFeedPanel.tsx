"use client";

import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
} from "lucide-react";
import { FeedManifestItem } from "../../lib/feeds";
import { Timeline, DrawableDetection } from "../../lib/timeline";
import { useVideoOverlay } from "../../hooks/useVideoOverlay";
import { PerfReport } from "../../types/aegis";

export interface LiveFeedPanelProps {
  activeFeed: FeedManifestItem | null;
  timeline: Timeline | null;
  liteMode: boolean;
  onThreatSample?: (currentTime: number, obs: DrawableDetection[]) => void;
  perfEnabled?: boolean;
  perfTargetFrames?: number;
  onPerfReport?: (report: PerfReport) => void;
  onActiveDetectionsChange?: (detections: DrawableDetection[], time: number) => void;
}

export function LiveFeedPanel({
  activeFeed,
  timeline,
  liteMode,
  onThreatSample,
  perfEnabled = false,
  perfTargetFrames = 600,
  onPerfReport,
  onActiveDetectionsChange,
}: LiveFeedPanelProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [failedVideoSrc, setFailedVideoSrc] = useState<string | null>(null);

  // Benchmarking refs
  const perfDrawTimes = useRef<number[]>([]);
  const perfBoxCounts = useRef<number[]>([]);
  const perfStartTime = useRef<number | null>(null);
  const perfStartCommits = useRef<number | null>(null);
  const perfDone = useRef(false);

  const onThreatSampleRef = useRef(onThreatSample);
  const onPerfReportRef = useRef(onPerfReport);
  const onActiveDetectionsChangeRef = useRef(onActiveDetectionsChange);

  useEffect(() => {
    onThreatSampleRef.current = onThreatSample;
    onPerfReportRef.current = onPerfReport;
    onActiveDetectionsChangeRef.current = onActiveDetectionsChange;
  });

  const handleFrame = useCallback(
    (mediaTime: number, obs: DrawableDetection[]) => {
      if (onThreatSampleRef.current && obs.length > 0) {
        onThreatSampleRef.current(mediaTime, obs);
      }
      if (onActiveDetectionsChangeRef.current) {
        onActiveDetectionsChangeRef.current(obs, mediaTime);
      }
    },
    []
  );

  const handleDrawTiming = useCallback(
    (drawMs: number, boxCount: number) => {
      if (!perfEnabled || perfDone.current) return;

      if (perfStartTime.current === null) {
        perfStartTime.current = performance.now();
        perfStartCommits.current =
          typeof window !== "undefined" &&
          typeof window.__AEGIS_REACT_COMMITS__ === "number"
            ? window.__AEGIS_REACT_COMMITS__
            : 0;
      }
      perfDrawTimes.current.push(drawMs);
      perfBoxCounts.current.push(boxCount);

      if (typeof window !== "undefined") {
        window.__AEGIS_PERF_FRAMES__ = perfDrawTimes.current.length;
      }

      if (perfDrawTimes.current.length >= perfTargetFrames) {
        perfDone.current = true;
        const sorted = [...perfDrawTimes.current].sort((a, b) => a - b);
        const mean = sorted.reduce((a, b) => a + b, 0) / sorted.length;
        const p95 = sorted[Math.floor(sorted.length * 0.95)];
        const totalBoxes = perfBoxCounts.current.reduce((a, b) => a + b, 0);
        const meanBoxes = totalBoxes / perfBoxCounts.current.length;
        const totalSec =
          (performance.now() - (perfStartTime.current ?? performance.now())) /
          1000;
        const rawCommits =
          typeof window !== "undefined" &&
          typeof window.__AEGIS_REACT_COMMITS__ === "number"
            ? window.__AEGIS_REACT_COMMITS__
            : 0;
        const startCommits = perfStartCommits.current ?? 0;
        const playbackCommits = Math.max(0, rawCommits - startCommits);
        const commitsPer100 =
          (playbackCommits / perfDrawTimes.current.length) * 100;

        let status: PerfReport["status"] = "OK";
        if (meanBoxes === 0) {
          status = "FAIL_ZERO_BOXES";
        } else if (rawCommits === 0) {
          status = "FAIL_PROFILER_DISABLED";
        }

        const report: PerfReport = {
          frames: perfDrawTimes.current.length,
          mean_draw_ms: Number(mean.toFixed(3)),
          p95_draw_ms: Number(p95.toFixed(3)),
          mean_boxes: Number(meanBoxes.toFixed(2)),
          total_commits: playbackCommits,
          commits_per_100_frames: Number(commitsPer100.toFixed(2)),
          duration_sec: Number(totalSec.toFixed(2)),
          status,
        };

        if (typeof window !== "undefined") {
          window.__AEGIS_PERF_REPORT__ = report;
          window.__AEGIS_PERF_DONE__ = true;
        }
        if (onPerfReportRef.current) {
          onPerfReportRef.current(report);
        }
      }
    },
    [perfEnabled, perfTargetFrames]
  );

  useVideoOverlay({
    videoRef,
    canvasRef,
    timeline,
    liteMode,
    onFrame: handleFrame,
    onDrawTiming: perfEnabled ? handleDrawTiming : undefined,
  });

  const handleTogglePlay = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    if (isPlaying) {
      video.pause();
      setIsPlaying(false);
    } else {
      const p = video.play();
      if (p !== undefined) {
        p.then(() => setIsPlaying(true)).catch(() => {});
      }
    }
  }, [isPlaying]);

  const handleToggleMute = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !isMuted;
    setIsMuted(!isMuted);
  }, [isMuted]);

  const handleToggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  }, []);

  const handleSeek = useCallback((timeSeconds: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = timeSeconds;
    setCurrentTime(timeSeconds);
    const p = video.play();
    if (p !== undefined) {
      p.then(() => setIsPlaying(true)).catch(() => {});
    }
  }, []);

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    setCurrentTime(video.currentTime);
    if (video.duration && duration === 0) {
      setDuration(video.duration);
    }
  }, [duration]);

  const threatMarkers = useMemo(() => {
    if (!timeline) return [];
    const markers: { time: number; class: string }[] = [];
    const keyframes = timeline.threatKeyframes;
    for (let i = 0; i < keyframes.length; i++) {
      const t = keyframes[i];
      const obsList = timeline.sampleAt(t);
      if (obsList.length > 0) {
        markers.push({ time: t, class: obsList[0].class });
      }
    }
    return markers;
  }, [timeline]);

  const evalBadge = useMemo(() => {
    if (!timeline) {
      return {
        text: "LOADING TELEMETRY...",
        shortText: "LOADING...",
        isEvaluated: false,
        className: "bg-[#121e2c] border-[#243244] text-[#708096]",
      };
    }
    const isEvaluated = Boolean(timeline.meta?.evaluated);
    if (isEvaluated) {
      const cvMetrics = timeline.meta?.cv_metrics;
      const isComplete =
        cvMetrics?.folds_count === undefined || cvMetrics.folds_count >= 5;
      if (cvMetrics?.person_ap50_mean !== undefined && isComplete) {
        const meanPct = (cvMetrics.person_ap50_mean * 100).toFixed(1);
        const stdPct =
          cvMetrics.person_ap50_std !== undefined
            ? ` ± ${(cvMetrics.person_ap50_std * 100).toFixed(1)}%`
            : "";
        return {
          text: `Demo Model · Held-out 5-fold CV Person AP50 ${meanPct}%${stdPct}`,
          shortText: `CV: ${meanPct}%${stdPct}`,
          isEvaluated: true,
          className: "bg-[#10b981]/10 border-[#10b981]/30 text-[#10b981]",
        };
      }
      return {
        text: "Demo Model · Cross-validation in progress",
        shortText: "CV in progress",
        isEvaluated: true,
        className: "bg-[#10b981]/10 border-[#10b981]/30 text-[#10b981]",
      };
    }
    return {
      text: "Baseline Model (zero-shot weights)",
      shortText: "Zero-shot",
      isEvaluated: false,
      className: "bg-[#f59e0b]/10 border-[#f59e0b]/30 text-[#f59e0b]",
    };
  }, [timeline]);

  const formatClock = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`;
  };

  const videoSrc = activeFeed?.video || "/feeds/uav-alpha/video.mp4";
  const videoError = failedVideoSrc === videoSrc;

  return (
    <div className="flex flex-col rounded bg-[#0d1724] border border-[#243244] overflow-hidden w-full">
      {/* Primary Video Header */}
      <div className="px-3.5 py-2.5 bg-[#121e2c] border-b border-[#243244] flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30 text-[10px] font-semibold tracking-wider font-mono">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isPlaying && !videoError ? "bg-[#10b981]" : "bg-[#708096]"
              }`}
            />
            <span>{videoError ? "ERROR" : isPlaying ? "LIVE" : "PAUSED"}</span>
          </div>

          <span className="text-[13px] font-semibold text-[#f2f5f8]">
            {activeFeed?.label || "UAV Alpha"}
          </span>

          <span className="text-[#708096] text-xs">•</span>
          <span className="text-[11px] text-[#a7b2c2]">
            {activeFeed?.sensor || "EO/IR Optronics"}
          </span>
        </div>

        {/* Evaluation Metadata Badge */}
        <div className="flex items-center gap-2">
          <span
            title={timeline?.meta?.note || evalBadge.text}
            className={`px-2 py-0.5 rounded border text-[10px] font-medium font-mono ${evalBadge.className}`}
          >
            <span className="hidden sm:inline">{evalBadge.text}</span>
            <span className="sm:hidden">{evalBadge.shortText}</span>
          </span>
        </div>
      </div>

      {/* Main Viewport Container */}
      <div
        ref={containerRef}
        className="relative w-full aspect-video min-h-[260px] sm:min-h-[340px] lg:min-h-[380px] bg-[#08111d] flex items-center justify-center overflow-hidden group select-none"
      >
        {/* Native Video Element */}
        <video
          ref={videoRef}
          src={videoSrc}
          className="absolute inset-0 w-full h-full object-contain"
          muted={isMuted}
          playsInline
          onError={() => setFailedVideoSrc(videoSrc)}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onClick={handleTogglePlay}
        />

        {/* Video Error Fallback */}
        {videoError && (
          <div className="absolute inset-0 z-15 flex flex-col items-center justify-center bg-[#08111d]/90 backdrop-blur-sm border border-[#ef4444]/30 select-none p-4 text-center">
            <div className="text-[#ef4444] font-mono text-xs font-semibold tracking-wider uppercase mb-1">
              SOURCE MEDIA UNAVAILABLE
            </div>
            <div className="text-[#a7b2c2] font-mono text-[11px] max-w-sm">
              Video media for {activeFeed?.label || "this feed"} could not be loaded.
            </div>
          </div>
        )}

        {/* High-Performance Canvas Overlay */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 pointer-events-none z-10"
        />

        {/* Minimal On-Screen Status Watermark */}
        <div className="absolute top-3 left-3 z-15 pointer-events-none flex items-center gap-2 px-2 py-1 rounded bg-[#08111d]/75 border border-[#243244] text-[10px] font-mono text-[#a7b2c2] backdrop-blur-sm">
          <span>{formatClock(currentTime)}</span>
          <span className="text-[#708096]">|</span>
          <span>{liteMode ? "30 FPS" : "60 FPS"}</span>
        </div>

        {/* Bottom Control Bar */}
        <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#08111d]/95 via-[#08111d]/75 to-transparent z-20 px-3 py-2 flex items-center justify-between text-[#a7b2c2] opacity-90 group-hover:opacity-100 transition-opacity">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleTogglePlay}
              className="p-1 rounded text-[#f2f5f8] hover:text-[#3b82f6] hover:bg-[#172333] transition-colors"
              aria-label={isPlaying ? "Pause video" : "Play video"}
            >
              {isPlaying ? <Pause size={16} /> : <Play size={16} fill="currentColor" />}
            </button>

            <button
              type="button"
              onClick={handleToggleMute}
              className="p-1 rounded text-[#a7b2c2] hover:text-[#f2f5f8] hover:bg-[#172333] transition-colors"
              aria-label={isMuted ? "Unmute audio" : "Mute audio"}
            >
              {isMuted ? <VolumeX size={16} /> : <Volume2 size={16} />}
            </button>

            <span className="text-[11px] font-mono text-[#a7b2c2] ml-1">
              {formatClock(currentTime)} / {formatClock(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleToggleFullscreen}
              className="p-1 rounded text-[#a7b2c2] hover:text-[#f2f5f8] hover:bg-[#172333] transition-colors"
              aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize size={16} /> : <Maximize size={16} />}
            </button>
          </div>
        </div>
      </div>

      {/* Detection Timeline Scrubber Bar */}
      <div className="px-3 py-2 bg-[#0d1724] border-t border-[#243244] flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-[10px] text-[#708096] font-mono">
          <span className="font-semibold text-[#a7b2c2]">TIMELINE SCRUBBER</span>
          <span>{threatMarkers.length} Keyframe Events</span>
        </div>

        <div
          className="relative w-full h-4 bg-[#09111c] border border-[#243244] rounded cursor-pointer overflow-hidden flex items-center"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clickPct = (e.clientX - rect.left) / rect.width;
            if (duration > 0) {
              handleSeek(clickPct * duration);
            }
          }}
          title="Click to seek timeline"
        >
          {/* Progress fill */}
          {duration > 0 && (
            <div
              className="absolute top-0 bottom-0 left-0 bg-[#3b82f6]/25 border-r border-[#3b82f6]"
              style={{ width: `${Math.min(100, (currentTime / duration) * 100)}%` }}
            />
          )}

          {/* Keyframe Threat Event Dots */}
          {duration > 0 &&
            threatMarkers.map((m, idx) => {
              const leftPct = (m.time / duration) * 100;
              if (leftPct < 0 || leftPct > 100) return null;
              const isAlert = m.class === "truck" || m.class === "drone";
              return (
                <div
                  key={`${m.time}-${idx}`}
                  style={{ left: `${leftPct}%` }}
                  className={`absolute top-0 bottom-0 w-1 ${
                    isAlert ? "bg-[#ef4444]" : "bg-[#3b82f6]"
                  } hover:w-2 transition-all`}
                  title={`Event: ${m.class} at ${m.time.toFixed(1)}s`}
                />
              );
            })}
        </div>
      </div>
    </div>
  );
}
