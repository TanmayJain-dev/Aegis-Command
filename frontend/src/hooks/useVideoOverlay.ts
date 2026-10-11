import { useEffect, useRef, useCallback } from "react";
import { Timeline, DrawableDetection } from "../lib/timeline";

export interface DrawDetectionsOptions {
  primaryColor?: string;
  fillAlpha?: number;
}

/**
 * Pure canvas rendering routine for bounding boxes and telemetry tags.
 * Preserves the exact visual style, colors, fonts, and corner brackets of Aegis HUD.
 */
export function drawDetections(
  ctx: CanvasRenderingContext2D,
  detections: DrawableDetection[],
  scale: { scaleX: number; scaleY: number },
  opts: DrawDetectionsOptions = {}
): void {
  const primaryColor = opts.primaryColor ?? "#06b6d4"; // cyan-500
  const fillAlpha = opts.fillAlpha ?? 0.15;

  for (let i = 0; i < detections.length; i++) {
    const det = detections[i];
    const [x1, y1, x2, y2] = det.box;

    const scaledX = x1 * scale.scaleX;
    const scaledY = y1 * scale.scaleY;
    const scaledWidth = (x2 - x1) * scale.scaleX;
    const scaledHeight = (y2 - y1) * scale.scaleY;

    // Tactical cyan bounding box
    ctx.strokeStyle = primaryColor;
    ctx.lineWidth = 2;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

    // Corner targeting brackets
    ctx.beginPath();
    ctx.moveTo(scaledX, scaledY + 10);
    ctx.lineTo(scaledX, scaledY);
    ctx.lineTo(scaledX + 10, scaledY);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(scaledX + scaledWidth - 10, scaledY);
    ctx.lineTo(scaledX + scaledWidth, scaledY);
    ctx.lineTo(scaledX + scaledWidth, scaledY + 10);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(scaledX, scaledY + scaledHeight - 10);
    ctx.lineTo(scaledX, scaledY + scaledHeight);
    ctx.lineTo(scaledX + 10, scaledY + scaledHeight);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(scaledX + scaledWidth - 10, scaledY + scaledHeight);
    ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight);
    ctx.lineTo(scaledX + scaledWidth, scaledY + scaledHeight - 10);
    ctx.stroke();

    // Box tint fill
    ctx.fillStyle = `rgba(6, 182, 212, ${fillAlpha})`;
    ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);

    // Header telemetry label
    const hasTrackingInfo = Boolean(det.id && det.direction && det.direction !== "-");
    const labelHeight = hasTrackingInfo ? 34 : 20;

    ctx.fillStyle = primaryColor;
    ctx.fillRect(scaledX, scaledY - labelHeight, 140, labelHeight);

    ctx.fillStyle = "#0a0a0a"; // Dark text on cyan background
    ctx.font = "bold 10px monospace";
    ctx.fillText(
      `[${det.class.toUpperCase()}] ${(det.confidence * 100).toFixed(1)}%`,
      scaledX + 4,
      scaledY - (hasTrackingInfo ? 20 : 6)
    );

    if (hasTrackingInfo) {
      ctx.fillText(
        `${det.id} · ${det.direction} · ${det.speed_kmh}km/h`,
        scaledX + 4,
        scaledY - 6
      );
    }
  }
}

export interface UseVideoOverlayOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  timeline: Timeline | null;
  liteMode?: boolean;
  onFrame?: (time: number, detections: DrawableDetection[]) => void;
}

/**
 * High-performance video overlay hook:
 * - Uses requestVideoFrameCallback with metadata.mediaTime and requestAnimationFrame fallback
 * - Sized with ResizeObserver x devicePixelRatio (capped at 2 in standard, 1 in lite mode)
 * - Zero canvas resize allocation inside draw loop
 * - Automatically pauses scheduling when video is paused/ended
 * - Zero console.log in playback path
 */
export function useVideoOverlay({
  videoRef,
  canvasRef,
  timeline,
  liteMode = false,
  onFrame,
}: UseVideoOverlayOptions): { redraw: () => void } {
  const onFrameRef = useRef(onFrame);
  const timelineRef = useRef(timeline);
  const liteModeRef = useRef(liteMode);

  useEffect(() => {
    onFrameRef.current = onFrame;
    timelineRef.current = timeline;
    liteModeRef.current = liteMode;
  });

  const draw = useCallback((mediaTime?: number) => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    const tl = timelineRef.current;
    if (!video || !canvas || !tl) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const t = typeof mediaTime === "number" ? mediaTime : video.currentTime;

    const cssWidth = canvas.clientWidth;
    const cssHeight = canvas.clientHeight;
    if (cssWidth === 0 || cssHeight === 0) return;

    ctx.clearRect(0, 0, cssWidth, cssHeight);

    const detections = tl.sampleAt(t);
    const scale = {
      scaleX: cssWidth / tl.meta.width,
      scaleY: cssHeight / tl.meta.height,
    };

    drawDetections(ctx, detections, scale);

    if (onFrameRef.current) {
      onFrameRef.current(t, detections);
    }
  }, [videoRef, canvasRef]);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    let rVFCId: number | null = null;
    let rAFId: number | null = null;
    let isRunning = false;

    const scheduleNextFrame = () => {
      if (!isRunning) return;
      const vid = videoRef.current;
      if (!vid || vid.paused || vid.ended) {
        isRunning = false;
        return;
      }

      const hasRVFC = typeof (vid as unknown as { requestVideoFrameCallback?: unknown }).requestVideoFrameCallback === "function";
      if (hasRVFC) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rVFCId = (vid as any).requestVideoFrameCallback(
          (_now: DOMHighResTimeStamp, metadata: { mediaTime: number }) => {
            draw(metadata.mediaTime);
            scheduleNextFrame();
          }
        );
      } else {
        rAFId = requestAnimationFrame(() => {
          const currentVid = videoRef.current;
          if (currentVid) {
            draw(currentVid.currentTime);
          }
          scheduleNextFrame();
        });
      }
    };

    const startLoop = () => {
      if (isRunning) return;
      isRunning = true;
      scheduleNextFrame();
    };

    const stopLoop = () => {
      isRunning = false;
      const vid = videoRef.current;
      if (rVFCId !== null && vid && "cancelVideoFrameCallback" in vid) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (vid as any).cancelVideoFrameCallback(rVFCId);
        rVFCId = null;
      }
      if (rAFId !== null) {
        cancelAnimationFrame(rAFId);
        rAFId = null;
      }
    };

    const handlePlay = () => startLoop();
    const handlePause = () => {
      stopLoop();
      draw();
    };
    const handleSeeked = () => draw();
    const handleLoadedData = () => draw();

    video.addEventListener("play", handlePlay);
    video.addEventListener("playing", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("ended", handlePause);
    video.addEventListener("seeked", handleSeeked);
    video.addEventListener("loadeddata", handleLoadedData);

    // Initial resize sync & observer
    const syncCanvasSize = (width: number, height: number) => {
      if (width === 0 || height === 0) return;
      const maxDpr = liteModeRef.current ? 1 : 2;
      const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
      const pixelWidth = Math.round(width * dpr);
      const pixelHeight = Math.round(height * dpr);

      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;

        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        }
      }
      draw();
    };

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        syncCanvasSize(width, height);
      }
    });

    resizeObserver.observe(video);

    // Initial sync
    if (video.clientWidth > 0 && video.clientHeight > 0) {
      syncCanvasSize(video.clientWidth, video.clientHeight);
    }

    if (!video.paused && !video.ended) {
      startLoop();
    }

    return () => {
      stopLoop();
      resizeObserver.disconnect();
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("playing", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("ended", handlePause);
      video.removeEventListener("seeked", handleSeeked);
      video.removeEventListener("loadeddata", handleLoadedData);
    };
  }, [videoRef, canvasRef, draw]);

  return { redraw: draw };
}
