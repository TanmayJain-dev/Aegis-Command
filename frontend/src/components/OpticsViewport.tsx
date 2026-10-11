"use client";

import React, { useRef, useState, useEffect, useCallback, useMemo } from "react";
import {
  Video,
  Crosshair,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  Target,
} from "lucide-react";
import { FeedItem } from "../lib/feeds";
import { Timeline, DrawableDetection } from "../lib/timeline";
import { useVideoOverlay } from "../hooks/useVideoOverlay";
import { PerfReport } from "../types/aegis";

export interface OpticsViewportProps {
  feeds: FeedItem[];
  activeFeed: FeedItem | null;
  onSelectFeed: (feedId: string) => void;
  timeline: Timeline | null;
  liteMode: boolean;
  onThreatSample?: (currentTime: number, obs: DrawableDetection[]) => void;
  perfEnabled?: boolean;
  perfTargetFrames?: number;
  onPerfReport?: (report: PerfReport) => void;
}

export function OpticsViewport({
  feeds,
  activeFeed,
  onSelectFeed,
  timeline,
  liteMode,
  onThreatSample,
  perfEnabled = false,
  perfTargetFrames = 600,
  onPerfReport,
}: OpticsViewportProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // Benchmarking refs
  const perfDrawTimes = useRef<number[]>([]);
  const perfBoxCounts = useRef<number[]>([]);
  const perfStartTime = useRef<number | null>(null);
  const perfDone = useRef(false);

  const onThreatSampleRef = useRef(onThreatSample);
  const onPerfReportRef = useRef(onPerfReport);

  useEffect(() => {
    onThreatSampleRef.current = onThreatSample;
    onPerfReportRef.current = onPerfReport;
  });

  const handleFrame = useCallback(
    (mediaTime: number, obs: DrawableDetection[]) => {
      if (onThreatSampleRef.current && obs.length > 0) {
        onThreatSampleRef.current(mediaTime, obs);
      }
    },
    []
  );

  const handleDrawTiming = useCallback(
    (drawMs: number, boxCount: number) => {
      if (!perfEnabled || perfDone.current) return;

      if (perfStartTime.current === null) {
        perfStartTime.current = performance.now();
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
        const totalSec = (performance.now() - (perfStartTime.current ?? performance.now())) / 1000;
        const totalCommits = (typeof window !== "undefined" && window.__AEGIS_REACT_COMMITS__) ? window.__AEGIS_REACT_COMMITS__ : 0;
        const commitsPer100 = (totalCommits / perfDrawTimes.current.length) * 100;

        const report: PerfReport = {
          frames: perfDrawTimes.current.length,
          mean_draw_ms: Number(mean.toFixed(3)),
          p95_draw_ms: Number(p95.toFixed(3)),
          mean_boxes: Number(meanBoxes.toFixed(2)),
          total_commits: totalCommits,
          commits_per_100_frames: Number(commitsPer100.toFixed(2)),
          duration_sec: Number(totalSec.toFixed(2)),
          status: meanBoxes === 0 ? "FAIL_ZERO_BOXES" : "OK",
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

  // Extract unique threat timestamps from timeline for threat radar
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

  const formatClock = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const videoSrc = activeFeed?.video || "/feeds/uav-alpha/video.mp4";

  return (
    <div className="flex flex-col gap-3 lg:gap-4 relative w-full">
      {/* Feeds Switcher Bar */}
      {feeds.length >= 2 && (
        <div className="flex items-center gap-2 text-xs overflow-x-auto no-scrollbar pb-1 whitespace-nowrap">
          {feeds.map((feed) => (
            <button
              key={feed.id}
              type="button"
              onClick={() => onSelectFeed(feed.id)}
              className={`px-3 sm:px-4 py-1.5 sm:py-2 border rounded flex items-center gap-1.5 sm:gap-2 transition-all flex-shrink-0 ${
                activeFeed?.id === feed.id
                  ? "bg-cyan-950/40 border-cyan-500/50 text-cyan-400 shadow-[0_0_10px_rgba(6,182,212,0.1)]"
                  : "bg-slate-900/30 border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-300"
              }`}
            >
              <Video size={13} />
              {feed.label}
            </button>
          ))}
        </div>
      )}

      {/* Main Video Viewport Container */}
      <div
        ref={containerRef}
        className="relative flex-1 w-full rounded border border-cyan-900/50 bg-black overflow-hidden group shadow-2xl min-h-[240px] sm:min-h-[300px]"
      >
        {/* Tactical HUD Overlay */}
        <div className="absolute inset-0 z-10 pointer-events-none flex flex-col justify-between p-4">
          <div className="flex justify-between items-start text-[10px] text-cyan-400 font-bold tracking-widest drop-shadow-[0_0_8px_rgba(0,0,0,0.9)]">
            <div className="flex flex-col gap-1 bg-black/40 p-2 rounded backdrop-blur-sm border border-cyan-500/20">
              <span>
                REC{" "}
                <span
                  className={
                    isPlaying
                      ? "text-rose-500 animate-pulse drop-shadow-[0_0_5px_rgba(244,63,94,0.8)]"
                      : "text-slate-500"
                  }
                >
                  ●
                </span>
              </span>
              <span>T-MINUS: {formatClock(currentTime)}</span>
              <span>FPS: {liteMode ? "30.00" : "59.94"}</span>
            </div>
            <div className="flex flex-col items-end gap-1 text-right bg-black/40 p-2 rounded backdrop-blur-sm border border-cyan-500/20">
              <span>FEED ENCRYPTION: AES-256</span>
              <span>SRC: {activeFeed?.label || "UAV-ALPHA"}</span>
              <span>
                STATUS:{" "}
                <span className="text-cyan-400 drop-shadow-[0_0_5px_rgba(6,182,212,0.8)]">
                  LIVE
                </span>
              </span>
            </div>
          </div>

          <div className="absolute inset-0 flex items-center justify-center">
            <Crosshair className="text-cyan-400/40 w-32 h-32 stroke-1 drop-shadow-[0_0_8px_rgba(6,182,212,0.4)]" />
          </div>

          <div className="absolute top-4 left-4 w-8 h-8 border-t-2 border-l-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]" />
          <div className="absolute top-4 right-4 w-8 h-8 border-t-2 border-r-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]" />
          <div className="absolute bottom-12 left-4 w-8 h-8 border-b-2 border-l-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]" />
          <div className="absolute bottom-12 right-4 w-8 h-8 border-b-2 border-r-2 border-cyan-400/60 drop-shadow-[0_0_5px_rgba(0,0,0,0.8)]" />
        </div>

        {/* Video Element */}
        <video
          ref={videoRef}
          src={videoSrc}
          className="absolute inset-0 w-full h-full object-contain filter contrast-125 brightness-90 grayscale-[20%]"
          muted={isMuted}
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={(e) => setDuration(e.currentTarget.duration)}
          onClick={handleTogglePlay}
        />

        {/* High-Performance Canvas Overlay */}
        <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none z-20" />

        {/* Bottom Hover Controls */}
        <div className="absolute bottom-0 w-full h-12 bg-gradient-to-t from-black/90 to-transparent z-30 flex items-end px-4 pb-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
          <div className="flex items-center justify-between w-full text-cyan-400/80">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={handleTogglePlay}
                className="hover:text-cyan-300 transition-colors"
              >
                {isPlaying ? <Pause size={18} /> : <Play size={18} fill="currentColor" />}
              </button>
              <button
                type="button"
                onClick={handleToggleMute}
                className="hover:text-cyan-300 transition-colors"
              >
                {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
              </button>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-1 h-3 bg-cyan-500/40 animate-pulse" />
              <div className="w-1 h-2 bg-cyan-500/40 animate-pulse delay-75" />
              <div className="w-1 h-4 bg-cyan-500/40 animate-pulse delay-150" />
              <div className="w-1 h-2 bg-cyan-500/40 animate-pulse delay-75" />
            </div>
            <button
              type="button"
              onClick={handleToggleFullscreen}
              className="hover:text-cyan-300 transition-colors z-40"
            >
              {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
            </button>
          </div>
        </div>
      </div>

      {/* Threat Radar / Timeline Scrubber */}
      <div
        className="w-full h-8 bg-slate-900 border border-slate-700 relative flex items-center px-1 overflow-hidden shadow-inner rounded cursor-pointer"
        onClick={(e) => {
          const target = (e.target as HTMLElement).closest("[data-seek-time]");
          if (target) {
            const timeVal = target.getAttribute("data-seek-time");
            if (timeVal) {
              handleSeek(parseFloat(timeVal));
            }
          }
        }}
      >
        <span className="absolute left-3 text-[10px] text-cyan-400 z-10 font-bold tracking-widest flex items-center gap-2 pointer-events-none">
          <Target size={12} /> THREAT RADAR
        </span>

        {/* Playhead progress */}
        {duration > 0 && (
          <div
            className="absolute top-0 bottom-0 bg-cyan-500/10 pointer-events-none"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          />
        )}

        {/* Threat markers */}
        {duration > 0 &&
          threatMarkers.map((marker, idx) => {
            const leftPct = (marker.time / duration) * 100;
            if (leftPct < 0 || leftPct > 100) return null;
            return (
              <div
                key={`${marker.time}-${idx}`}
                data-seek-time={marker.time}
                className="absolute h-full w-1 bg-rose-500 hover:w-2 hover:bg-rose-400 z-20 transition-all shadow-[0_0_10px_rgba(244,63,94,0.8)]"
                style={{ left: `${leftPct}%` }}
                title={`Threat [${marker.class}] at ${marker.time.toFixed(1)}s`}
              />
            );
          })}
      </div>
    </div>
  );
}
