import { useEffect, useRef, useState, useCallback } from "react";
import { ThreatAssessment, ThreatTriggerPayload, IntelRecord } from "../types/aegis";

export interface ThreatSocketMessage {
  event: string;
  assessment?: ThreatAssessment;
  telemetry?: {
    latitude?: number;
    longitude?: number;
    class?: string;
    speed_kmh?: number;
    direction?: string;
  };
  evidence?: IntelRecord[];
  latitude?: number;
  longitude?: number;
  lat?: number;
  lng?: number;
}

export interface UseThreatSocketOptions {
  onThreatAssessed?: (data: ThreatSocketMessage) => void;
}

export interface UseThreatSocketReturn {
  isConnected: boolean;
  latestAssessment: ThreatAssessment | null;
  latestTelemetry: { latitude: number; longitude: number } | null;
  latestEvidence: IntelRecord | null;
  sendThreat: (payload: ThreatTriggerPayload) => boolean;
  clearAssessment: () => void;
}

const TACTICAL_AUDIO_B64 = "data:audio/wav;base64,UklGRl9vT19XQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YU";

export function getWebSocketUrl(): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    return process.env.NEXT_PUBLIC_WS_URL;
  }
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (backendUrl) {
    const wsUrl = backendUrl.replace(/^http:\/\//, "ws://").replace(/^https:\/\//, "wss://");
    return `${wsUrl.replace(/\/+$/, "")}/ws/threat-engine`;
  }
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}/ws/threat-engine`;
  }
  return "ws://localhost:8000/ws/threat-engine";
}

export function useThreatSocket(options?: UseThreatSocketOptions): UseThreatSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [latestAssessment, setLatestAssessment] = useState<ThreatAssessment | null>(null);
  const [latestTelemetry, setLatestTelemetry] = useState<{ latitude: number; longitude: number } | null>(null);
  const [latestEvidence, setLatestEvidence] = useState<IntelRecord | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const optionsRef = useRef(options);

  useEffect(() => {
    optionsRef.current = options;
  });

  useEffect(() => {
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      if (typeof window === "undefined") return;

      const url = getWebSocketUrl();
      const ws = new WebSocket(url);

      ws.onopen = () => {
        if (cancelled) {
          ws.close();
          return;
        }
        wsRef.current = ws;
        setIsConnected(true);
      };

      ws.onmessage = (event: MessageEvent) => {
        try {
          const data: ThreatSocketMessage = JSON.parse(event.data);
          if (data.event !== "THREAT_ASSESSED") {
            return;
          }

          // Tactical audio notification cue
          try {
            const audio = new Audio(TACTICAL_AUDIO_B64);
            audio.play().catch(() => {});
          } catch {
            // Audio policy blocked
          }

          if (data.assessment) {
            setLatestAssessment(data.assessment);
          }

          if (
            data.telemetry &&
            typeof data.telemetry.latitude === "number" &&
            typeof data.telemetry.longitude === "number"
          ) {
            setLatestTelemetry({
              latitude: data.telemetry.latitude,
              longitude: data.telemetry.longitude,
            });
          }

          if (Array.isArray(data.evidence) && data.evidence.length > 0) {
            setLatestEvidence(data.evidence[0]);
          }

          if (optionsRef.current?.onThreatAssessed) {
            optionsRef.current.onThreatAssessed(data);
          }
        } catch (err) {
          console.error("[THREAT WS] Message parse error:", err);
        }
      };

      ws.onerror = () => {
        setIsConnected(false);
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (!cancelled) {
          reconnectTimerRef.current = setTimeout(connect, 2000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const sendThreat = useCallback((payload: ThreatTriggerPayload): boolean => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return false;
    }
    try {
      wsRef.current.send(JSON.stringify(payload));
      return true;
    } catch (err) {
      console.error("[THREAT WS] Send error:", err);
      return false;
    }
  }, []);

  const clearAssessment = useCallback(() => {
    setLatestAssessment(null);
  }, []);

  return {
    isConnected,
    latestAssessment,
    latestTelemetry,
    latestEvidence,
    sendThreat,
    clearAssessment,
  };
}
