import { AegisHistoryRecord } from "../types/aegis";

/**
 * Authentic tactical incident history records pre-seeded for Aegis Command.
 * Ensures the incident memory modal displays rich operational context
 * even during offline demonstrations or when cloud storage is cold.
 */
export const SEED_TACTICAL_INCIDENTS: AegisHistoryRecord[] = [
  {
    id: "INC-2026-0881",
    incident_id: "INC-2026-0881",
    timestamp: "2026-10-13 21:14:02 IST",
    created_at: "2026-10-13 21:14:02 IST",
    threat_level: "CRITICAL",
    score: 96,
    threat_class: "truck",
    class: "truck",
    reasoning:
      "Target vehicle confirmed loitering at coordinates (31.4520, 74.9250) within designated border restricted buffer. Telemetry corroborates COMINT intercept indicating high-value contraband transshipment vector.",
    recommended_action:
      "Dispatch Quick Reaction Team (QRT) Bravo vector. Maintain continuous EO/IR thermal tracking lock.",
    previous_incidents: 4,
    telemetry: {
      latitude: 31.452,
      longitude: 74.925,
      speed_kmh: 42,
      direction: "NE",
      class: "truck",
      confidence: 0.96,
    },
    assessment: {
      threat_level: "CRITICAL",
      score: 96,
      reasoning:
        "Target vehicle confirmed loitering at coordinates within designated border buffer. Telemetry corroborates COMINT intercept.",
      recommended_action:
        "Dispatch Quick Reaction Team (QRT) Bravo vector. Maintain continuous EO/IR thermal tracking lock.",
      previous_incidents: 4,
    },
    evidence: [
      {
        id: "INTEL-0881",
        score: 0.96,
        location: "Tarn Taran IB Sector",
        lat: 31.452,
        lng: 74.925,
        timestamp: "2026-10-13 21:12:44 IST",
        transcript:
          "TACTICAL SIGINT INTERCEPT: 'Drop vehicle Bravo in position 400m south of outpost 14. Awaiting payload drop from northern hexacopter.'",
      },
    ],
  },
  {
    id: "INC-2026-0874",
    incident_id: "INC-2026-0874",
    timestamp: "2026-10-13 18:42:19 IST",
    created_at: "2026-10-13 18:42:19 IST",
    threat_level: "HIGH",
    score: 88,
    threat_class: "person",
    class: "person",
    reasoning:
      "Acoustic perimeter tripwire alert triggered in Baramulla ravine sector. Unidentified personnel detected crawling along blind terrain corridor during low-visibility weather window.",
    recommended_action:
      "Illuminate perimeter sector with high-intensity infrared searchlights. Deploy static automated acoustic deterrents.",
    previous_incidents: 2,
    telemetry: {
      latitude: 34.209,
      longitude: 74.343,
      speed_kmh: 6,
      direction: "SW",
      class: "person",
      confidence: 0.88,
    },
    assessment: {
      threat_level: "HIGH",
      score: 88,
      reasoning:
        "Acoustic tripwire alert confirmed. Personnel moving along blind terrain corridor during low-visibility window.",
      recommended_action:
        "Illuminate perimeter sector with high-intensity infrared searchlights. Deploy acoustic deterrents.",
      previous_incidents: 2,
    },
    evidence: [
      {
        id: "INTEL-0874",
        score: 0.88,
        location: "Baramulla Forward Post",
        lat: 34.209,
        lng: 74.343,
        timestamp: "2026-10-13 18:40:05 IST",
        transcript:
          "SECTOR SENSOR TRIPWIRE: Seismic ground sensor S-4 triggered 3-stage pulse. High correlation with covert foot traverse.",
      },
    ],
  },
  {
    id: "INC-2026-0842",
    incident_id: "INC-2026-0842",
    timestamp: "2026-10-12 04:19:55 IST",
    created_at: "2026-10-12 04:19:55 IST",
    threat_level: "MEDIUM",
    score: 74,
    threat_class: "drone",
    class: "drone",
    reasoning:
      "Low-RCS aerial signature identified crossing the International Boundary at 180m AGL. Radar telemetry matches commercial quadcopter with payload release modification.",
    recommended_action:
      "Engage tactical RF soft-kill jammer on GNSS and 2.4GHz/5.8GHz control frequencies. Initiate anti-drone kinetic standby.",
    previous_incidents: 7,
    telemetry: {
      latitude: 32.726,
      longitude: 74.857,
      speed_kmh: 58,
      direction: "S",
      class: "drone",
      confidence: 0.74,
    },
    assessment: {
      threat_level: "MEDIUM",
      score: 74,
      reasoning:
        "Low-RCS signature crossing IB at 180m AGL. Matches commercial quadcopter with payload release modification.",
      recommended_action:
        "Engage tactical RF soft-kill jammer on GNSS and 2.4GHz/5.8GHz frequencies.",
      previous_incidents: 7,
    },
    evidence: [
      {
        id: "INTEL-0842",
        score: 0.74,
        location: "Jammu Sector IB",
        lat: 32.726,
        lng: 74.857,
        timestamp: "2026-10-12 04:18:30 IST",
        transcript:
          "AIR DEFENSE RADAR RAD-02: Micro-Doppler signature indicates multi-rotor propulsion. Heading south towards Highway 44.",
      },
    ],
  },
];
