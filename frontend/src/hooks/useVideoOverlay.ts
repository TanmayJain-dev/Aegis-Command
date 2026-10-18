import { useEffect, useRef, useCallback } from "react";
import { Timeline, DrawableDetection } from "../lib/timeline";

export interface DrawDetectionsOptions {
  primaryColor?: string;
  fillAlpha?: number;
}

export interface OverlayScale {
  scaleX: number;
  scaleY: number;
  offsetX?: number;
  offsetY?: number;
}

export interface DisplayedVideoRect {
  width: number;
  height: number;
  offsetX: number;
  offsetY: number;
}

/**
 * Computes the actual displayed video frame rectangle inside a container
 * using standard object-contain letterboxing/pillarboxing semantics.
 */
export function computeDisplayedVideoRect(
  containerWidth: number,
  containerHeight: number,
  videoWidth: number,
  videoHeight: number
): DisplayedVideoRect {
  if (containerWidth <= 0 || containerHeight <= 0 || videoWidth <= 0 || videoHeight <= 0) {
    return {
      width: Math.max(0, containerWidth),
      height: Math.max(0, containerHeight),
      offsetX: 0,
      offsetY: 0,
    };
  }

  const videoAspect = videoWidth / videoHeight;
  const containerAspect = containerWidth / containerHeight;

  if (containerAspect > videoAspect) {
    // Pillarboxed (bars on left/right)
    const height = containerHeight;
    const width = containerHeight * videoAspect;
    const offsetX = (containerWidth - width) / 2;
    return { width, height, offsetX, offsetY: 0 };
  } else {
    // Letterboxed (bars on top/bottom)
    const width = containerWidth;
    const height = containerWidth / videoAspect;
    const offsetY = (containerHeight - height) / 2;
    return { width, height, offsetX: 0, offsetY };
  }
}

/**
 * Computes the uniform scale factor and centering offsets to map
 * source coordinate space (e.g. 1920x1080) to the physical video frame
 * rendered inside the container under object-contain.
 */
export function computeOverlayScale(
  containerWidth: number,
  containerHeight: number,
  sourceWidth: number,
  sourceHeight: number,
  videoWidth?: number,
  videoHeight?: number
): OverlayScale {
  const vw = videoWidth && videoWidth > 0 ? videoWidth : sourceWidth;
  const vh = videoHeight && videoHeight > 0 ? videoHeight : sourceHeight;

  const rect = computeDisplayedVideoRect(containerWidth, containerHeight, vw, vh);

  return {
    scaleX: rect.width / sourceWidth,
    scaleY: rect.height / sourceHeight,
    offsetX: rect.offsetX,
    offsetY: rect.offsetY,
  };
}

function getSemanticColor(cls: string, fallback?: string): string {
  if (fallback) return fallback;
  const c = (cls || "").toLowerCase();
  if (c === "person" || c === "human" || c === "pedestrian") {
    return "#10b981"; // restrained green
  }
  if (c === "drone" || c === "uav" || c === "threat") {
    return "#ef4444"; // restrained red
  }
  if (["truck", "car", "vehicle", "bus", "motorcycle"].includes(c)) {
    return "#3b82f6"; // restrained blue
  }
  return "#3b82f6";
}

function getSemanticFill(color: string, alpha = 0.08): string {
  if (color === "#10b981") return `rgba(16, 185, 129, ${alpha})`;
  if (color === "#ef4444") return `rgba(239, 68, 68, ${alpha})`;
  if (color === "#3b82f6") return `rgba(59, 130, 246, ${alpha})`;
  return `rgba(59, 130, 246, ${alpha})`;
}

/**
 * Pure canvas rendering routine for bounding boxes and telemetry tags.
 * Restrained semantic styling: green for personnel, blue for vehicles, red for critical threats.
 */
export function drawDetections(
  ctx: CanvasRenderingContext2D,
  detections: DrawableDetection[],
  scale: OverlayScale,
  opts: DrawDetectionsOptions = {}
): void {
  const fillAlpha = opts.fillAlpha ?? 0.08;
  const offX = scale.offsetX ?? 0;
  const offY = scale.offsetY ?? 0;

  for (let i = 0; i < detections.length; i++) {
    const det = detections[i];
    const [x1, y1, x2, y2] = det.box;

    const scaledX = offX + x1 * scale.scaleX;
    const scaledY = offY + y1 * scale.scaleY;
    const scaledWidth = (x2 - x1) * scale.scaleX;
    const scaledHeight = (y2 - y1) * scale.scaleY;

    const color = getSemanticColor(det.class, opts.primaryColor);

    // Clean semantic bounding box
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);

    // Subtle box tint fill
    ctx.fillStyle = getSemanticFill(color, fillAlpha);
    ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);

    // Header telemetry label: clean solid label
    const hasTrackingInfo = Boolean(det.id && det.direction && det.direction !== '-');
    const labelText = det.class.toLowerCase() + ' ' + Math.round(det.confidence * 100) + '%';
    const trackText = hasTrackingInfo ? (det.direction + ' · ' + det.speed_kmh + 'km/h') : '';

    const labelHeight = hasTrackingInfo ? 26 : 15;
    const labelY = scaledY >= labelHeight ? scaledY - labelHeight : scaledY;

    ctx.font = '600 10px monospace';
    const textWidth = Math.max(ctx.measureText(labelText).width + 8, hasTrackingInfo ? ctx.measureText(trackText).width + 8 : 0);
    const labelWidth = Math.min(Math.max(textWidth, 64), Math.max(scaledWidth, 64));

    // Solid label badge
    ctx.fillStyle = color;
    ctx.fillRect(scaledX, labelY, labelWidth, labelHeight);

    // Dark text on solid badge for high contrast
    ctx.fillStyle = '#070d17';
    ctx.font = '600 9px monospace';
    ctx.fillText(labelText, scaledX + 4, labelY + 11);

    if (hasTrackingInfo) {
      ctx.fillStyle = '#070d17';
      ctx.font = '500 8px monospace';
      ctx.fillText(trackText, scaledX + 4, labelY + 22);
    }
  }
}

export interface UseVideoOverlayOptions {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  timeline: Timeline | null;
  liteMode?: boolean;
  onFrame?: (time: number, detections: DrawableDetection[]) => void;
  onDrawTiming?: (drawTimeMs: number, boxCount: number) => void;
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
  onDrawTiming,
}: UseVideoOverlayOptions): { redraw: () => void } {
  const onFrameRef = useRef(onFrame);
  const onDrawTimingRef = useRef(onDrawTiming);
  const timelineRef = useRef(timeline);
  const liteModeRef = useRef(liteMode);

  useEffect(() => {
    onFrameRef.current = onFrame;
    onDrawTimingRef.current = onDrawTiming;
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

    const tStart = performance.now();
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    const detections = tl.sampleAt(t);
    const scale = computeOverlayScale(
      cssWidth,
      cssHeight,
      tl.meta.width,
      tl.meta.height,
      video.videoWidth,
      video.videoHeight
    );

    drawDetections(ctx, detections, scale);
    const tEnd = performance.now();

    if (onDrawTimingRef.current) {
      onDrawTimingRef.current(tEnd - tStart, detections.length);
    }

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
