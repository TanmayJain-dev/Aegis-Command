export type ThreatClass = "truck" | "car" | "person" | "drone" | "motorcycle" | "bus" | string;

export interface ThreatAssessment {
  threat_level?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  score?: number;
  reasoning?: string;
  recommended_action?: string;
  previous_incidents?: number;
}

export interface IntelRecord {
  id: string;
  score?: number;
  location?: string;
  lat?: number;
  lng?: number;
  transcript?: string;
  timestamp?: string;
  summary?: string;
  text?: string;
}

export interface ThreatTriggerPayload {
  class: string;
  confidence: number;
  speed_kmh: number;
  direction: string;
  latitude: number;
  longitude: number;
  video_x: number;
  video_y: number;
  detection_time: number;
  timestamp: string;
}

export interface AegisHistoryRecord {
  id?: number | string;
  incident_id?: string;
  timestamp?: string;
  created_at?: string;
  threat_level?: string;
  score?: number;
  threat_class?: string;
  class?: string;
  reasoning?: string;
  recommended_action?: string;
  previous_incidents?: number;
  telemetry?: Record<string, unknown>;
  assessment?: ThreatAssessment;
  evidence?: IntelRecord[];
  payload?: Record<string, unknown>;
  telemetry_json?: string;
  assessment_json?: string;
  evidence_json?: string;
  object_class?: string;
  latitude?: number;
  longitude?: number;
}

export interface ChatterItem {
  src: string;
  time: string;
  text: string;
  threat: "HIGH" | "MED" | "LOW";
}

export interface PerfReport {
  frames: number;
  mean_draw_ms: number;
  p95_draw_ms: number;
  total_commits: number;
  commits_per_second: number;
  duration_sec: number;
}

declare global {
  interface Window {
    __AEGIS_PERF_REPORT__?: PerfReport;
    __AEGIS_PERF_DONE__?: boolean;
    __AEGIS_PERF_FRAMES__?: number;
  }
}
